from __future__ import annotations

import concurrent.futures
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request

from app.services.llm import generate_text
from app.services.postprocess import postprocess_answer
from app.services.search_client import fetch_chunks

ask_bp = Blueprint("ask", __name__)


def _load_system_prompt() -> str:
    path = Path(current_app.config["PROMPTS_DIR"]) / "budget_agent.txt"
    return path.read_text(encoding="utf-8")


def _format_context(chunks: list[dict]) -> str:
    parts: list[str] = []
    for i, c in enumerate(chunks, 1):
        page = c.get("page_number", "?")
        section = c.get("section") or "Budget document"
        text = (c.get("text") or "").strip()
        parts.append(f"[Excerpt {i} | Page {page} | {section}]\n{text}")
    return "\n\n".join(parts) if parts else "(No excerpts retrieved.)"


def _extract_citations(chunks: list[dict]) -> list[dict]:
    seen: set[tuple] = set()
    citations: list[dict] = []
    for c in chunks:
        page = c.get("page_number")
        section = c.get("section") or ""
        key = (page, section)
        if key in seen:
            continue
        seen.add(key)
        citations.append({"page": page, "section": section})
    return citations


def _run_ask(question: str, ward: str | None, lang: str) -> dict:
    chunks = fetch_chunks(question, ward=ward)
    template = _load_system_prompt()
    context = _format_context(chunks)
    prompt = template.format(context=context, question=question)

    raw_answer = generate_text(current_app.config, prompt)
    answer = postprocess_answer(raw_answer, lang=lang)

    return {
        "answer": answer,
        "citations": _extract_citations(chunks),
        "ward": ward,
        "lang": lang,
        "chunks_used": len(chunks),
    }


@ask_bp.route("/api/ask", methods=["POST"])
def ask():
    body = request.get_json(silent=True) or {}
    question = (body.get("question") or "").strip()
    if not question:
        return jsonify({"error": "question is required"}), 400
    if len(question) > 2000:
        return jsonify({"error": "question too long (max 2000 characters)"}), 400

    ward = body.get("ward")
    if ward is not None:
        ward = str(ward).strip() or None

    lang = (body.get("lang") or "en").strip().lower()
    if lang not in ("en", "sw"):
        return jsonify({"error": 'lang must be "en" or "sw"'}), 400

    timeout = current_app.config.get("ASK_TIMEOUT_SECONDS", 30)
    app = current_app._get_current_object()

    def _run_with_context() -> dict:
        with app.app_context():
            return _run_ask(question, ward, lang)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(_run_with_context)
        try:
            result = future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            return jsonify({"error": "request timed out"}), 504

    return jsonify(result)
