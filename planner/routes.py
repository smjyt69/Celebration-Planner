"""HTTP routes: pages, health check and the JSON API."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from flask import Blueprint, Response, current_app, jsonify, request, send_from_directory
from werkzeug.exceptions import UnsupportedMediaType

from .config import Settings
from .engine import answer_offline, build_plan
from .llm import LLMClient, compact_context
from .models import Plan
from .validation import ValidationError, parse_plan_request, parse_question

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

bp = Blueprint("main", __name__)


def _settings() -> Settings:
    return current_app.extensions["settings"]


def _llm() -> LLMClient:
    return current_app.extensions["llm"]


def _json_body() -> dict[str, Any]:
    """Return the request's JSON object, or raise a 415/400-style error."""
    if not request.is_json:
        raise UnsupportedMediaType("Send Content-Type: application/json.")
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ValidationError({"body": "Send a valid JSON object."})
    return data


def _plan_from_request(body: dict[str, Any]) -> Plan:
    today = _settings().today()
    return build_plan(parse_plan_request(body, today), today)


# ---- pages
@bp.get("/")
def index() -> Response:
    return send_from_directory(STATIC_DIR, "index.html")


@bp.get("/static/<path:name>")
def static_files(name: str) -> Response:
    return send_from_directory(STATIC_DIR, name, max_age=3600)


@bp.get("/healthz")
def healthz() -> Response:
    return jsonify(status="ok")


# ---- API
@bp.post("/api/plan")
def api_plan() -> Response:
    return jsonify(_plan_from_request(_json_body()))


@bp.post("/api/ideas")
def api_ideas() -> Response:
    plan = _plan_from_request(_json_body())
    llm = _llm()
    ai_ideas = llm.ideas(compact_context(plan)) if llm.enabled else None
    return jsonify(ideas=plan["ideas"], ai_ideas=ai_ideas or [], ai_used=ai_ideas is not None)


@bp.post("/api/ask")
def api_ask() -> Response:
    body = _json_body()
    question = parse_question(body.get("question"))
    plan = _plan_from_request(body)
    llm = _llm()
    answer = llm.answer(question, compact_context(plan)) if llm.enabled else None
    return jsonify(answer=answer or answer_offline(question, plan),
                   source="ai" if answer else "offline")
