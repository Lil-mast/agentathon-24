"""Vertex AI text embeddings for budget chunks.

Wraps ``vertexai.language_models.TextEmbeddingModel`` with lazy initialisation
so importing this module never touches GCP credentials. Batches inputs at the
Vertex per-request limit (250) and preserves input order in the output list.
"""
from __future__ import annotations

import logging
import time
from typing import Optional

from google.api_core.exceptions import ResourceExhausted

from app.config import Config

logger = logging.getLogger(__name__)

# Vertex AI text-embedding endpoints enforce two limits per request:
#   - at most 250 input instances
#   - at most 20,000 total tokens across all instances
# The estimator below is a rough char-based heuristic; budget docs with many
# digits and short tokens trend higher than 4 chars/token, so we use 3 here
# and cap the per-request budget well under 20K with real headroom.
VERTEX_BATCH_INSTANCES = 250
VERTEX_BATCH_TOKEN_BUDGET = 15000
CHARS_PER_TOKEN = 3


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // CHARS_PER_TOKEN)


_model = None  # type: ignore[var-annotated]


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a list of strings, returning vectors in input order."""
    if not texts:
        return []

    model = _get_model()
    vectors: list[list[float]] = []

    batch: list[str] = []
    batch_tokens = 0
    sent = 0

    def flush() -> None:
        nonlocal batch, batch_tokens, sent
        if not batch:
            return
        logger.info(
            "Embedding batch %d..%d of %d (~%d tokens)",
            sent,
            sent + len(batch),
            len(texts),
            batch_tokens,
        )
        results = _embed_with_retry(model, batch)
        vectors.extend(list(emb.values) for emb in results)
        sent += len(batch)
        batch = []
        batch_tokens = 0

    for text in texts:
        tokens = _estimate_tokens(text)
        if batch and (
            len(batch) >= VERTEX_BATCH_INSTANCES
            or batch_tokens + tokens > VERTEX_BATCH_TOKEN_BUDGET
        ):
            flush()
        batch.append(text)
        batch_tokens += tokens
    flush()

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
# Retry on Vertex per-minute quota exhaustion
# ---------------------------------------------------------------------------

# Vertex embedding endpoints share a per-base-model RPM quota; bursting ~20+
# requests in a few seconds hits it. Backoff exponentially on 429 instead of
# failing the whole ingest.
RETRY_INITIAL_DELAY_S = 2.0
RETRY_MAX_DELAY_S = 30.0
RETRY_MAX_ATTEMPTS = 6


def _embed_with_retry(model, batch):
    delay = RETRY_INITIAL_DELAY_S
    last_exc: Optional[BaseException] = None
    for attempt in range(1, RETRY_MAX_ATTEMPTS + 1):
        try:
            return model.get_embeddings(batch)
        except ResourceExhausted as exc:
            last_exc = exc
            if attempt == RETRY_MAX_ATTEMPTS:
                break
            logger.warning(
                "Vertex 429 (attempt %d/%d); sleeping %.1fs before retry",
                attempt,
                RETRY_MAX_ATTEMPTS,
                delay,
            )
            time.sleep(delay)
            delay = min(delay * 2, RETRY_MAX_DELAY_S)
    assert last_exc is not None
    raise last_exc


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
