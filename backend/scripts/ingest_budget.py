"""CLI to ingest a county budget PDF end-to-end into BigQuery.

Usage:
    python scripts/ingest_budget.py --pdf path/to/budget.pdf \
        [--source-url URL] [--version v1] [--force]

Pipeline: ensure_dataset_and_tables -> parse_pdf -> chunk_pages ->
embed_chunks -> register_document -> insert_chunks.
"""
from __future__ import annotations

import argparse
import hashlib
import logging
import sys
import time
from pathlib import Path

# Make `from app...` importable when invoked as `python scripts/ingest_budget.py`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.bq import (  # noqa: E402  (import after sys.path tweak)
    ensure_dataset_and_tables,
    insert_chunks,
    register_document,
)
from app.services.chunker import chunk_pages  # noqa: E402
from app.services.embeddings import embed_chunks  # noqa: E402
from app.services.pdf_ingest import parse_pdf  # noqa: E402

logger = logging.getLogger("ingest_budget")


def _compute_doc_id(pdf_path: Path) -> str:
    """Return a stable 16-char doc_id from the SHA-256 of the PDF bytes."""
    h = hashlib.sha256()
    with pdf_path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()[:16]


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Ingest a county budget PDF into BigQuery."
    )
    parser.add_argument("--pdf", required=True, help="Path to the budget PDF.")
    parser.add_argument(
        "--source-url",
        default=None,
        help="Public source URL of the PDF (defaults to file:// + abspath).",
    )
    parser.add_argument(
        "--version",
        default="draft",
        help="Document version label (default: draft).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-parse the PDF even if a cache hit exists.",
    )
    return parser.parse_args(argv)


def _step(label: str) -> float:
    """Start a step: log it and return the start time."""
    print(f"[ingest] {label}...", flush=True)
    logger.info("step start: %s", label)
    return time.perf_counter()


def _done(label: str, start: float) -> float:
    """Finish a step: log + print elapsed seconds and return the duration."""
    elapsed = time.perf_counter() - start
    print(f"[ingest] {label} done in {elapsed:.2f}s", flush=True)
    logger.info("step done: %s (%.2fs)", label, elapsed)
    return elapsed


def main(argv: list[str] | None = None) -> int:
    """Run the full ingestion pipeline. Returns a process exit code."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    args = _parse_args(argv)
    pdf_path = Path(args.pdf).resolve()
    if not pdf_path.exists():
        logger.error("PDF not found: %s", pdf_path)
        print(f"[ingest] ERROR: PDF not found: {pdf_path}", file=sys.stderr)
        return 1

    source_url = args.source_url or f"file://{pdf_path}"
    version = args.version

    total_start = time.perf_counter()
    try:
        doc_id = _compute_doc_id(pdf_path)
        print(f"[ingest] doc_id={doc_id} source_url={source_url} version={version}")

        t = _step("ensure_dataset_and_tables")
        ensure_dataset_and_tables()
        _done("ensure_dataset_and_tables", t)

        t = _step(f"parse_pdf ({pdf_path.name}, force={args.force})")
        pages = parse_pdf(pdf_path, force=args.force)
        _done(f"parse_pdf -> {len(pages)} pages", t)

        t = _step("chunk_pages")
        chunks = chunk_pages(pages)
        _done(f"chunk_pages -> {len(chunks)} chunks", t)

        if not chunks:
            print("[ingest] WARNING: no chunks produced; nothing to embed or insert.")
            dims = 0
        else:
            t = _step("embed_chunks")
            chunks = embed_chunks(chunks)
            _done("embed_chunks", t)
            first_emb = chunks[0].get("embedding") if chunks else None
            dims = len(first_emb) if first_emb else 0

        t = _step("register_document")
        register_document(doc_id, source_url, version)
        _done("register_document", t)

        t = _step("insert_chunks")
        inserted = insert_chunks(chunks, doc_id)
        _done(f"insert_chunks -> {inserted} rows", t)

        total = time.perf_counter() - total_start
        print(
            "[ingest] SUMMARY "
            f"pages={len(pages)} chunks={len(chunks)} dims={dims} "
            f"doc_id={doc_id} total_seconds={total:.2f}",
            flush=True,
        )
        return 0
    except Exception:
        logger.exception("Ingestion failed")
        total = time.perf_counter() - total_start
        print(
            f"[ingest] FAILED after {total:.2f}s (see log for traceback)",
            file=sys.stderr,
            flush=True,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
