import os
import unittest
from datetime import date
from unittest import mock

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


class AppSettingsTests(unittest.TestCase):
    def test_a_misspelled_setting_is_an_error_not_silently_ignored(self) -> None:
        with self.assertRaises(TypeError):
            Settings(rate_limt_plan=5)  # type: ignore[call-arg]

    def test_settings_reach_the_app(self) -> None:
        app = create_app(Settings(today=lambda: date(2030, 1, 1), rate_limit_plan=7))
        self.assertEqual(app.extensions["settings"].rate_limit_plan, 7)
        self.assertEqual(app.extensions["settings"].today(), date(2030, 1, 1))

    def test_environment_is_used_when_no_settings_are_given(self) -> None:
        with mock.patch.dict(os.environ, {"TRUST_PROXY": "1", "ANTHROPIC_API_KEY": ""}):
            app = create_app()
        self.assertTrue(app.extensions["settings"].trust_proxy)
        self.assertFalse(app.extensions["llm"].enabled)

    def test_proxy_headers_are_ignored_unless_trusted(self) -> None:
        body = {"event_type": "birthday", "event_date": "2030-01-01", "budget": 20_000, "guests": 30}
        for trust, expected in ((False, [200, 429, 429]), (True, [200, 200, 200])):
            client = create_app(Settings(rate_limit_plan=1, trust_proxy=trust)).test_client()
            codes = [client.post("/api/plan", json=body, headers={"X-Forwarded-For": f"9.9.9.{i}"}).status_code
                     for i in range(3)]
            self.assertEqual(codes, expected, f"trust_proxy={trust}")


if __name__ == "__main__":
    unittest.main()
