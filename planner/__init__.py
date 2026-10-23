"""Celebration Planner: a Flask app with a deterministic planning engine and an optional AI layer."""
from __future__ import annotations

from dataclasses import replace
from typing import Any

from flask import Flask, Response, jsonify
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

from .config import Settings
from .llm import LLMClient
from .ratelimit import RateLimiter
from .routes import bp
from .security import register_security
from .validation import ValidationError

__all__ = ["RateLimiter", "Settings", "create_app"]


def create_app(overrides: dict[str, Any] | None = None) -> Flask:
    """Build the application.

    `overrides` replaces fields of `Settings` using the upper-case names the tests and
    older callers use (for example `TODAY`, `ANTHROPIC_API_KEY`, `RATE_LIMIT_PLAN`).
    """
    settings = _apply_overrides(Settings.from_env(), overrides or {})

    app = Flask(__name__, static_folder=None)
    app.config["MAX_CONTENT_LENGTH"] = settings.max_body_bytes
    app.extensions["settings"] = settings
    app.extensions["llm"] = LLMClient(settings.anthropic_api_key, settings.anthropic_model,
                                      settings.llm_transport)
    if settings.trust_proxy:  # only behind a reverse proxy you control (e.g. Render)
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1)  # type: ignore[method-assign]

    register_security(app, settings)
    _register_error_handlers(app)
    app.register_blueprint(bp)
    return app


_OVERRIDE_FIELDS = {
    "TODAY": "today",
    "ANTHROPIC_API_KEY": "anthropic_api_key",
    "ANTHROPIC_MODEL": "anthropic_model",
    "LLM_TRANSPORT": "llm_transport",
    "RATE_LIMIT_PLAN": "rate_limit_plan",
    "RATE_LIMIT_AI": "rate_limit_ai",
    "RATE_WINDOW": "rate_window_seconds",
    "MAX_CONTENT_LENGTH": "max_body_bytes",
    "TRUST_PROXY": "trust_proxy",
}


def _apply_overrides(settings: Settings, overrides: dict[str, Any]) -> Settings:
    unknown = set(overrides) - set(_OVERRIDE_FIELDS)
    if unknown:
        raise KeyError(f"Unknown setting(s): {', '.join(sorted(unknown))}")
    return replace(settings, **{_OVERRIDE_FIELDS[k]: v for k, v in overrides.items()})


def _register_error_handlers(app: Flask) -> None:
    @app.errorhandler(ValidationError)
    def on_validation(err: ValidationError) -> tuple[Response, int]:
        return jsonify(error="Please fix the highlighted fields.", fields=err.fields), 400

    @app.errorhandler(Exception)
    def on_error(err: Exception) -> tuple[Response, int]:
        if isinstance(err, HTTPException):
            return jsonify(error=err.name), err.code or 500
        app.logger.exception("Unhandled error")  # details stay in the logs, never in the response
        return jsonify(error="Something went wrong on our side."), 500
