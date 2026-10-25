import itertools
import unittest
from datetime import date, timedelta

from planner.data import BUDGET_WEIGHTS, EVENT_TYPES, TIMELINES, VENUE_TYPES
from planner.engine import (
    adjust_weights,
    answer_offline,
    build_budget,
    build_ideas,
    build_plan,
    build_timeline,
    build_vendors,
    season_notes,
)
from tests.helpers import TODAY, make_request


def shares(budget):
    """Map budget category -> percentage share."""
    return {line["category"]: line["percent"] for line in budget["lines"]}


class BudgetTests(unittest.TestCase):
    def test_templates_sum_to_100_and_have_shared_keys(self):
        for event, weights in BUDGET_WEIGHTS.items():
            self.assertEqual(sum(weights.values()), 100, event)
            for key in ("venue", "catering", "decor", "entertainment", "contingency"):
                self.assertIn(key, weights, event)

    def test_adjusted_weights_always_sum_to_100_and_respect_floor(self):
        for event, venue, tight in itertools.product(EVENT_TYPES, VENUE_TYPES, (True, False)):
            w = adjust_weights(event, venue, tight)
            self.assertEqual(sum(w.values()), 100, (event, venue, tight))
            self.assertTrue(all(v >= 2 for v in w.values()), (event, venue, tight))

    def test_amounts_sum_exactly_to_budget(self):
        for event, budget, guests in itertools.product(EVENT_TYPES, (1_000, 12_345, 99_999, 1_000_003), (1, 37, 400)):
            req = make_request(event_type=event, budget=budget, guests=guests)
            lines = build_budget(req)["lines"]
            self.assertEqual(sum(line["amount"] for line in lines), budget)
            self.assertEqual(lines[-1]["category"], "contingency")

    def test_home_venue_moves_money_from_venue_to_food_and_decor(self):
        indoor = shares(build_budget(make_request(venue_type="indoor")))
        home = shares(build_budget(make_request(venue_type="home")))
        self.assertEqual(home["venue"], 5)
        self.assertGreater(home["catering"], indoor["catering"])
        self.assertGreater(home["decor"], indoor["decor"])

    def test_outdoor_adds_weather_contingency(self):
        indoor = shares(build_budget(make_request(venue_type="indoor")))
        outdoor = shares(build_budget(make_request(venue_type="outdoor")))
        self.assertEqual(outdoor["contingency"], indoor["contingency"] + 3)

    def test_tight_budget_is_flagged_and_prioritises_catering(self):
        tight = build_budget(make_request(budget=50_000, guests=200))   # 250 per guest vs 800 minimum
        roomy = build_budget(make_request(budget=2_000_000, guests=200))
        self.assertTrue(tight["tight"])
        self.assertFalse(roomy["tight"])
        self.assertGreater(shares(tight)["catering"], shares(roomy)["catering"])
        self.assertEqual(tight["guests_supported"], 62)

    def test_currency_changes_the_affordability_threshold(self):
        # 100 per guest is fine for a USD birthday but not for a wedding in INR.
        birthday_usd = make_request(event_type="birthday", currency="USD", budget=10_000, guests=100)
        wedding_inr = make_request(event_type="wedding", currency="INR", budget=10_000, guests=100)
        self.assertFalse(build_budget(birthday_usd)["tight"])
        self.assertTrue(build_budget(wedding_inr)["tight"])


class TimelineTests(unittest.TestCase):
    def test_plenty_of_time_keeps_ideal_offsets(self):
        req = make_request(event_date=(TODAY + timedelta(days=400)).isoformat())
        tl = build_timeline(req, TODAY)
        self.assertFalse(tl["rushed"])
        self.assertEqual(len(tl["tasks"]), len(TIMELINES["wedding"]))
        self.assertEqual(max(t["days_before"] for t in tl["tasks"]), 270)

    def test_short_notice_compresses_and_never_schedules_in_the_past(self):
        req = make_request(event_date=(TODAY + timedelta(days=100)).isoformat())
        tl = build_timeline(req, TODAY)
        self.assertTrue(tl["rushed"])
        self.assertFalse(tl["heavy"])
        for task in tl["tasks"]:
            self.assertGreaterEqual(date.fromisoformat(task["due_date"]), TODAY)
            self.assertLessEqual(date.fromisoformat(task["due_date"]), req.event_date)

    def test_compressed_schedule_keeps_every_task_while_two_weeks_remain(self):
        tl = build_timeline(make_request(event_date=(TODAY + timedelta(days=14)).isoformat()), TODAY)
        self.assertFalse(tl["heavy"])
        self.assertEqual(len(tl["tasks"]), len(TIMELINES["wedding"]))
        self.assertEqual(tl["skipped"], [])

    def test_under_two_weeks_keeps_only_critical_tasks(self):
        tl = build_timeline(make_request(event_date=(TODAY + timedelta(days=13)).isoformat()), TODAY)
        self.assertTrue(tl["heavy"])
        self.assertTrue(all(t["critical"] for t in tl["tasks"]))
        self.assertTrue(tl["skipped"])
        self.assertEqual(len(tl["tasks"]) + len(tl["skipped"]), len(TIMELINES["wedding"]))

    def test_event_today_schedules_everything_today(self):
        tl = build_timeline(make_request(event_date=TODAY.isoformat()), TODAY)
        self.assertTrue(all(t["due_date"] == TODAY.isoformat() for t in tl["tasks"]))

    def test_tasks_are_sorted_by_due_date(self):
        tl = build_timeline(make_request(), TODAY)
        dates = [t["due_date"] for t in tl["tasks"]]
        self.assertEqual(dates, sorted(dates))

    def test_every_event_type_has_a_day_zero_task(self):
        for event in EVENT_TYPES:
            self.assertTrue(any(d == 0 for d, *_ in TIMELINES[event]), event)


