"""Strict input validation. Everything from the client is untrusted until it passes through here."""
from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from .data import ATTENDEES, CURRENCIES, DIETARY, EVENT_TYPES, VENUE_TYPES, VIBES

MAX_HORIZON_DAYS = 5 * 366
MIN_BUDGET, MAX_BUDGET = 1_000, 100_000_000
MIN_GUESTS, MAX_GUESTS = 1, 5_000
MAX_INTERESTS = 5

_CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f]")
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ValidationError(Exception):
    """Carries a field -> message mapping so the UI can annotate each input."""

    def __init__(self, fields: dict[str, str]):
        super().__init__("Invalid input")
        self.fields = fields


@dataclass(frozen=True)
class PlanRequest:
    event_type: str
    event_date: date
    budget: int
    guests: int
    title: str = ""
    currency: str = "INR"
    venue_type: str = "indoor"
    vibe: str = "modern"
    dietary: tuple[str, ...] = ()
    attendees: tuple[str, ...] = ()
    interests: tuple[str, ...] = ()


def clean_text(value: str, max_len: int) -> str:
    """Strip control characters and surrounding whitespace, then cap the length."""
    return _CONTROL.sub("", value).strip()[:max_len]


def _int_field(data: dict[str, Any], name: str, lo: int, hi: int, errors: dict[str, str]) -> int:
    raw = data.get(name)
    if isinstance(raw, float) and raw.is_integer():
        raw = int(raw)
    if isinstance(raw, bool) or not isinstance(raw, int):
        errors[name] = "Enter a whole number."
        return 0
    if not lo <= raw <= hi:
        errors[name] = f"Enter a number between {lo:,} and {hi:,}."
        return 0
    return raw


def _choice(data: dict[str, Any], name: str, choices: Sequence[str], default: str, errors: dict[str, str]) -> str:
    raw = data.get(name, default)
    if not isinstance(raw, str) or raw not in choices:
        errors[name] = "Choose one of: " + ", ".join(choices) + "."
        return default
    return raw


def _multi(data: dict[str, Any], name: str, choices: Sequence[str], errors: dict[str, str]) -> tuple[str, ...]:
    raw = data.get(name, [])
    if not isinstance(raw, list) or not all(isinstance(x, str) for x in raw):
        errors[name] = "Send a list of options."
        return ()
    cleaned = [x.strip().lower().replace("-", "_").replace(" ", "_") for x in raw]
    cleaned = [x for x in cleaned if x and x != "none"]
    bad = [x for x in cleaned if x not in choices]
    if bad:
        errors[name] = "Unknown option(s). Allowed: " + ", ".join(choices) + "."
        return ()
    return tuple(dict.fromkeys(cleaned))  # de-duplicate, keep order


def parse_plan_request(data: object, today: date) -> PlanRequest:
    """Validate a raw JSON payload and return an immutable PlanRequest."""
    if not isinstance(data, dict):
        raise ValidationError({"body": "Send a JSON object."})
    errors: dict[str, str] = {}

    event_type = _choice(data, "event_type", EVENT_TYPES, "", errors)  # missing -> "" -> error

    event_date = today
    raw_date = data.get("event_date")
    if not isinstance(raw_date, str) or not _ISO_DATE.match(raw_date):
        errors["event_date"] = "Use the format YYYY-MM-DD."
    else:
        try:
            event_date = date.fromisoformat(raw_date)
        except ValueError:
            errors["event_date"] = "That is not a real calendar date."
        else:
            if event_date < today:
                errors["event_date"] = "Pick today or a future date."
            elif event_date > today + timedelta(days=MAX_HORIZON_DAYS):
                errors["event_date"] = "Pick a date within the next five years."

    budget = _int_field(data, "budget", MIN_BUDGET, MAX_BUDGET, errors)
    guests = _int_field(data, "guests", MIN_GUESTS, MAX_GUESTS, errors)
    currency = _choice(data, "currency", tuple(CURRENCIES), "INR", errors)
    venue_type = _choice(data, "venue_type", VENUE_TYPES, "indoor", errors)
    vibe = _choice(data, "vibe", VIBES, "modern", errors)
    dietary = _multi(data, "dietary", DIETARY, errors)
    attendees = _multi(data, "attendees", ATTENDEES, errors)

    title = ""
    if data.get("title") is not None:
        if isinstance(data["title"], str):
            title = clean_text(data["title"], 80)
        else:
            errors["title"] = "Title must be text."

    interests: tuple[str, ...] = ()
    raw_interests = data.get("interests", [])
    if not isinstance(raw_interests, list) or not all(isinstance(x, str) for x in raw_interests):
        errors["interests"] = "Send a list of short phrases."
    else:
        items = [clean_text(x, 30) for x in raw_interests]
        items = [x for x in items if x]
        if len(items) > MAX_INTERESTS:
            errors["interests"] = f"Add at most {MAX_INTERESTS} interests."
        else:
            interests = tuple(dict.fromkeys(items))

    if errors:
        raise ValidationError(errors)
    return PlanRequest(event_type=event_type, event_date=event_date, budget=budget, guests=guests,
                       title=title, currency=currency, venue_type=venue_type, vibe=vibe,
                       dietary=dietary, attendees=attendees, interests=interests)


def parse_question(raw: object) -> str:
    """Validate the free-text question sent to the assistant."""
    if not isinstance(raw, str):
        raise ValidationError({"question": "Ask your question as text."})
    question = clean_text(raw, 500)
    if len(question) < 3:
        raise ValidationError({"question": "Type a question of at least 3 characters."})
    return question
