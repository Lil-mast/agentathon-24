"""Local TF-IDF search over budget chunks (Person 2 dev fallback)."""

from __future__ import annotations

import json
import logging
import math
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_chunks: list[dict[str, Any]] | None = None
_idf: dict[str, float] | None = None
_doc_vectors: list[dict[str, float]] | None = None


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", (text or "").lower())


def _load_chunks(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        logger.warning("Chunks file not found: %s — run scripts/build_local_index.py", path)
        return []
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else data.get("chunks", [])


def _build_index(chunks: list[dict[str, Any]]) -> None:
    global _idf, _doc_vectors

    doc_freq: dict[str, int] = {}
    doc_tokens: list[list[str]] = []

    for chunk in chunks:
        text = " ".join(
            filter(
                None,
                [
                    chunk.get("section"),
                    chunk.get("ward"),
                    chunk.get("text"),
                ],
            )
        )
        tokens = _tokenize(text)
        doc_tokens.append(tokens)
        for term in set(tokens):
            doc_freq[term] = doc_freq.get(term, 0) + 1

    n = len(chunks) or 1
    _idf = {term: math.log((n + 1) / (df + 1)) + 1.0 for term, df in doc_freq.items()}

    _doc_vectors = []
    for tokens in doc_tokens:
        tf: dict[str, int] = {}
        for t in tokens:
            tf[t] = tf.get(t, 0) + 1
        vec: dict[str, float] = {}
        for term, count in tf.items():
            if term in _idf:
                vec[term] = (count / len(tokens)) * _idf[term]
        _doc_vectors.append(vec)


def ensure_index(chunks_path: Path) -> None:
    global _chunks, _idf, _doc_vectors

    if _chunks is not None:
        return

    _chunks = _load_chunks(chunks_path)
    if _chunks:
        _build_index(_chunks)
        logger.info("Local search index loaded: %d chunks", len(_chunks))


def reload_index(chunks_path: Path) -> None:
    global _chunks, _idf, _doc_vectors
    _chunks = None
    _idf = None
    _doc_vectors = None
    ensure_index(chunks_path)


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(a.get(k, 0) * b.get(k, 0) for k in a)
    norm_a = math.sqrt(sum(v * v for v in a.values()))
    norm_b = math.sqrt(sum(v * v for v in b.values()))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _query_vector(query: str) -> dict[str, float]:
    assert _idf is not None
    tokens = _tokenize(query)
    if not tokens:
        return {}
    tf: dict[str, int] = {}
    for t in tokens:
        tf[t] = tf.get(t, 0) + 1
    vec: dict[str, float] = {}
    for term, count in tf.items():
        if term in _idf:
            vec[term] = (count / len(tokens)) * _idf[term]
    return vec


def search(
    query: str,
    ward: str | None = None,
    top_k: int = 8,
    chunks_path: Path | None = None,
) -> list[dict[str, Any]]:
    """
    Return top-k chunks ranked by TF-IDF cosine similarity.

    Optional ward filter: prefer chunks mentioning the ward; if none match,
    fall back to county-wide results.
    """
    from flask import current_app

    path = chunks_path or Path(current_app.config["LOCAL_CHUNKS_PATH"])
    ensure_index(path)

    if not _chunks or not _doc_vectors:
        return []

    qvec = _query_vector(query)
    scored: list[tuple[float, dict[str, Any]]] = []

    ward_lower = ward.lower().strip() if ward else None

    for i, chunk in enumerate(_chunks):
        score = _cosine(qvec, _doc_vectors[i])
        if ward_lower:
            chunk_text = (chunk.get("text") or "").lower()
            chunk_ward = (chunk.get("ward") or "").lower()
            if ward_lower in chunk_text or ward_lower in chunk_ward:
                score *= 1.5
            else:
                score *= 0.85
        if score > 0:
            scored.append((score, chunk))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored[:top_k]]
