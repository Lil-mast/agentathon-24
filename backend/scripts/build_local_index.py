#!/usr/bin/env python3
"""
Extract text from the Nairobi 2024-25 FY Budget PDF and write chunks.json for local search.

Usage (from backend/):
  python scripts/build_local_index.py
  python scripts/build_local_index.py --pdf ../2024-25-FY-Budget-Submission-PBB-DRAFT Nairobi.pdf
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from pypdf import PdfReader

BACKEND_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PDF = BACKEND_ROOT.parent / "2024-25-FY-Budget-Submission-PBB-DRAFT Nairobi.pdf"
DEFAULT_OUT = BACKEND_ROOT / "data" / "chunks.json"

CHUNK_CHARS = 1800
BATCH_LOG_EVERY = 50

# Sample Nairobi wards for metadata tagging (not exhaustive)
WARD_NAMES = [
    "Westlands",
    "Dagoretti",
    "Langata",
    "Kibra",
    "Roysambu",
    "Kasarani",
    "Ruaraka",
    "Embakasi",
    "Makadara",
    "Kamukunji",
    "Starehe",
    "Mathare",
]


def _detect_section(text: str) -> str | None:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    for line in lines[:5]:
        if len(line) < 120 and line.isupper():
            return line.title()
        if re.match(r"^(CHAPTER|PART|SECTION)\s+\d+", line, re.I):
            return line[:120]
    return None


def _detect_ward(text: str) -> str | None:
    lower = text.lower()
    for ward in WARD_NAMES:
        if ward.lower() in lower:
            return ward
    return None


def _merge_pages(pages: list[tuple[int, str]]) -> list[dict]:
    chunks: list[dict] = []
    buffer = ""
    start_page: int | None = None
    chunk_idx = 0

    def flush():
        nonlocal buffer, start_page, chunk_idx
        if not buffer.strip():
            buffer = ""
            start_page = None
            return
        chunk_idx += 1
        section = _detect_section(buffer)
        chunks.append(
            {
                "chunk_id": f"local-{chunk_idx:05d}",
                "page_number": start_page,
                "section": section,
                "ward": _detect_ward(buffer),
                "text": buffer.strip(),
            }
        )
        buffer = ""
        start_page = None

    for page_num, text in pages:
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            continue
        if start_page is None:
            start_page = page_num
        if len(buffer) + len(text) + 1 <= CHUNK_CHARS:
            buffer = f"{buffer} {text}".strip() if buffer else text
        else:
            flush()
            start_page = page_num
            buffer = text
            if len(buffer) > CHUNK_CHARS:
                # Very long single page — split hard
                for i in range(0, len(buffer), CHUNK_CHARS):
                    part = buffer[i : i + CHUNK_CHARS]
                    chunk_idx += 1
                    chunks.append(
                        {
                            "chunk_id": f"local-{chunk_idx:05d}",
                            "page_number": page_num,
                            "section": _detect_section(part),
                            "ward": _detect_ward(part),
                            "text": part,
                        }
                    )
                buffer = ""
                start_page = None
    flush()
    return chunks


def build_index(pdf_path: Path, out_path: Path) -> int:
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    reader = PdfReader(str(pdf_path))
    total = len(reader.pages)
    print(f"Reading {total} pages from {pdf_path.name}…")

    pages: list[tuple[int, str]] = []
    for i, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception as exc:
            print(f"  warning: page {i} extract failed: {exc}", file=sys.stderr)
            text = ""
        pages.append((i, text))
        if i % BATCH_LOG_EVERY == 0:
            print(f"  extracted {i}/{total} pages…")

    chunks = _merge_pages(pages)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)

    print(f"Wrote {len(chunks)} chunks to {out_path}")
    return len(chunks)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build local budget chunk index")
    parser.add_argument("--pdf", type=Path, default=DEFAULT_PDF)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    try:
        build_index(args.pdf.resolve(), args.out.resolve())
    except FileNotFoundError as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
