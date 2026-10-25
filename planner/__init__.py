"""Celebration Planner: a Flask app with a deterministic planning engine and an optional AI layer."""
from __future__ import annotations

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


def create_app(settings: Settings | None = None) -> Flask:
    """Build the application. With no argument, settings are read from the environment."""
    settings = settings or Settings.from_env()

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
