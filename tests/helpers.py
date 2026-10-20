"""Shared test helpers."""
from datetime import date

from planner.validation import parse_plan_request

TODAY = date(2026, 10, 20)


def make_request(**overrides):
    payload = {"event_type": "wedding", "event_date": "2027-07-15", "budget": 1_000_000, "guests": 200}
    payload.update(overrides)
    return parse_plan_request(payload, TODAY)


def payload(**overrides):
    base = {"event_type": "birthday", "event_date": "2026-12-01", "budget": 50_000, "guests": 40}
    base.update(overrides)
    return base
