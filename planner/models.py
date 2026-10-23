"""Typed shapes for the plan the engine produces and the HTTP layer returns as JSON."""
from __future__ import annotations

from typing import Literal, NamedTuple, TypedDict

Level = Literal["info", "warning"]


class TimelineTemplate(NamedTuple):
    """One task in an event type's ideal timeline."""

    days_before: int
    title: str
    category: str
    critical: bool


class VendorTemplate(TypedDict, total=False):
    """Static vendor guidance. Optional keys decide when a vendor applies."""

    category: str
    vendor: str
    ask: list[str]
    contract: list[str]
    skip_venue: tuple[str, ...]   # hide for these venue types
    only_venue: tuple[str, ...]   # show only for these venue types
    only_attendee: str            # show only when this attendee group is present


class BudgetLine(TypedDict):
    category: str
    label: str
    percent: int
    amount: int


class Budget(TypedDict):
    lines: list[BudgetLine]
    per_guest: int
    min_per_guest: int
    tight: bool
    guests_supported: int


class Task(TypedDict):
    id: str
    title: str
    category: str
    critical: bool
    days_before: int
    due_date: str


class Timeline(TypedDict):
    tasks: list[Task]
    rushed: bool
    heavy: bool
    ideal_lead_days: int
    days_left: int
    skipped: list[str]


class Vendor(TypedDict):
    category: str
    label: str
    vendor: str
    ask: list[str]
    contract: list[str]
    budget: int | None


class Note(TypedDict):
    level: Level
    text: str


class Summary(TypedDict):
    event_type: str
    title: str
    event_date: str
    days_left: int
    guests: int
    budget: int
    currency: str
    symbol: str
    venue_type: str
    vibe: str
    dietary: list[str]
    attendees: list[str]
    interests: list[str]


class Plan(TypedDict):
    summary: Summary
    notes: list[Note]
    budget: Budget
    timeline: Timeline
    vendors: list[Vendor]
    ideas: list[str]
