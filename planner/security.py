"""Security headers and the per-client request throttle."""
from __future__ import annotations

from flask import Flask, Response, jsonify, request

from .config import Settings
from .ratelimit import RateLimiter

CSP = ("default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
       "connect-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'")

AI_PATHS = frozenset({"/api/ideas", "/api/ask"})


def register_security(app: Flask, settings: Settings) -> None:
    """Attach the throttle (before each request) and security headers (after each response)."""
    limiters = {
        "plan": RateLimiter(settings.rate_limit_plan, settings.rate_window_seconds),
        "ai": RateLimiter(settings.rate_limit_ai, settings.rate_window_seconds),
    }

    @app.before_request
    def throttle() -> Response | None:
        if not request.path.startswith("/api/"):
            return None
        bucket = "ai" if request.path in AI_PATHS else "plan"
        if limiters[bucket].allow(request.remote_addr or "unknown"):
            return None
        response = jsonify(error="Too many requests. Please wait a moment.")
        response.status_code = 429
        response.headers["Retry-After"] = str(settings.rate_window_seconds)
        return response

    @app.after_request
    def add_headers(response: Response) -> Response:
        response.headers["Content-Security-Policy"] = CSP
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response
