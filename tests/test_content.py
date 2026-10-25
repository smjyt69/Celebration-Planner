import copy
import json
import unittest
from typing import Any

from planner import data
from planner.data import CONTENT_DIR, ContentError, validate_content


def valid_content() -> dict[str, Any]:
    """A deep copy of the real content, so each test can break exactly one thing."""
    return copy.deepcopy({
        "weights": data.BUDGET_WEIGHTS, "min_per_guest": data.MIN_PER_GUEST,
        "timelines": data.TIMELINES, "vendors": data.VENDORS, "ideas": data.IDEAS,
    })


def check(content: dict[str, Any]) -> None:
    validate_content(content["weights"], content["min_per_guest"], content["timelines"],
                     content["vendors"], content["ideas"])


class ContentValidationTests(unittest.TestCase):
    def test_shipped_content_is_valid(self) -> None:
        check(valid_content())

    def test_weights_must_sum_to_100(self) -> None:
        content = valid_content()
        content["weights"]["wedding"]["venue"] += 1
        with self.assertRaisesRegex(ContentError, "sum to 101"):
            check(content)

    def test_required_budget_lines_are_enforced(self) -> None:
        content = valid_content()
        weights = content["weights"]["birthday"]
        weights["catering"] += weights.pop("contingency")
        with self.assertRaisesRegex(ContentError, "contingency"):
            check(content)

    def test_every_event_type_must_be_present_everywhere(self) -> None:
        for table in ("weights", "timelines", "vendors", "ideas"):
            content = valid_content()
            del content[table]["community"]
            with self.assertRaisesRegex(ContentError, "community"):
                check(content)

    def test_timeline_needs_an_event_day_task(self) -> None:
        content = valid_content()
        content["timelines"]["wedding"] = [s for s in content["timelines"]["wedding"] if s.days_before != 0]
        with self.assertRaisesRegex(ContentError, "event-day"):
            check(content)

    def test_vendor_needs_questions_and_contract_points(self) -> None:
        for key in ("ask", "contract"):
            content = valid_content()
            content["vendors"]["wedding"][0][key] = []
            with self.assertRaisesRegex(ContentError, key):
                check(content)

    def test_every_style_needs_ideas(self) -> None:
        content = valid_content()
        content["ideas"]["birthday"]["fun"] = []
        with self.assertRaisesRegex(ContentError, "fun"):
            check(content)

    def test_every_currency_needs_positive_minimums(self) -> None:
        content = valid_content()
        content["min_per_guest"]["USD"]["wedding"] = 0
        with self.assertRaisesRegex(ContentError, "USD/wedding"):
            check(content)
        content = valid_content()
        del content["min_per_guest"]["GBP"]
        with self.assertRaisesRegex(ContentError, "GBP"):
            check(content)


class ContentFilesTests(unittest.TestCase):
    def test_files_are_utf8_json_with_expected_top_level_keys(self) -> None:
        expected = {"budget.json": {"weights", "min_per_guest", "labels"},
                    "timelines.json": set(data.EVENT_TYPES),
                    "vendors.json": {"by_event", "extra"},
                    "ideas.json": {"by_style", "interests", "context"}}
        for name, keys in expected.items():
            content = json.loads((CONTENT_DIR / name).read_text(encoding="utf-8"))
            self.assertEqual(set(content), keys, name)

    def test_loaded_vendor_filters_are_tuples(self) -> None:
        home_hidden = [v for v in data.VENDORS["wedding"] if "skip_venue" in v]
        self.assertTrue(home_hidden)
        self.assertTrue(all(isinstance(v["skip_venue"], tuple) for v in home_hidden))
        self.assertTrue(all(isinstance(v["only_venue"], tuple) for v in data.EXTRA_VENDORS if "only_venue" in v))

    def test_timeline_rows_load_as_named_tuples(self) -> None:
        first = data.TIMELINES["wedding"][0]
        self.assertEqual(first.days_before, 270)
        self.assertIsInstance(first.critical, bool)


if __name__ == "__main__":
    unittest.main()
