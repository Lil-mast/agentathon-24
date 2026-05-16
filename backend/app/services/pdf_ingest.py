"""PDF ingestion via Google Document AI.

`parse_pdf(file_path)` splits a PDF into sync-safe batches, sends each batch
through the configured Document AI processor, merges the results, and returns
a flat list of page dicts:

    [
        {
            "page_number": 1,
            "text": "...",
            "tables": [{"rows": [["c1", "c2"], ...]}, ...],
            "section": "VOTE 4641: ..." | None,
        },
        ...
    ]

The parsed output is cached by content hash under PARSED_OUTPUT_DIR (or the
configured GCS bucket if GCS_BUCKET is set) so repeat runs skip the API call.

Currently targets the standard OCR / Document OCR processor type. Layout
Parser support can be added later by branching on document.document_layout.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from io import BytesIO
from pathlib import Path
from typing import Optional

from google.api_core.client_options import ClientOptions
from google.cloud import documentai, storage
from pypdf import PdfReader, PdfWriter

from app.config import Config

logger = logging.getLogger(__name__)

# Sync limit for the OCR processor is 15 pages; Layout Parser is 30.
# 15 keeps us safe across processor types.
BATCH_PAGE_LIMIT = 15

# Best-effort section heading detection. Matches common PBB structures:
#   VOTE 4641: COUNTY EXECUTIVE OFFICE
#   PROGRAMME 1.1: ADMINISTRATION AND SUPPORT SERVICES
#   SUB-PROGRAMME 1.1.1: ...
#   PART A: VISION AND MISSION
# Falls through to the previous section if no match.
HEADING_RE = re.compile(
    r"^(?:VOTE\s+\d+\s*:[^\n]+"
    r"|(?:SUB[-\s]?)?PROGRAMME\s+[\d.]+\s*:[^\n]+"
    r"|PART\s+[A-Z]+\s*:[^\n]+)",
    re.MULTILINE,
)


def parse_pdf(file_path: str | Path, *, force: bool = False) -> list[dict]:
    """Parse a PDF through Document AI and return one dict per page.

    Args:
        file_path: Path to the local PDF file.
        force: If True, re-parse even if a cache hit exists.

    Returns:
        List of page dicts with `page_number`, `text`, `tables`, `section`.
    """
    path = Path(file_path).resolve()
    if not path.exists():
        raise FileNotFoundError(path)

    cached = _load_cache(path)
    if cached is not None and not force:
        logger.info("Cache hit for %s (%d pages)", path.name, len(cached))
        return cached

    client = _docai_client()
    batches = _split_pdf_into_batches(path, BATCH_PAGE_LIMIT)
    logger.info(
        "Parsing %s through Document AI in %d batches (<= %d pages each)",
        path.name,
        len(batches),
        BATCH_PAGE_LIMIT,
    )

    all_pages: list[dict] = []
    section: Optional[str] = None
    page_offset = 0
    for i, batch_bytes in enumerate(batches, start=1):
        logger.info("Batch %d/%d (page offset %d)", i, len(batches), page_offset)
        pages, section = _process_batch(client, batch_bytes, page_offset, section)
        all_pages.extend(pages)
        page_offset += len(pages)

    _save_cache(path, all_pages)
    return all_pages


# ---------------------------------------------------------------------------
# Document AI
# ---------------------------------------------------------------------------


def _docai_client() -> documentai.DocumentProcessorServiceClient:
    if not (Config.GCP_PROJECT_ID and Config.DOCAI_PROCESSOR_ID):
        raise RuntimeError(
            "Document AI is not configured. Set GCP_PROJECT_ID and "
            "DOCAI_PROCESSOR_ID in your .env (see .env.example)."
        )
    options = ClientOptions(
        api_endpoint=f"{Config.DOCAI_LOCATION}-documentai.googleapis.com"
    )
    return documentai.DocumentProcessorServiceClient(client_options=options)


def _processor_name() -> str:
    return (
        f"projects/{Config.GCP_PROJECT_ID}"
        f"/locations/{Config.DOCAI_LOCATION}"
        f"/processors/{Config.DOCAI_PROCESSOR_ID}"
    )


def _process_batch(
    client: documentai.DocumentProcessorServiceClient,
    pdf_bytes: bytes,
    page_offset: int,
    section: Optional[str],
) -> tuple[list[dict], Optional[str]]:
    request = documentai.ProcessRequest(
        name=_processor_name(),
        raw_document=documentai.RawDocument(
            content=pdf_bytes,
            mime_type="application/pdf",
        ),
    )
    result = client.process_document(request=request)
    doc = result.document

    pages: list[dict] = []
    for i, page in enumerate(doc.pages):
        text = _text_from_layout(page.layout, doc.text)
        section = _guess_section(text, section)
        pages.append(
            {
                "page_number": page_offset + i + 1,
                "text": text,
                "tables": _extract_tables(page, doc.text),
                "section": section,
            }
        )
    return pages, section


def _text_from_layout(
    layout: documentai.Document.Page.Layout, full_text: str
) -> str:
    parts = []
    for segment in layout.text_anchor.text_segments:
        start = int(segment.start_index or 0)
        end = int(segment.end_index or 0)
        parts.append(full_text[start:end])
    return "".join(parts).strip()


def _extract_tables(
    page: documentai.Document.Page, full_text: str
) -> list[dict]:
    tables: list[dict] = []
    for table in page.tables:
        rows: list[list[str]] = []
        for row in list(table.header_rows) + list(table.body_rows):
            rows.append(
                [_text_from_layout(cell.layout, full_text) for cell in row.cells]
            )
        tables.append({"rows": rows})
    return tables


def _guess_section(page_text: str, previous_section: Optional[str]) -> Optional[str]:
    match = HEADING_RE.search(page_text)
    if match:
        return " ".join(match.group(0).split())
    return previous_section


# ---------------------------------------------------------------------------
# PDF batching
# ---------------------------------------------------------------------------


def _split_pdf_into_batches(path: Path, pages_per_batch: int) -> list[bytes]:
    reader = PdfReader(str(path))
    total = len(reader.pages)
    batches: list[bytes] = []
    for start in range(0, total, pages_per_batch):
        writer = PdfWriter()
        for i in range(start, min(start + pages_per_batch, total)):
            writer.add_page(reader.pages[i])
        buf = BytesIO()
        writer.write(buf)
        batches.append(buf.getvalue())
    return batches


# ---------------------------------------------------------------------------
# Cache (local FS or GCS)
# ---------------------------------------------------------------------------


def _content_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def _cache_key(path: Path) -> str:
    return f"{path.stem}.{_content_hash(path)}.json"


def _load_cache(path: Path) -> Optional[list[dict]]:
    key = _cache_key(path)
    if Config.GCS_BUCKET:
        blob = _gcs_blob(key)
        if blob.exists():
            return json.loads(blob.download_as_text())
        return None
    local = Path(Config.PARSED_OUTPUT_DIR) / key
    if local.exists():
        return json.loads(local.read_text(encoding="utf-8"))
    return None


def _save_cache(path: Path, pages: list[dict]) -> None:
    key = _cache_key(path)
    payload = json.dumps(pages, indent=2)
    if Config.GCS_BUCKET:
        _gcs_blob(key).upload_from_string(payload, content_type="application/json")
        logger.info("Cached parse to gs://%s/parsed/%s", Config.GCS_BUCKET, key)
        return
    local_dir = Path(Config.PARSED_OUTPUT_DIR)
    local_dir.mkdir(parents=True, exist_ok=True)
    out = local_dir / key
    out.write_text(payload, encoding="utf-8")
    logger.info("Cached parse to %s", out)


def _gcs_blob(key: str) -> storage.Blob:
    client = storage.Client(project=Config.GCP_PROJECT_ID)
    bucket = client.bucket(Config.GCS_BUCKET)
    return bucket.blob(f"parsed/{key}")
