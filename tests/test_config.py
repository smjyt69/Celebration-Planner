import unittest
from datetime import date

from planner import create_app
from planner.config import DEFAULT_MODEL, Settings


class SettingsTests(unittest.TestCase):
    def test_defaults_when_environment_is_empty(self) -> None:
        settings = Settings.from_env({})
        self.assertEqual(settings.anthropic_api_key, "")
        self.assertEqual(settings.anthropic_model, DEFAULT_MODEL)
        self.assertFalse(settings.trust_proxy)

    def test_values_are_read_from_the_environment(self) -> None:
        settings = Settings.from_env({"ANTHROPIC_API_KEY": "k", "ANTHROPIC_MODEL": "m", "TRUST_PROXY": "1"})
        self.assertEqual((settings.anthropic_api_key, settings.anthropic_model, settings.trust_proxy), ("k", "m", True))

    def test_trust_proxy_only_for_exact_one(self) -> None:
        for value in ("0", "true", "yes", ""):
            self.assertFalse(Settings.from_env({"TRUST_PROXY": value}).trust_proxy, value)

    def test_settings_are_immutable(self) -> None:
        with self.assertRaises(AttributeError):
            Settings().rate_limit_ai = 1_000  # type: ignore[misc]


class AppOverrideTests(unittest.TestCase):
    def test_unknown_override_is_rejected_instead_of_ignored(self) -> None:
        with self.assertRaises(KeyError):
            create_app({"RATE_LIMT_PLAN": 5})   # typo must not silently disable a limit

    def test_overrides_reach_the_app(self) -> None:
        app = create_app({"TODAY": lambda: date(2030, 1, 1), "RATE_LIMIT_PLAN": 7})
        self.assertEqual(app.extensions["settings"].rate_limit_plan, 7)
        self.assertEqual(app.extensions["settings"].today(), date(2030, 1, 1))

    def test_proxy_headers_are_ignored_unless_trusted(self) -> None:
        body = {"event_type": "birthday", "event_date": "2030-01-01", "budget": 20_000, "guests": 30}
        for trust, expected in ((False, [200, 429, 429]), (True, [200, 200, 200])):
            client = create_app({"RATE_LIMIT_PLAN": 1, "TRUST_PROXY": trust}).test_client()
            codes = [client.post("/api/plan", json=body, headers={"X-Forwarded-For": f"9.9.9.{i}"}).status_code
                     for i in range(3)]
            self.assertEqual(codes, expected, f"trust_proxy={trust}")


if __name__ == "__main__":
    unittest.main()
