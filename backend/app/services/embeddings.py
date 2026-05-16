"""Vertex AI text embeddings for budget chunks.

Wraps ``vertexai.language_models.TextEmbeddingModel`` with lazy initialisation
so importing this module never touches GCP credentials. Batches inputs at the
Vertex per-request limit (250) and preserves input order in the output list.
"""
from __future__ import annotations

import logging
from typing import Optional

from app.config import Config

logger = logging.getLogger(__name__)

# Vertex AI text-embedding endpoints accept at most 250 instances per call.
VERTEX_BATCH_LIMIT = 250

_model = None  # type: ignore[var-annotated]


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a list of strings, returning vectors in input order."""
    if not texts:
        return []

    model = _get_model()
    vectors: list[list[float]] = []
    for start in range(0, len(texts), VERTEX_BATCH_LIMIT):
        batch = texts[start : start + VERTEX_BATCH_LIMIT]
        logger.info(
            "Embedding batch %d..%d of %d",
            start,
            start + len(batch),
            len(texts),
        )
        results = model.get_embeddings(batch)
        vectors.extend(list(emb.values) for emb in results)
    return vectors


def embed_chunks(chunks: list[dict]) -> list[dict]:
    """Embed each chunk's ``text`` and attach the vector as ``embedding``."""
    if not chunks:
        return chunks
    vectors = embed_texts([c["text"] for c in chunks])
    for chunk, vector in zip(chunks, vectors):
        chunk["embedding"] = vector
    return chunks


# ---------------------------------------------------------------------------
# Lazy client
# ---------------------------------------------------------------------------


def _get_model():
    """Return a cached TextEmbeddingModel, initialising Vertex on first call."""
    global _model
    if _model is not None:
        return _model

    if not Config.GCP_PROJECT_ID:
        raise RuntimeError(
            "Vertex AI embeddings require GCP_PROJECT_ID. Set it in .env "
            "(see .env.example)."
        )

    # Imported lazily so module import never fails on missing credentials.
    import vertexai
    from vertexai.language_models import TextEmbeddingModel

    vertexai.init(
        project=Config.GCP_PROJECT_ID,
        location=Config.VERTEX_LOCATION,
    )
    logger.info(
        "Loading Vertex AI embedding model %s in %s/%s",
        Config.EMBEDDING_MODEL,
        Config.GCP_PROJECT_ID,
        Config.VERTEX_LOCATION,
    )
    _model = TextEmbeddingModel.from_pretrained(Config.EMBEDDING_MODEL)
    return _model


def _reset_model_for_tests() -> Optional[object]:
    """Clear the cached model. Useful for tests; not part of the public API."""
    global _model
    previous = _model
    _model = None
    return previous
