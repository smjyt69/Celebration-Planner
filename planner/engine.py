"""Deterministic planning engine: context in, budget / timeline / vendors / ideas out.

Pure functions only (no I/O, no clock access: `today` is passed in), so every rule is unit-testable
and the app stays useful even when the GenAI layer is unavailable.
"""
from __future__ import annotations

from datetime import date, timedelta

from .data import (BUDGET_WEIGHTS, CONTEXT_IDEAS, CURRENCIES, EXTRA_VENDORS, IDEAS, INTEREST_IDEAS,
                   LABELS, MIN_PER_GUEST, TIMELINES, VENDORS)
from .validation import PlanRequest

FLOOR = 2                 # no budget category is squeezed below this percentage
HEAVY_DAYS = 14           # under this many days left, keep only the key tasks
HOME_GUEST_LIMIT = 60
MAX_IDEAS = 10


def label(key: str) -> str:
    return LABELS.get(key, key.replace("_", " ").capitalize())


# ---------------------------------------------------------------- budget
def _shift(weights: dict[str, int], src: str, dst: str, amount: int) -> None:
    """Move up to `amount` percentage points from src to dst without breaching FLOOR."""
    moved = max(0, min(amount, weights[src] - FLOOR))
    weights[src] -= moved
    weights[dst] += moved


