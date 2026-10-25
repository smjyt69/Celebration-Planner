"""Deterministic planning engine: context in, budget / timeline / vendors / ideas out.

Pure functions only (no I/O, no clock access: `today` is passed in), so every rule is unit-testable
and the app stays useful even when the GenAI layer is unavailable.
"""
from __future__ import annotations

from datetime import date, timedelta

from .data import (
    BUDGET_WEIGHTS,
    CONTEXT_IDEAS,
    CURRENCIES,
    EXTRA_VENDORS,
    IDEAS,
    INTEREST_IDEAS,
    LABELS,
    MIN_PER_GUEST,
    TIMELINES,
    VENDORS,
)
from .models import Budget, BudgetLine, Note, Plan, Task, Timeline, Vendor, VendorTemplate
from .validation import PlanRequest

FLOOR = 2                 # no budget category is squeezed below this percentage
HEAVY_DAYS = 14           # under this many days left, keep only the key tasks
HOME_GUEST_LIMIT = 60     # above this, warn that a home may be too small
MAX_IDEAS = 10


def label(key: str) -> str:
    """Human-readable name for a budget or vendor category."""
    return LABELS.get(key, key.replace("_", " ").capitalize())


# ---------------------------------------------------------------- budget
def _shift(weights: dict[str, int], src: str, dst: str, amount: int) -> None:
    """Move up to `amount` percentage points from src to dst without breaching FLOOR."""
    moved = max(0, min(amount, weights[src] - FLOOR))
    weights[src] -= moved
    weights[dst] += moved


