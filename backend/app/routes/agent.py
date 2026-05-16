"""Multi-turn agent chat — proxies to Vertex AI Agent Builder session API."""

from __future__ import annotations

import uuid

from flask import Blueprint, jsonify, request

from app.services import agent_builder
from app.services.agent_builder import AgentBuilderError

agent_bp = Blueprint("agent", __name__)


@agent_bp.route("/api/agent/chat", methods=["POST"])
def agent_chat():
    """
    Proxy chat to Vertex AI Agent Builder (Reasoning Engine).

    Body: { "message": str, "session_id": str?, "ward": str?, "lang": "en"|"sw"? }
    """
    body = request.get_json(silent=True) or {}
    message = (body.get("message") or body.get("question") or "").strip()
    if not message:
        return jsonify({"error": "message is required"}), 400
    if len(message) > 4000:
        return jsonify({"error": "message too long (max 4000 characters)"}), 400

    session_id = (body.get("session_id") or "").strip() or str(uuid.uuid4())
    ward = body.get("ward")
    if ward is not None:
        ward = str(ward).strip() or None

    lang = (body.get("lang") or "en").strip().lower()
    if lang not in ("en", "sw"):
        return jsonify({"error": 'lang must be "en" or "sw"'}), 400

    try:
        result = agent_builder.chat(
            message,
            session_id=session_id,
            ward=ward,
            lang=lang,
        )
    except AgentBuilderError as exc:
        return (
            jsonify(
                {
                    "error": str(exc),
                    "session_id": session_id,
                    "configured": agent_builder.engine_resource_name() is not None,
                }
            ),
            503,
        )

    return jsonify(
        {
            "session_id": session_id,
            "answer": result["answer"],
            "citations": result.get("citations", []),
            "ward": ward,
            "lang": lang,
            "mock": result.get("mock", False),
            "agent_configured": agent_builder.engine_resource_name() is not None,
        }
    )
