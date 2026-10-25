import unittest
from datetime import timedelta

from planner.validation import (FieldError, ValidationError, int_between, iso_date, many_of, one_of,
                                optional_text, parse_plan_request, parse_question, phrases)
from tests.helpers import TODAY, payload


def errors_for(**overrides):
    try:
        parse_plan_request(payload(**overrides), TODAY)
    except ValidationError as err:
        return err.fields
    return {}


class PlanRequestTests(unittest.TestCase):
    def test_valid_request_with_defaults(self):
        req = parse_plan_request(payload(), TODAY)
        self.assertEqual((req.currency, req.venue_type, req.vibe), ("INR", "indoor", "modern"))
        self.assertEqual((req.dietary, req.attendees, req.interests), ((), (), ()))

    def test_missing_required_fields_are_all_reported_together(self):
        with self.assertRaises(ValidationError) as ctx:
            parse_plan_request({}, TODAY)
        self.assertEqual(set(ctx.exception.fields), {"event_type", "event_date", "budget", "guests"})

    def test_non_object_body_rejected(self):
        for bad in (None, [], "text", 5):
            with self.assertRaises(ValidationError):
                parse_plan_request(bad, TODAY)

    def test_event_type_must_be_known(self):
        self.assertIn("event_type", errors_for(event_type="funeral"))
        self.assertIn("event_type", errors_for(event_type=7))

    def test_date_rules(self):
        self.assertEqual(errors_for(event_date=TODAY.isoformat()), {})
        self.assertIn("event_date", errors_for(event_date=(TODAY - timedelta(days=1)).isoformat()))
        self.assertIn("event_date", errors_for(event_date=(TODAY + timedelta(days=366 * 6)).isoformat()))
        for bad in ("2026-02-30", "20261201", "2026-W49-1", "12/01/2026", "", None, 20261201):
            self.assertIn("event_date", errors_for(event_date=bad), bad)

    def test_number_rules(self):
        self.assertEqual(errors_for(budget=1_000.0), {})            # integral float is fine
        for bad in (999, 100_000_001, 1234.5, "50000", True, None):
            self.assertIn("budget", errors_for(budget=bad), bad)
        for bad in (0, 5_001, -3, "40", False):
            self.assertIn("guests", errors_for(guests=bad), bad)

    def test_choice_fields(self):
        self.assertIn("currency", errors_for(currency="JPY"))
        self.assertIn("venue_type", errors_for(venue_type="rooftop"))
        self.assertIn("vibe", errors_for(vibe=["fun"]))

    def test_multi_select_normalised_and_deduplicated(self):
        req = parse_plan_request(payload(dietary=["Gluten-Free", "vegan", "vegan", "none"], attendees=["KIDS"]), TODAY)
        self.assertEqual(req.dietary, ("gluten_free", "vegan"))
        self.assertEqual(req.attendees, ("kids",))

    def test_multi_select_rejects_unknown_or_wrong_type(self):
        self.assertIn("dietary", errors_for(dietary=["pizza"]))
        self.assertIn("dietary", errors_for(dietary="vegan"))
        self.assertIn("attendees", errors_for(attendees=[1]))

    def test_title_is_cleaned_and_truncated(self):
        req = parse_plan_request(payload(title="  Ravi\x00's \x07party\n" + "x" * 200), TODAY)
        self.assertNotIn("\x00", req.title)
        self.assertNotIn("\n", req.title)
        self.assertEqual(len(req.title), 80)
        self.assertIn("title", errors_for(title=123))

    def test_interests_limits(self):
        req = parse_plan_request(payload(interests=["  music ", "", "music", "x" * 100]), TODAY)
        self.assertEqual(req.interests, ("music", "x" * 30))
        self.assertIn("interests", errors_for(interests=["a", "b", "c", "d", "e", "f"]))
        self.assertIn("interests", errors_for(interests="music"))

    def test_unicode_text_is_kept(self):
        req = parse_plan_request(payload(title="ಹುಟ್ಟುಹಬ್ಬ 🎂", interests=["ಸಂಗೀತ"]), TODAY)
        self.assertEqual(req.title, "ಹುಟ್ಟುಹಬ್ಬ 🎂")
        self.assertEqual(req.interests, ("ಸಂಗೀತ",))


class QuestionTests(unittest.TestCase):
    def test_valid_question_is_trimmed_and_capped(self):
        self.assertEqual(parse_question("  What first?  "), "What first?")
        self.assertEqual(len(parse_question("q" * 900)), 500)

    def test_invalid_questions(self):
        for bad in (None, 42, "", "  ", "hi", ["a"]):
            with self.assertRaises(ValidationError):
                parse_question(bad)


class FieldParserTests(unittest.TestCase):
    def test_int_between(self) -> None:
        parse = int_between(1, 10)
        self.assertEqual((parse(1), parse(10), parse(5.0)), (1, 10, 5))
        for bad in (0, 11, 2.5, "3", None, True):
            with self.assertRaises(FieldError, msg=repr(bad)):
                parse(bad)

    def test_one_of(self) -> None:
        parse = one_of(("a", "b"))
        self.assertEqual(parse("a"), "a")
        for bad in ("c", "", None, ["a"], 1):
            with self.assertRaises(FieldError, msg=repr(bad)):
                parse(bad)

    def test_many_of_normalises_and_deduplicates(self) -> None:
        parse = many_of(("gluten_free", "vegan"))
        self.assertEqual(parse(["Gluten-Free", "VEGAN", "vegan", "none", ""]), ("gluten_free", "vegan"))
        self.assertEqual(parse([]), ())
        for bad in (["pizza"], "vegan", [1], None):
            with self.assertRaises(FieldError, msg=repr(bad)):
                parse(bad)

    def test_iso_date_boundaries(self) -> None:
        parse = iso_date(TODAY)
        self.assertEqual(parse(TODAY.isoformat()), TODAY)
        last_day = TODAY + timedelta(days=5 * 366)
        self.assertEqual(parse(last_day.isoformat()), last_day)
        for bad in ((TODAY - timedelta(days=1)).isoformat(), (last_day + timedelta(days=1)).isoformat(),
                    "2026-02-30", "26-1-1", None, 20261201):
            with self.assertRaises(FieldError, msg=repr(bad)):
                parse(bad)

    def test_optional_text(self) -> None:
        parse = optional_text(5, "must be text")
        self.assertEqual((parse(None), parse("  ab\x00cdefg  ")), ("", "abcde"))
        with self.assertRaisesRegex(FieldError, "must be text"):
            parse(12)

    def test_phrases(self) -> None:
        parse = phrases(max_items=3, max_len=4)
        # blanks are dropped, long phrases truncated, then duplicates collapsed
        self.assertEqual(parse([" abcdef ", "", "abcd", "xy"]), ("abcd", "xy"))
        with self.assertRaises(FieldError):          # the limit applies to non-blank entries
            parse(["a", "b", "c", "d"])
        with self.assertRaises(FieldError):
            parse("a")

    def test_every_invalid_field_is_reported_in_one_pass(self) -> None:
        with self.assertRaises(ValidationError) as ctx:
            parse_plan_request({"event_type": "x", "event_date": "nope", "budget": 1, "guests": 0,
                                "currency": "JPY", "dietary": ["pizza"], "title": 5, "interests": "a"}, TODAY)
        self.assertEqual(set(ctx.exception.fields),
                         {"event_type", "event_date", "budget", "guests", "currency", "dietary", "title", "interests"})


if __name__ == "__main__":
    unittest.main()
