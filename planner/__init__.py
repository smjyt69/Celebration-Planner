"""Flask application factory: HTTP layer, validation hooks, rate limiting and security headers."""
from __future__ import annotations

import os
import threading
import time
from collections import defaultdict, deque
from datetime import date
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from werkzeug.exceptions import HTTPException, UnsupportedMediaType

from .engine import answer_offline, build_plan
from .llm import LLMClient, compact_context
from .validation import ValidationError, parse_plan_request, parse_question

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

CSP = ("default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
       "connect-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'")


class RateLimiter:
    """Sliding-window limiter, per client key. In-memory: fine for one process (see README)."""

    def __init__(self, limit: int, window: float, clock=time.monotonic, max_keys: int = 10_000):
        self.limit, self.window, self._clock, self._max_keys = limit, window, clock, max_keys
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = self._clock()
        with self._lock:
            if key not in self._hits and len(self._hits) >= self._max_keys:  # bound memory under many distinct clients
                for k in [k for k, q in self._hits.items() if not q or now - q[-1] > self.window]:
                    del self._hits[k]
            q = self._hits[key]
            while q and now - q[0] > self.window:
                q.popleft()
            if len(q) >= self.limit:
                return False
            q.append(now)
            return True


def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__, static_folder=None)
    app.config.update(
        MAX_CONTENT_LENGTH=16 * 1024,
        TODAY=date.today,
        LLM_TRANSPORT=None,
        ANTHROPIC_API_KEY=os.environ.get("ANTHROPIC_API_KEY", ""),
        ANTHROPIC_MODEL=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5-5"),
        RATE_LIMIT_PLAN=60, RATE_LIMIT_AI=10, RATE_WINDOW=60,
    )
    if config:
        app.config.update(config)
    if os.environ.get("TRUST_PROXY") == "1":  # only enable behind a reverse proxy you control
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1)

    llm = LLMClient(app.config["ANTHROPIC_API_KEY"], app.config["ANTHROPIC_MODEL"], app.config["LLM_TRANSPORT"])
    app.extensions["llm"] = llm
    limiters = {"plan": RateLimiter(app.config["RATE_LIMIT_PLAN"], app.config["RATE_WINDOW"]),
                "ai": RateLimiter(app.config["RATE_LIMIT_AI"], app.config["RATE_WINDOW"])}

    def today() -> date:
        return app.config["TODAY"]()

    def json_body() -> dict:
        if not request.is_json:
            raise UnsupportedMediaType("Send Content-Type: application/json.")
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            raise ValidationError({"body": "Send a valid JSON object."})
        return data

    # ---- cross-cutting
    @app.before_request
    def throttle():
        if request.path.startswith("/api/"):
            bucket = "ai" if request.path in ("/api/ideas", "/api/ask") else "plan"
            if not limiters[bucket].allow(request.remote_addr or "unknown"):
                resp = jsonify(error="Too many requests. Please wait a moment.")
                resp.status_code = 429
                resp.headers["Retry-After"] = str(app.config["RATE_WINDOW"])
                return resp
        return None

    @app.after_request
    def secure(resp):
        resp.headers["Content-Security-Policy"] = CSP
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if request.path.startswith("/api/"):
            resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.errorhandler(ValidationError)
    def on_validation(err: ValidationError):
        return jsonify(error="Please fix the highlighted fields.", fields=err.fields), 400

    @app.errorhandler(Exception)
    def on_error(err: Exception):
        if isinstance(err, HTTPException):
            return jsonify(error=err.name), err.code
        app.logger.exception("Unhandled error")
        return jsonify(error="Something went wrong on our side."), 500

    # ---- pages
    @app.get("/")
    def index():
        return send_from_directory(STATIC_DIR, "index.html")

    @app.get("/static/<path:name>")
    def static_files(name: str):
        return send_from_directory(STATIC_DIR, name, max_age=3600)

    @app.get("/healthz")
    def healthz():
        return jsonify(status="ok")

    # ---- API
    @app.post("/api/plan")
    def api_plan():
        body = json_body()
        return jsonify(build_plan(parse_plan_request(body, today()), today()))

    @app.post("/api/ideas")
    def api_ideas():
        body = json_body()
        plan = build_plan(parse_plan_request(body, today()), today())
        ai = llm.ideas(compact_context(plan)) if llm.enabled else None
        return jsonify(ideas=plan["ideas"], ai_ideas=ai or [], ai_used=ai is not None)

    @app.post("/api/ask")
    def api_ask():
        body = json_body()
        question = parse_question(body.get("question"))
        plan = build_plan(parse_plan_request(body, today()), today())
        answer = llm.answer(question, compact_context(plan)) if llm.enabled else None
        return jsonify(answer=answer or answer_offline(question, plan), source="ai" if answer else "offline")

    return app
