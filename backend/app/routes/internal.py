"""Internal endpoints (not user-facing).

- POST /internal/search        - vector search over budget chunks (Person 1)
- POST /internal/poll-gazette  - cron: scrape gazette + detect amendments (Person 2)
- POST /internal/send-digests  - cron: send weekly SMS digests (Person 2)

The cron endpoints require an X-Internal-Token header matching
APP_INTERNAL_TOKEN. /search is open inside the VPC and intended to be called
by the ask/agent services in the same project.
"""
from __future__ import annotations

import logging
from typing import Any

from flask import Blueprint, current_app, jsonify, request

logger = logging.getLogger(__name__)

bp = Blueprint("internal", __name__, url_prefix="/internal")

TOP_K_DEFAULT = 8
TOP_K_MAX = 50


def _strip_embeddings(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cleaned: list[dict[str, Any]] = []
    for row in results:
        if "embedding" in row:
            row = {k: v for k, v in row.items() if k != "embedding"}
        cleaned.append(row)
    return cleaned


def _authorized() -> bool:
    expected = current_app.config.get("APP_INTERNAL_TOKEN", "")
    if not expected:
        return False
    provided = request.headers.get("X-Internal-Token", "")
    return provided == expected


@bp.post("/search")
def search():
    """Embed a query and return the top-K matching budget chunks."""
    from app.services.bq import vector_search
    from app.services.embeddings import embed_texts

    payload = request.get_json(silent=True) or {}

    query = payload.get("query")
    if not isinstance(query, str) or not query.strip():
        return jsonify({"error": "query is required and must be a non-empty string"}), 400

    top_k: Any = payload.get("top_k", TOP_K_DEFAULT)
    if isinstance(top_k, bool) or not isinstance(top_k, int):
        return jsonify({"error": "top_k must be an integer"}), 400
    if top_k < 1 or top_k > TOP_K_MAX:
        return jsonify({"error": f"top_k must be in [1, {TOP_K_MAX}]"}), 400

    ward = payload.get("ward")
    if ward is not None and not isinstance(ward, str):
        return jsonify({"error": "ward must be a string or null"}), 400

    try:
        query_emb = embed_texts([query])[0]
        results = vector_search(query_emb, top_k=top_k, ward=ward)
        results = _strip_embeddings(results)
        return jsonify({"results": results, "count": len(results)}), 200
    except Exception:
        current_app.logger.exception("internal search failed")
        return jsonify({"error": "internal error"}), 500


def run_poll_gazette() -> dict:
    from app.services.amendments import detect_amendments_for_unprocessed
    from app.services.gazette import poll_and_store_latest_notices
    poll_result = poll_and_store_latest_notices(current_app.config)
    detect_result = detect_amendments_for_unprocessed(current_app.config)
    return {"poll": poll_result, "detect": detect_result}


def run_send_digests() -> dict:
    from app.services.digest import send_weekly_digests
    return send_weekly_digests(current_app.config)


@bp.post("/poll-gazette")
def poll_gazette_endpoint():
    if not _authorized():
        return jsonify({"error": "unauthorized"}), 401
    return jsonify(run_poll_gazette()), 200


@bp.post("/send-digests")
def send_digests_endpoint():
    if not _authorized():
        return jsonify({"error": "unauthorized"}), 401
    return jsonify(run_send_digests()), 200
