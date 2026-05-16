from flask import Blueprint, current_app, jsonify, request

from app.services import local_search

internal_bp = Blueprint("internal", __name__)


@internal_bp.route("/internal/search", methods=["POST"])
def internal_search():
    """
    Dev stub for Person 1's search API.

    Uses local TF-IDF over chunks.json when INTERNAL_SEARCH_MODE=local.
    """
    body = request.get_json(silent=True) or {}
    query = (body.get("query") or body.get("question") or "").strip()
    if not query:
        return jsonify({"error": "query is required"}), 400

    ward = body.get("ward")
    top_k = int(body.get("top_k", current_app.config.get("SEARCH_TOP_K", 8)))

    chunks = local_search.search(
        query,
        ward=ward,
        top_k=top_k,
        chunks_path=current_app.config["LOCAL_CHUNKS_PATH"],
    )
    return jsonify({"chunks": chunks, "count": len(chunks)})