class VendorTests(unittest.TestCase):
    def categories(self, **kw):
        req = make_request(**kw)
        return [v["category"] for v in build_vendors(req, build_budget(req))]

    def test_home_events_skip_venue_vendor(self):
        self.assertNotIn("venue", self.categories(venue_type="home"))
        self.assertIn("venue", self.categories(venue_type="indoor"))

    def test_outdoor_adds_tent_and_power(self):
        cats = self.categories(venue_type="outdoor")
        self.assertIn("tent", cats)
        self.assertIn("power", cats)
        self.assertNotIn("tent", self.categories(venue_type="indoor"))

    def test_attendees_add_accessibility_and_kids_safety(self):
        self.assertIn("accessibility", self.categories(attendees=["seniors"]))
        self.assertIn("kids_safety", self.categories(attendees=["kids"]))
        self.assertNotIn("accessibility", self.categories())

    def test_dietary_needs_reach_the_caterer_questions(self):
        req = make_request(dietary=["jain", "gluten_free"])
        catering = next(v for v in build_vendors(req, build_budget(req)) if v["category"] == "catering")
        self.assertTrue(any("jain" in q and "gluten-free" in q for q in catering["ask"]))

    def test_vendor_budget_matches_budget_line(self):
        req = make_request()
        budget = build_budget(req)
        venue = next(v for v in build_vendors(req, budget) if v["category"] == "venue")
        venue_line = next(line for line in budget["lines"] if line["category"] == "venue")
        self.assertEqual(venue["budget"], venue_line["amount"])


class IdeasAndNotesTests(unittest.TestCase):
    def test_ideas_follow_vibe(self):
        self.assertNotEqual(build_ideas(make_request(vibe="minimal"))[:3], build_ideas(make_request(vibe="fun"))[:3])

    def test_known_and_unknown_interests_are_used(self):
        ideas = build_ideas(make_request(interests=["music", "Pottery"]))
        self.assertTrue(any("playlist" in i for i in ideas))
        self.assertTrue(any("'Pottery'" in i for i in ideas))

    def test_ideas_are_unique_and_capped(self):
        ideas = build_ideas(make_request(attendees=["kids", "seniors"], dietary=["vegan"], venue_type="outdoor",
                                         interests=["music", "food", "art", "tech", "dance"]))
        self.assertEqual(len(ideas), len(set(ideas)))
        self.assertLessEqual(len(ideas), 10)

    def test_season_notes(self):
        monsoon = season_notes(make_request(venue_type="outdoor", event_date="2027-07-10"))
        self.assertTrue(any("Monsoon" in n["text"] for n in monsoon))
        peak = season_notes(make_request(event_date="2027-12-10"))
        self.assertTrue(any("Peak wedding" in n["text"] for n in peak))
        self.assertEqual(season_notes(make_request(event_type="birthday", event_date="2027-03-10")), [])


class PlanTests(unittest.TestCase):
    def test_plan_contains_all_sections_and_context(self):
        plan = build_plan(make_request(title="Asha & Ravi", guests=300, budget=100_000), TODAY)
        self.assertEqual(set(plan), {"summary", "notes", "budget", "timeline", "vendors", "ideas"})
        self.assertEqual(plan["summary"]["title"], "Asha & Ravi")
        self.assertTrue(any("per guest" in n["text"] for n in plan["notes"]))

    def test_large_home_gathering_is_warned(self):
        plan = build_plan(make_request(venue_type="home", guests=150), TODAY)
        self.assertTrue(any("home" in n["text"] for n in plan["notes"]))

    def test_default_title_when_none_given(self):
        self.assertEqual(build_plan(make_request(), TODAY)["summary"]["title"], "Your wedding")


class OfflineAnswerTests(unittest.TestCase):
    def setUp(self):
        self.plan = build_plan(make_request(), TODAY)

    def test_routes_by_topic(self):
        self.assertIn("per guest", answer_offline("How is my budget split?", self.plan))
        self.assertIn("Start with", answer_offline("What should I do first?", self.plan))
        self.assertIn("Vendors to line up", answer_offline("Which vendors do I need to hire?", self.plan))
        self.assertIn("Ideas to start with", answer_offline("Any decor ideas?", self.plan))
        self.assertIn("guests", answer_offline("How many people can I invite?", self.plan))

    def test_unknown_question_gets_helpful_fallback(self):
        self.assertIn("I can answer questions about", answer_offline("what's the weather like?", self.plan))


if __name__ == "__main__":
    unittest.main()
