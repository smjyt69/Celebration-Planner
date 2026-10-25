"""Planning knowledge, loaded from JSON files in `planner/content/` and validated on import.

Keeping the content in data files means it can be reviewed and tuned without touching code, and a
mistake (for example budget weights that do not sum to 100) fails fast with a clear message instead
of producing a wrong plan. All benchmark numbers are illustrative heuristics (see README, "Assumptions").
"""
from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .models import TimelineTemplate, VendorTemplate

CONTENT_DIR = Path(__file__).resolve().parent / "content"

# Fixed vocabulary shared by validation, the engine and the UI.
EVENT_TYPES: tuple[str, ...] = ("wedding", "birthday", "community")
VENUE_TYPES: tuple[str, ...] = ("indoor", "outdoor", "home")
VIBES: tuple[str, ...] = ("traditional", "modern", "minimal", "fun")
DIETARY: tuple[str, ...] = ("vegetarian", "vegan", "jain", "halal", "gluten_free")
ATTENDEES: tuple[str, ...] = ("kids", "seniors")
CURRENCIES: dict[str, str] = {"INR": "₹", "USD": "$", "EUR": "€", "GBP": "£"}

# Budget lines the engine moves money between, so every event type must define them.
REQUIRED_BUDGET_KEYS: tuple[str, ...] = ("venue", "catering", "decor", "entertainment", "contingency")
VENDOR_LIST_KEYS: tuple[str, ...] = ("ask", "contract")


class ContentError(ValueError):
    """Raised when the planning content is inconsistent."""


# ---------------------------------------------------------------- validation
def validate_content(
    weights: Mapping[str, Mapping[str, int]],
    min_per_guest: Mapping[str, Mapping[str, int]],
    timelines: Mapping[str, Sequence[TimelineTemplate]],
    vendors: Mapping[str, Sequence[VendorTemplate]],
    ideas: Mapping[str, Mapping[str, Sequence[str]]],
) -> None:
    """Check cross-file consistency. Raises ContentError describing the first problem found."""
    for event in EVENT_TYPES:
        for table_name, table in (("budget weights", weights), ("timelines", timelines),
                                  ("vendors", vendors), ("ideas", ideas)):
            if event not in table:
                raise ContentError(f"{table_name}: missing event type '{event}'")

        event_weights = weights[event]
        if sum(event_weights.values()) != 100:
            raise ContentError(f"budget weights for '{event}' sum to {sum(event_weights.values())}, expected 100")
        missing = [key for key in REQUIRED_BUDGET_KEYS if key not in event_weights]
        if missing:
            raise ContentError(f"budget weights for '{event}' lack required lines: {', '.join(missing)}")

        if not any(step.days_before == 0 for step in timelines[event]):
            raise ContentError(f"timeline for '{event}' has no event-day (days_before 0) task")

        for vendor in vendors[event]:
            _check_vendor(vendor, event)

        for vibe in VIBES:
            if not ideas[event].get(vibe):
                raise ContentError(f"ideas for '{event}' have no entries for style '{vibe}'")

    for currency in CURRENCIES:
        if currency not in min_per_guest:
            raise ContentError(f"minimum spend per guest: missing currency '{currency}'")
        for event in EVENT_TYPES:
            if min_per_guest[currency].get(event, 0) <= 0:
                raise ContentError(f"minimum spend per guest for {currency}/{event} must be positive")


def _check_vendor(vendor: VendorTemplate, context: str) -> None:
    name = vendor.get("vendor", "?")
    for key in ("category", "vendor", *VENDOR_LIST_KEYS):
        if not vendor.get(key):
            raise ContentError(f"vendor '{name}' ({context}) has no '{key}'")


# ---------------------------------------------------------------- loading
def _read(name: str) -> Any:
    return json.loads((CONTENT_DIR / name).read_text(encoding="utf-8"))


def _vendor(raw: Mapping[str, Any]) -> VendorTemplate:
    """Convert a JSON vendor object to a VendorTemplate (JSON arrays become tuples where required)."""
    vendor: VendorTemplate = {
        "category": raw["category"], "vendor": raw["vendor"],
        "ask": list(raw["ask"]), "contract": list(raw["contract"]),
    }
    if "skip_venue" in raw:
        vendor["skip_venue"] = tuple(raw["skip_venue"])
    if "only_venue" in raw:
        vendor["only_venue"] = tuple(raw["only_venue"])
    if "only_attendee" in raw:
        vendor["only_attendee"] = raw["only_attendee"]
    return vendor


_budget = _read("budget.json")
_timelines = _read("timelines.json")
_vendors = _read("vendors.json")
_ideas = _read("ideas.json")

BUDGET_WEIGHTS: dict[str, dict[str, int]] = _budget["weights"]
MIN_PER_GUEST: dict[str, dict[str, int]] = _budget["min_per_guest"]
LABELS: dict[str, str] = _budget["labels"]

TIMELINES: dict[str, list[TimelineTemplate]] = {
    event: [TimelineTemplate(**step) for step in steps] for event, steps in _timelines.items()
}

VENDORS: dict[str, list[VendorTemplate]] = {
    event: [_vendor(v) for v in vendors] for event, vendors in _vendors["by_event"].items()
}
EXTRA_VENDORS: list[VendorTemplate] = [_vendor(v) for v in _vendors["extra"]]

IDEAS: dict[str, dict[str, list[str]]] = _ideas["by_style"]
INTEREST_IDEAS: dict[str, str] = _ideas["interests"]
CONTEXT_IDEAS: dict[str, str] = _ideas["context"]

for _vendor_template in EXTRA_VENDORS:
    _check_vendor(_vendor_template, "extra")
validate_content(BUDGET_WEIGHTS, MIN_PER_GUEST, TIMELINES, VENDORS, IDEAS)