def adjust_weights(event_type: str, venue_type: str, tight: bool) -> dict[str, int]:
    """Start from the event-type template, then adapt to venue and affordability. Always sums to 100."""
    w = dict(BUDGET_WEIGHTS[event_type])
    if venue_type == "home":          # no hall to rent: reinvest in food and decor
        extra = max(0, w["venue"] - 5)
        _shift(w, "venue", "catering", extra // 2)
        _shift(w, "venue", "decor", extra - extra // 2)
    if venue_type == "outdoor":       # weather backup comes out of decor
        _shift(w, "decor", "contingency", 3)
    if tight:                         # food first when money is short
        _shift(w, "entertainment", "catering", 2)
        _shift(w, "decor", "catering", 3)
    return w


def build_budget(req: PlanRequest) -> dict:
    min_pg = MIN_PER_GUEST[req.currency][req.event_type]
    per_guest = req.budget // req.guests
    tight = per_guest < min_pg
    weights = adjust_weights(req.event_type, req.venue_type, tight)

    amounts = {k: req.budget * pct // 100 for k, pct in weights.items()}
    amounts["contingency"] += req.budget - sum(amounts.values())  # rounding remainder, so totals are exact

    ordered = sorted(weights, key=lambda k: (k == "contingency", -weights[k]))
    lines = [{"category": k, "label": label(k), "percent": weights[k], "amount": amounts[k]} for k in ordered]
    return {"lines": lines, "per_guest": per_guest, "min_per_guest": min_pg, "tight": tight,
            "guests_supported": max(1, req.budget // min_pg)}


# ---------------------------------------------------------------- timeline
def build_timeline(req: PlanRequest, today: date) -> dict:
    template = TIMELINES[req.event_type]
    lead = max(days for days, *_ in template)
    days_left = (req.event_date - today).days
    factor = min(1.0, days_left / lead)
    heavy = days_left < HEAVY_DAYS

    tasks, skipped = [], []
    for i, (days, title, category, critical) in enumerate(template):
        if heavy and not critical:
            skipped.append(title)
            continue
        offset = round(days * factor)
        tasks.append({"id": f"{req.event_type}-{i}", "title": title, "category": category,
                      "critical": critical, "days_before": offset,
                      "due_date": (req.event_date - timedelta(days=offset)).isoformat()})
    tasks.sort(key=lambda t: (t["due_date"], not t["critical"]))
    return {"tasks": tasks, "rushed": factor < 1.0, "heavy": heavy, "ideal_lead_days": lead,
            "days_left": days_left, "skipped": skipped}


# ---------------------------------------------------------------- vendors
def build_vendors(req: PlanRequest, budget: dict) -> list[dict]:
    amounts = {line["category"]: line["amount"] for line in budget["lines"]}
    out = []
    candidates = list(VENDORS[req.event_type]) + list(EXTRA_VENDORS)
    for v in candidates:
        if req.venue_type in v.get("skip_venue", ()):
            continue
        if "only_venue" in v and req.venue_type not in v["only_venue"]:
            continue
        if "only_attendee" in v and v["only_attendee"] not in req.attendees:
            continue
        ask = list(v["ask"])
        if v["category"] == "catering" and req.dietary:
            ask.append("Can you prepare and serve separately for: " + ", ".join(d.replace("_", "-") for d in req.dietary) + "?")
        out.append({"category": v["category"], "label": label(v["category"]), "vendor": v["vendor"],
                    "ask": ask, "contract": list(v["contract"]), "budget": amounts.get(v["category"])})
    return out


# ---------------------------------------------------------------- ideas
def build_ideas(req: PlanRequest) -> list[str]:
    ideas = list(IDEAS[req.event_type][req.vibe])
    if "kids" in req.attendees:
        ideas.append(CONTEXT_IDEAS["kids"])
    if "seniors" in req.attendees:
        ideas.append(CONTEXT_IDEAS["seniors"])
    if req.dietary:
        ideas.append(CONTEXT_IDEAS["dietary"])
    if req.venue_type == "outdoor":
        ideas.append(CONTEXT_IDEAS["outdoor"])
    for interest in req.interests:
        ideas.append(INTEREST_IDEAS.get(interest.lower()) or
                     f"Build a small theme moment around '{interest}' (a decor corner, a game or a favour)")
    return list(dict.fromkeys(ideas))[:MAX_IDEAS]


# ---------------------------------------------------------------- notes
def season_notes(req: PlanRequest) -> list[dict]:
    """Seasonal advice. Assumes an Indian climate and wedding calendar (see README)."""
    month, notes = req.event_date.month, []
    if req.venue_type == "outdoor" and month in (6, 7, 8, 9):
        notes.append({"level": "warning", "text": "Monsoon months: arrange a covered or indoor backup and weatherproof decor."})
    if req.venue_type == "outdoor" and month in (4, 5):
        notes.append({"level": "info", "text": "Peak summer: schedule for the evening and plan shade, water and cooling."})
    if req.event_type == "wedding" and month in (11, 12, 1, 2):
        notes.append({"level": "warning", "text": "Peak wedding season: venues, photographers and caterers sell out early, so book them first."})
    return notes


def build_notes(req: PlanRequest, budget: dict, timeline: dict) -> list[dict]:
    notes = []
    if budget["tight"]:
        notes.append({"level": "warning", "text": (
            f"Budget works out to {budget['per_guest']:,} per guest, below the usual minimum of "
            f"{budget['min_per_guest']:,} for a {req.event_type}. Food is prioritised; consider about "
            f"{budget['guests_supported']:,} guests, a home or community venue, or a weekday date.")})
    if timeline["rushed"]:
        notes.append({"level": "warning", "text": (
            f"Only {timeline['days_left']} days left versus the ideal {timeline['ideal_lead_days']}: "
            "the schedule has been compressed. Book the critical vendors first.")})
    if timeline["heavy"]:
        notes.append({"level": "warning", "text": f"With under two weeks to go, {len(timeline['skipped'])} optional tasks were left out so you can focus on the essentials."})
    if req.venue_type == "home" and req.guests > HOME_GUEST_LIMIT:
        notes.append({"level": "warning", "text": f"{req.guests} guests is a lot for a home. Check space, parking and neighbours' noise rules."})
    notes.extend(season_notes(req))
    return notes


# ---------------------------------------------------------------- orchestration
def build_plan(req: PlanRequest, today: date) -> dict:
    budget = build_budget(req)
    timeline = build_timeline(req, today)
    return {
        "summary": {
            "event_type": req.event_type, "title": req.title or f"Your {req.event_type}",
            "event_date": req.event_date.isoformat(), "days_left": timeline["days_left"],
            "guests": req.guests, "budget": req.budget, "currency": req.currency,
            "symbol": CURRENCIES[req.currency], "venue_type": req.venue_type, "vibe": req.vibe,
            "dietary": list(req.dietary), "attendees": list(req.attendees), "interests": list(req.interests),
        },
        "notes": build_notes(req, budget, timeline),
        "budget": budget,
        "timeline": timeline,
        "vendors": build_vendors(req, budget),
        "ideas": build_ideas(req),
    }


# ---------------------------------------------------------------- offline Q&A
_ROUTES = (
    (("budget", "cost", "price", "afford", "spend", "money"), "budget"),
    (("guest", "headcount", "how many"), "guests"),
    (("when", "timeline", "deadline", "schedule", "start", "first", "next"), "timeline"),
    (("vendor", "book", "hire", "checklist", "caterer", "photographer"), "vendors"),
    (("idea", "theme", "decor", "suggest", "surprise"), "ideas"),
)


def answer_offline(question: str, plan: dict) -> str:
    """Keyword-routed answer built from the plan, used when no AI key is configured or the call fails."""
    q, s = question.lower(), plan["summary"]
    topic = next((name for words, name in _ROUTES if any(w in q for w in words)), None)
    sym = s["symbol"]
    if topic == "budget":
        top = plan["budget"]["lines"][:3]
        parts = ", ".join(f"{l['label']} {sym}{l['amount']:,} ({l['percent']}%)" for l in top)
        return f"Your {sym}{s['budget']:,} budget is about {sym}{plan['budget']['per_guest']:,} per guest. Biggest shares: {parts}."
    if topic == "guests":
        b = plan["budget"]
        return (f"You plan {s['guests']:,} guests at about {sym}{b['per_guest']:,} each. "
                f"This budget comfortably supports about {b['guests_supported']:,} guests for a {s['event_type']}.")
    if topic == "timeline":
        nxt = plan["timeline"]["tasks"][:3]
        parts = "; ".join(f"{t['title']} (by {t['due_date']})" for t in nxt)
        return f"Start with: {parts}. The event is in {s['days_left']} days."
    if topic == "vendors":
        parts = ", ".join(v["vendor"] for v in plan["vendors"][:5])
        return f"Vendors to line up: {parts}. Open each one in the checklist for questions to ask and contract must-haves."
    if topic == "ideas":
        return "Ideas to start with: " + "; ".join(plan["ideas"][:3]) + "."
    return ("I can answer questions about your budget, guest count, timeline, vendors and ideas. "
            "Try: 'What should I book first?' or 'How is my budget split?'")
