"""
Vertex AI Agent Builder / Reasoning Engine proxy with in-memory session map.

Env: GCP_PROJECT, GCP_REGION, AGENT_ID (or AGENT_ENGINE_ID / REASONING_ENGINE_ID),
     USE_MOCK_AGENT=auto|true|false
"""

from __future__ import annotations

import logging
import os
import uuid
from typing import Any

import requests
from flask import current_app

from app.services.postprocess import postprocess_answer

logger = logging.getLogger(__name__)

# session_id -> {vertex_session, ward, lang, turns}
_sessions: dict[str, dict[str, Any]] = {}


class AgentBuilderError(Exception):
    """Agent Builder call failed."""


def _cfg(key: str, default: str = "") -> str:
    if current_app:
        val = current_app.config.get(key)
        if val:
            return str(val)
    return os.getenv(key, default)


def _agent_engine_id() -> str:
    return (
        _cfg("AGENT_ENGINE_ID")
        or _cfg("AGENT_ID")
        or _cfg("REASONING_ENGINE_ID")
        or os.getenv("AGENT_ENGINE_ID", "")
        or os.getenv("AGENT_ID", "")
        or os.getenv("REASONING_ENGINE_ID", "")
    )


def engine_resource_name() -> str | None:
    project = _cfg("GCP_PROJECT")
    region = _cfg("GCP_REGION", "us-central1")
    engine_id = _agent_engine_id()
    if not project or not engine_id:
        return None
    return f"projects/{project}/locations/{region}/reasoningEngines/{engine_id}"


def _use_mock() -> bool:
    mode = (_cfg("USE_MOCK_AGENT") or "auto").strip().lower()
    if mode in ("1", "true", "yes", "on"):
        return True
    if mode in ("0", "false", "no", "off"):
        return False
    return engine_resource_name() is None


def _access_token() -> str:
    import google.auth
    import google.auth.transport.requests

    creds, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    creds.refresh(google.auth.transport.requests.Request())
    return creds.token


def _ensure_session(session_id: str, ward: str | None, lang: str) -> dict[str, Any]:
    if session_id not in _sessions:
        _sessions[session_id] = {
            "vertex_session": None,
            "ward": ward,
            "lang": lang,
            "turns": [],
        }
    meta = _sessions[session_id]
    if ward is not None:
        meta["ward"] = ward
    meta["lang"] = lang
    return meta


def _mock_chat(message: str, session_id: str, ward: str | None, lang: str) -> dict[str, Any]:
    meta = _ensure_session(session_id, ward, lang)
    meta["turns"].append({"role": "user", "content": message})

    ward_phrase = f" in {ward}" if ward else ""
    prior_user = [
        t["content"]
        for t in meta["turns"]
        if t.get("role") == "user"
    ]
    context_hint = ""
    if len(prior_user) > 1:
        context_hint = f" (following up on: {prior_user[-2][:80]})"

    raw = (
        "[Dev mock — set GCP_PROJECT and AGENT_ID for live Agent Builder.] "
        f"You asked about the Nairobi County 2024-25 budget{ward_phrase}: "
        f"{message}{context_hint}. "
        "Open the budget PDF or use POST /api/ask for grounded citations."
    )
    answer = postprocess_answer(raw, lang=lang)
    meta["turns"].append({"role": "assistant", "content": answer})

    return {
        "answer": answer,
        "citations": [],
        "mock": True,
        "vertex_session": meta.get("vertex_session"),
    }


def _live_chat(message: str, session_id: str, ward: str | None, lang: str) -> dict[str, Any]:
    meta = _ensure_session(session_id, ward, lang)
    resource = engine_resource_name()
    if not resource:
        raise AgentBuilderError("Agent Builder is not configured (GCP_PROJECT, AGENT_ID).")

    region = _cfg("GCP_REGION", "us-central1")
    url = f"https://{region}-aiplatform.googleapis.com/v1/{resource}:query"

    payload: dict[str, Any] = {
        "input": {
            "message": message,
            "session_id": meta.get("vertex_session") or session_id,
            "user_id": session_id,
            "ward": ward,
            "lang": lang,
        },
    }

    try:
        token = _access_token()
    except Exception as exc:
        logger.warning("Agent Builder auth failed: %s", exc)
        raise AgentBuilderError(
            "Could not obtain GCP credentials for Agent Builder."
        ) from exc

    try:
        resp = requests.post(
            url,
            json=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            timeout=int(_cfg("AGENT_TIMEOUT_SECONDS", "60") or "60"),
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        logger.warning("Agent Builder query failed: %s", exc)
        raise AgentBuilderError(f"Agent Builder request failed: {exc}") from exc

    output = data.get("output") or data
    if isinstance(output, dict):
        raw_answer = (
            output.get("answer")
            or output.get("text")
            or output.get("response")
            or str(output)
        )
        citations = output.get("citations") or []
        vertex_session = output.get("session_id") or output.get("vertex_session")
    else:
        raw_answer = str(output)
        citations = []
        vertex_session = None

    if vertex_session:
        meta["vertex_session"] = vertex_session

    answer = postprocess_answer(str(raw_answer), lang=lang)
    meta["turns"].append({"role": "user", "content": message})
    meta["turns"].append({"role": "assistant", "content": answer})

    return {
        "answer": answer,
        "citations": citations if isinstance(citations, list) else [],
        "mock": False,
        "vertex_session": meta.get("vertex_session"),
    }


def chat(
    message: str,
    *,
    session_id: str | None = None,
    ward: str | None = None,
    lang: str = "en",
) -> dict[str, Any]:
    """Send a message to Agent Builder (or dev mock) and return answer metadata."""
    sid = session_id or str(uuid.uuid4())
    if _use_mock():
        return _mock_chat(message, sid, ward, lang)
    try:
        return _live_chat(message, sid, ward, lang)
    except AgentBuilderError:
        logger.info("Agent Builder unavailable; falling back to dev mock")
        return _mock_chat(message, sid, ward, lang)


def reset_sessions() -> None:
    """Clear in-memory sessions (for tests)."""
    _sessions.clear()
