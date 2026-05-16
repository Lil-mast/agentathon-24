"""Chunk parsed PDF pages into embedding-friendly text spans.

Consumes the page dicts produced by ``app.services.pdf_ingest.parse_pdf`` and
yields chunk dicts ready for embedding plus BigQuery insertion. Chunk size
targets 500 to 800 tokens (estimated as ``len(text) // 4``); splits prefer
paragraph then sentence boundaries, falling back to a hard char cut only when
needed.
"""
from __future__ import annotations

import hashlib
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# Token sizing. Rough heuristic: ~4 chars per token for English-ish prose.
CHARS_PER_TOKEN = 4
TARGET_MIN_TOKENS = 500
TARGET_MAX_TOKENS = 800
TARGET_MIN_CHARS = TARGET_MIN_TOKENS * CHARS_PER_TOKEN  # 2000
TARGET_MAX_CHARS = TARGET_MAX_TOKENS * CHARS_PER_TOKEN  # 3200

# Ward detector. Matches 1 to 3 Title-cased tokens followed by "Ward".
# Examples: "Kileleshwa Ward", "Westlands Ward", "Kayole North Ward".
WARD_RE = re.compile(
    r"[A-Z][a-zA-Z'\-]+(?:\s+[A-Z][a-zA-Z'\-]+){0,2}\s+Ward"
)

# Paragraph break: one or more blank lines.
PARAGRAPH_SPLIT_RE = re.compile(r"\n\s*\n+")

# Sentence split: end punctuation followed by whitespace. Naive but adequate.
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")


def estimate_tokens(text: str) -> int:
    """Return a rough token count for ``text`` using a 4-chars-per-token heuristic."""
    return len(text) // CHARS_PER_TOKEN


def chunk_pages(pages: list[dict]) -> list[dict]:
    """Split parsed pages into 500-800 token chunks with section and ward metadata."""
    chunks: list[dict] = []
    for page in pages:
        text = (page.get("text") or "").strip()
        if not text:
            continue

        page_number = int(page.get("page_number", 0))
        section = page.get("section")

        for idx, chunk_text in enumerate(_split_text(text)):
            chunk_text = chunk_text.strip()
            if not chunk_text:
                continue
            chunks.append(
                {
                    "chunk_id": _chunk_id(page_number, idx, chunk_text),
                    "page_number": page_number,
                    "section": section,
                    "ward": _detect_ward(chunk_text),
                    "text": chunk_text,
                }
            )

    logger.info("Produced %d chunks from %d pages", len(chunks), len(pages))
    return chunks


# ---------------------------------------------------------------------------
# Splitting
# ---------------------------------------------------------------------------


def _split_text(text: str) -> list[str]:
    """Split ``text`` into chunks within the target char window."""
    paragraphs = [p.strip() for p in PARAGRAPH_SPLIT_RE.split(text) if p.strip()]
    if not paragraphs:
        return []

    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        if len(para) > TARGET_MAX_CHARS:
            # Flush whatever we have, then split the oversized paragraph.
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(_split_oversized(para))
            continue

        candidate = f"{current}\n\n{para}" if current else para
        if len(candidate) <= TARGET_MAX_CHARS:
            current = candidate
            continue

        # Adding this paragraph would overflow. Decide whether current is
        # already substantial enough to emit, or if we should still pack more.
        if len(current) >= TARGET_MIN_CHARS:
            chunks.append(current)
            current = para
        else:
            # Current is too small to stand alone; merging would overflow, so
            # split the incoming paragraph and absorb a sentence prefix.
            merged = candidate
            pieces = _split_oversized(merged)
            # Last piece becomes the new "current"; earlier pieces are flushed.
            chunks.extend(pieces[:-1])
            current = pieces[-1] if pieces else ""

    if current:
        chunks.append(current)

    return chunks


def _split_oversized(text: str) -> list[str]:
    """Break a paragraph longer than the max into target-sized pieces."""
    sentences = SENTENCE_SPLIT_RE.split(text)
    sentences = [s.strip() for s in sentences if s.strip()]
    if not sentences:
        return _hard_split(text)

    chunks: list[str] = []
    current = ""
    for sent in sentences:
        if len(sent) > TARGET_MAX_CHARS:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(_hard_split(sent))
            continue
        candidate = f"{current} {sent}".strip() if current else sent
        if len(candidate) <= TARGET_MAX_CHARS:
            current = candidate
        else:
            if current:
                chunks.append(current)
            current = sent
    if current:
        chunks.append(current)
    return chunks


def _hard_split(text: str) -> list[str]:
    """Last-resort splitter on word boundaries, never mid-word."""
    pieces: list[str] = []
    remaining = text.strip()
    while len(remaining) > TARGET_MAX_CHARS:
        cut = remaining.rfind(" ", 0, TARGET_MAX_CHARS)
        if cut <= 0:
            # No whitespace in window; fall back to a hard slice but try to
            # advance to the next space to avoid splitting a token.
            cut = remaining.find(" ", TARGET_MAX_CHARS)
            if cut <= 0:
                pieces.append(remaining)
                return pieces
        pieces.append(remaining[:cut].strip())
        remaining = remaining[cut:].strip()
    if remaining:
        pieces.append(remaining)
    return pieces


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _detect_ward(text: str) -> Optional[str]:
    """Return the first ward name in ``text``, or None."""
    match = WARD_RE.search(text)
    if not match:
        return None
    return " ".join(match.group(0).split())


def _chunk_id(page_number: int, chunk_index: int, text: str) -> str:
    """Stable SHA1-derived chunk id keyed on (page, index, text prefix)."""
    key = f"{page_number}:{chunk_index}:{text[:50]}"
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]
    return f"chk_{digest}"
