"""Strict input validation. Everything from the client is untrusted until it passes through here.

Each field is checked by a small parser that either returns a clean value or raises `FieldError`.
`parse_plan_request` runs the parsers through a reader that collects every failure, so the UI can
highlight all invalid fields at once instead of one per submit.
"""
from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, TypeVar

from .data import ATTENDEES, CURRENCIES, DIETARY, EVENT_TYPES, VENUE_TYPES, VIBES

MAX_HORIZON_DAYS = 5 * 366
MIN_BUDGET, MAX_BUDGET = 1_000, 100_000_000
MIN_GUESTS, MAX_GUESTS = 1, 5_000
MAX_INTERESTS = 5
MAX_TITLE_LENGTH = 80
MAX_INTEREST_LENGTH = 30
MAX_QUESTION_LENGTH = 500
MIN_QUESTION_LENGTH = 3

_CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f]")
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

T = TypeVar("T")
Parser = Callable[[Any], T]


class FieldError(ValueError):
    """One field failed validation. The message is safe to show to the user."""


class ValidationError(Exception):
    """Carries a field -> message mapping so the UI can annotate each input."""

    def __init__(self, fields: dict[str, str]) -> None:
        super().__init__("Invalid input")
        self.fields = fields


@dataclass(frozen=True)
class PlanRequest:
    """A fully validated request for a plan."""

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


# ---------------------------------------------------------------- field parsers
def int_between(lo: int, hi: int) -> Parser[int]:
    """Whole number within [lo, hi]. Integral floats such as 5000.0 are accepted; booleans are not."""
    def parse(raw: Any) -> int:
        value = int(raw) if isinstance(raw, float) and raw.is_integer() else raw
        if isinstance(value, bool) or not isinstance(value, int):
            raise FieldError("Enter a whole number.")
        if not lo <= value <= hi:
            raise FieldError(f"Enter a number between {lo:,} and {hi:,}.")
        return value
    return parse


def one_of(choices: Sequence[str]) -> Parser[str]:
    """Exactly one value from a fixed list."""
    def parse(raw: Any) -> str:
        if not isinstance(raw, str) or raw not in choices:
            raise FieldError("Choose one of: " + ", ".join(choices) + ".")
        return raw
    return parse


def many_of(choices: Sequence[str]) -> Parser[tuple[str, ...]]:
    """Zero or more values from a fixed list; spelling variants and duplicates are normalised."""
    def parse(raw: Any) -> tuple[str, ...]:
        if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
            raise FieldError("Send a list of options.")
        cleaned = [item.strip().lower().replace("-", "_").replace(" ", "_") for item in raw]
        cleaned = [item for item in cleaned if item and item != "none"]
        if any(item not in choices for item in cleaned):
            raise FieldError("Unknown option(s). Allowed: " + ", ".join(choices) + ".")
        return tuple(dict.fromkeys(cleaned))  # de-duplicate, keep order
    return parse


def iso_date(today: date) -> Parser[date]:
    """A real YYYY-MM-DD date from today up to MAX_HORIZON_DAYS ahead."""
    def parse(raw: Any) -> date:
        if not isinstance(raw, str) or not _ISO_DATE.match(raw):
            raise FieldError("Use the format YYYY-MM-DD.")
        try:
            value = date.fromisoformat(raw)
        except ValueError:
            raise FieldError("That is not a real calendar date.") from None
        if value < today:
            raise FieldError("Pick today or a future date.")
        if value > today + timedelta(days=MAX_HORIZON_DAYS):
            raise FieldError("Pick a date within the next five years.")
        return value
    return parse


def optional_text(max_len: int, error: str) -> Parser[str]:
    """Free text that may be missing (becomes ''); control characters are removed."""
    def parse(raw: Any) -> str:
        if raw is None:
            return ""
        if not isinstance(raw, str):
            raise FieldError(error)
        return clean_text(raw, max_len)
    return parse


def phrases(max_items: int, max_len: int) -> Parser[tuple[str, ...]]:
    """A short list of free-text phrases, cleaned, de-duplicated and capped in count."""
    def parse(raw: Any) -> tuple[str, ...]:
        if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
            raise FieldError("Send a list of short phrases.")
        items = [clean_text(item, max_len) for item in raw]
        items = [item for item in items if item]
        if len(items) > max_items:
            raise FieldError(f"Add at most {max_items} interests.")
        return tuple(dict.fromkeys(items))
    return parse


# ---------------------------------------------------------------- orchestration
class _FieldReader:
    """Reads fields from a payload, collecting every failure rather than stopping at the first."""

    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload
        self.errors: dict[str, str] = {}

    def read(self, name: str, parse: Parser[T], *, fallback: T, default: Any = None) -> T:
        """Parse one field. On failure, record the message and return `fallback` (never used if errors exist)."""
        try:
            return parse(self._payload.get(name, default))
        except FieldError as err:
            self.errors[name] = str(err)
            return fallback

    def raise_if_errors(self) -> None:
        if self.errors:
            raise ValidationError(self.errors)


def parse_plan_request(data: object, today: date) -> PlanRequest:
    """Validate a raw JSON payload and return an immutable PlanRequest."""
    if not isinstance(data, dict):
        raise ValidationError({"body": "Send a JSON object."})
    reader = _FieldReader(data)
    request = PlanRequest(
        event_type=reader.read("event_type", one_of(EVENT_TYPES), fallback=""),
        event_date=reader.read("event_date", iso_date(today), fallback=today),
        budget=reader.read("budget", int_between(MIN_BUDGET, MAX_BUDGET), fallback=0),
        guests=reader.read("guests", int_between(MIN_GUESTS, MAX_GUESTS), fallback=0),
        title=reader.read("title", optional_text(MAX_TITLE_LENGTH, "Title must be text."), fallback=""),
        currency=reader.read("currency", one_of(tuple(CURRENCIES)), default="INR", fallback="INR"),
        venue_type=reader.read("venue_type", one_of(VENUE_TYPES), default="indoor", fallback="indoor"),
        vibe=reader.read("vibe", one_of(VIBES), default="modern", fallback="modern"),
        dietary=reader.read("dietary", many_of(DIETARY), default=[], fallback=()),
        attendees=reader.read("attendees", many_of(ATTENDEES), default=[], fallback=()),
        interests=reader.read("interests", phrases(MAX_INTERESTS, MAX_INTEREST_LENGTH), default=[], fallback=()),
    )
    reader.raise_if_errors()
    return request


def parse_question(raw: object) -> str:
    """Validate the free-text question sent to the assistant."""
    if not isinstance(raw, str):
        raise ValidationError({"question": "Ask your question as text."})
    question = clean_text(raw, MAX_QUESTION_LENGTH)
    if len(question) < MIN_QUESTION_LENGTH:
        raise ValidationError({"question": f"Type a question of at least {MIN_QUESTION_LENGTH} characters."})
    return question