def adjust_weights(event_type: str, venue_type: str, tight: bool) -> dict[str, int]:
    """Start from the event-type template, then adapt to venue and affordability.

    The result always sums to 100 and no category falls below FLOOR.
    """
    weights = dict(BUDGET_WEIGHTS[event_type])
    if venue_type == "home":          # no hall to rent: reinvest in food and decor
        spare = max(0, weights["venue"] - 5)
        _shift(weights, "venue", "catering", spare // 2)
        _shift(weights, "venue", "decor", spare - spare // 2)
    if venue_type == "outdoor":       # weather backup comes out of decor
        _shift(weights, "decor", "contingency", 3)
    if tight:                         # food first when money is short
        _shift(weights, "entertainment", "catering", 2)
        _shift(weights, "decor", "catering", 3)
    return weights


def build_budget(req: PlanRequest) -> Budget:
    """Split the budget across categories and judge affordability per guest."""
    min_per_guest = MIN_PER_GUEST[req.currency][req.event_type]
    per_guest = req.budget // req.guests
    tight = per_guest < min_per_guest
    weights = adjust_weights(req.event_type, req.venue_type, tight)

    amounts = {key: req.budget * pct // 100 for key, pct in weights.items()}
    amounts["contingency"] += req.budget - sum(amounts.values())  # rounding remainder: totals stay exact

    ordered = sorted(weights, key=lambda key: (key == "contingency", -weights[key]))
    lines: list[BudgetLine] = [
        {"category": key, "label": label(key), "percent": weights[key], "amount": amounts[key]}
        for key in ordered
    ]
    return {"lines": lines, "per_guest": per_guest, "min_per_guest": min_per_guest, "tight": tight,
            "guests_supported": max(1, req.budget // min_per_guest)}


# ---------------------------------------------------------------- timeline
def build_timeline(req: PlanRequest, today: date) -> Timeline:
    """Scale the ideal timeline to the time actually left, dropping optional tasks if very short."""
    template = TIMELINES[req.event_type]
    ideal_lead = max(step.days_before for step in template)
    days_left = (req.event_date - today).days
    factor = min(1.0, days_left / ideal_lead)
    heavy = days_left < HEAVY_DAYS

    tasks: list[Task] = []
    skipped: list[str] = []
    for index, step in enumerate(template):
        if heavy and not step.critical:
            skipped.append(step.title)
            continue
        offset = round(step.days_before * factor)
        tasks.append({"id": f"{req.event_type}-{index}", "title": step.title, "category": step.category,
                      "critical": step.critical, "days_before": offset,
                      "due_date": (req.event_date - timedelta(days=offset)).isoformat()})
    tasks.sort(key=lambda task: (task["due_date"], not task["critical"]))
    return {"tasks": tasks, "rushed": factor < 1.0, "heavy": heavy, "ideal_lead_days": ideal_lead,
            "days_left": days_left, "skipped": skipped}


# ---------------------------------------------------------------- vendors
def _vendor_applies(template: VendorTemplate, req: PlanRequest) -> bool:
    """Whether a vendor template is relevant for this venue type and these attendees."""
    if req.venue_type in template.get("skip_venue", ()):
        return False
    if "only_venue" in template and req.venue_type not in template["only_venue"]:
        return False
    if "only_attendee" in template and template["only_attendee"] not in req.attendees:
        return False
    return True


def build_vendors(req: PlanRequest, budget: Budget) -> list[Vendor]:
    """Vendor checklist for this event, with questions, contract points and the matching budget."""
    amounts = {line["category"]: line["amount"] for line in budget["lines"]}
    vendors: list[Vendor] = []
    for template in [*VENDORS[req.event_type], *EXTRA_VENDORS]:
        if not _vendor_applies(template, req):
            continue
        category = template["category"]
        questions = list(template["ask"])
        if category == "catering" and req.dietary:
            needs = ", ".join(item.replace("_", "-") for item in req.dietary)
            questions.append(f"Can you prepare and serve separately for: {needs}?")
        vendors.append({"category": category, "label": label(category), "vendor": template["vendor"],
                        "ask": questions, "contract": list(template["contract"]),
                        "budget": amounts.get(category)})
    return vendors


# ---------------------------------------------------------------- ideas
def build_ideas(req: PlanRequest) -> list[str]:
    """Ideas from the chosen style, adapted to attendees, dietary needs, venue and interests."""
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
        ideas.append(INTEREST_IDEAS.get(interest.lower())
                     or f"Build a small theme moment around '{interest}' (a decor corner, a game or a favour)")
    return list(dict.fromkeys(ideas))[:MAX_IDEAS]


# ---------------------------------------------------------------- notes
def season_notes(req: PlanRequest) -> list[Note]:
    """Seasonal advice. Assumes an Indian climate and wedding calendar (see README)."""
    month = req.event_date.month
    notes: list[Note] = []
    if req.venue_type == "outdoor" and month in (6, 7, 8, 9):
        notes.append({"level": "warning",
                      "text": "Monsoon months: arrange a covered or indoor backup and weatherproof decor."})
    if req.venue_type == "outdoor" and month in (4, 5):
        notes.append({"level": "info",
                      "text": "Peak summer: schedule for the evening and plan shade, water and cooling."})
    if req.event_type == "wedding" and month in (11, 12, 1, 2):
        notes.append({"level": "warning", "text": "Peak wedding season: venues, photographers and caterers "
                                                  "sell out early, so book them first."})
    return notes


def build_notes(req: PlanRequest, budget: Budget, timeline: Timeline) -> list[Note]:
    """Warnings and tips that explain how the plan was adapted to the user's situation."""
    notes: list[Note] = []
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
        notes.append({"level": "warning", "text": (
            f"With under two weeks to go, {len(timeline['skipped'])} optional tasks were left out "
            "so you can focus on the essentials.")})
    if req.venue_type == "home" and req.guests > HOME_GUEST_LIMIT:
        notes.append({"level": "warning", "text": (
            f"{req.guests} guests is a lot for a home. Check space, parking and neighbours' noise rules.")})
    notes.extend(season_notes(req))
    return notes


# ---------------------------------------------------------------- orchestration
def build_plan(req: PlanRequest, today: date) -> Plan:
    """Build the complete plan for a validated request."""
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
_ROUTES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("budget", "cost", "price", "afford", "spend", "money"), "budget"),
    (("guest", "headcount", "how many"), "guests"),
    (("when", "timeline", "deadline", "schedule", "start", "first", "next"), "timeline"),
    (("vendor", "book", "hire", "checklist", "caterer", "photographer"), "vendors"),
    (("idea", "theme", "decor", "suggest", "surprise"), "ideas"),
)

HELP_TEXT = ("I can answer questions about your budget, guest count, timeline, vendors and ideas. "
             "Try: 'What should I book first?' or 'How is my budget split?'")


def _topic(question: str) -> str | None:
    lowered = question.lower()
    return next((name for words, name in _ROUTES if any(word in lowered for word in words)), None)


def answer_offline(question: str, plan: Plan) -> str:
    """Keyword-routed answer built from the plan, used when no AI key is set or the AI call fails."""
    summary, budget = plan["summary"], plan["budget"]
    symbol = summary["symbol"]
    topic = _topic(question)
    if topic == "budget":
        shares = ", ".join(f"{line['label']} {symbol}{line['amount']:,} ({line['percent']}%)"
                           for line in budget["lines"][:3])
        return (f"Your {symbol}{summary['budget']:,} budget is about {symbol}{budget['per_guest']:,} "
                f"per guest. Biggest shares: {shares}.")
    if topic == "guests":
        return (f"You plan {summary['guests']:,} guests at about {symbol}{budget['per_guest']:,} each. "
                f"This budget comfortably supports about {budget['guests_supported']:,} guests "
                f"for a {summary['event_type']}.")
    if topic == "timeline":
        steps = "; ".join(f"{task['title']} (by {task['due_date']})" for task in plan["timeline"]["tasks"][:3])
        return f"Start with: {steps}. The event is in {summary['days_left']} days."
    if topic == "vendors":
        names = ", ".join(vendor["vendor"] for vendor in plan["vendors"][:5])
        return (f"Vendors to line up: {names}. Open each one in the checklist for "
                "questions to ask and contract must-haves.")
    if topic == "ideas":
        return "Ideas to start with: " + "; ".join(plan["ideas"][:3]) + "."
    return HELP_TEXT