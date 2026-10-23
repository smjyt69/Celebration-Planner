"""Runtime configuration, read once from the environment."""
from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import date

from .llm import Transport

DEFAULT_MODEL = "claude-sonnet-5-5"


@dataclass(frozen=True)
class Settings:
    """Application settings. Tests override fields instead of patching the environment."""

    anthropic_api_key: str = ""
    anthropic_model: str = DEFAULT_MODEL
    trust_proxy: bool = False
    max_body_bytes: int = 16 * 1024
    rate_limit_plan: int = 60       # requests per window, per client
    rate_limit_ai: int = 10         # AI endpoints cost money, so they get a tighter budget
    rate_window_seconds: int = 60
    today: Callable[[], date] = field(default=date.today)
    llm_transport: Transport | None = None

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        source = os.environ if env is None else env
        return cls(
            anthropic_api_key=source.get("ANTHROPIC_API_KEY", ""),
            anthropic_model=source.get("ANTHROPIC_MODEL", DEFAULT_MODEL),
            trust_proxy=source.get("TRUST_PROXY") == "1",
        )
