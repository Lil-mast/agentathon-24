"""Internal endpoints used by other services in this app.

Currently exposes `POST /internal/search`, which embeds a query and runs a
BigQuery vector search over the budget chunks.
"""
from __future__ import annotations

import logging
from typing import Any

from flask import Blueprint, current_app, jsonify, request

from app.services.bq import vector_search
from app.services.embeddings import embed_texts

logger = logging.getLogger(__name__)

bp = Blueprint("internal", __name__, url_prefix="/internal")

TOP_K_DEFAULT = 8
TOP_K_MAX = 50


def _strip_embeddings(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return results with any `embedding` field removed (defensive copy)."""
    cleaned: list[dict[str, Any]] = []
    for row in results:
        if "embedding" in row:
            row = {k: v for k, v in row.items() if k != "embedding"}
        cleaned.append(row)
    return cleaned


@bp.post("/search")
def search():
    """Embed a query and return the top-K matching budget chunks."""
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
