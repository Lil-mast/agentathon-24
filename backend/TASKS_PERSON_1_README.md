# Person 1: Document Ingestion & Knowledge Base

Operational docs for the data layer. See [`TASKS_PERSON_1.md`](TASKS_PERSON_1.md) for the original task spec, and [`README.md`](README.md) for project-wide setup.

## What this layer does

Takes a Nairobi County budget PDF, runs it through Document AI, chunks the text, embeds each chunk with Vertex AI, and stores everything in BigQuery. Exposes a single `POST /internal/search` endpoint that the agent layer (person 2) calls.

```
PDF  ->  Document AI  ->  chunker  ->  Vertex embeddings  ->  BigQuery
                                                                  ^
                                                                  |
                              person 2's agent  --->  POST /internal/search
```

## Ingest a budget PDF

Prerequisites:

- GCP project configured per the [Setup](README.md#setup) section of the team README
- A Document AI processor created in your project (use the `Document OCR` type; the ingest currently targets that processor, Layout Parser is a future variant)
- `DOCAI_PROCESSOR_ID`, `GCP_PROJECT_ID`, `BQ_DATASET`, and the rest of `.env` filled in

Run the CLI from inside `backend/`:

```
python scripts/ingest_budget.py --pdf path/to/budget.pdf \
  --source-url "https://nairobi.go.ke/.../budget.pdf" \
  --version certified-2025-26
```

Flags:

- `--pdf` (required): local path to the PDF.
- `--source-url` (optional): provenance URL stored in `budget_documents`; defaults to `file://<abspath>`.
- `--version` (optional): label for this ingest; defaults to `draft`.
- `--force` (optional): bypass the local Document AI parse cache and re-call the API.

The script prints per-step durations and a final summary line:

```
[ingest] SUMMARY pages=412 chunks=348 dims=768 doc_id=a1b2c3d4e5f60718 total_seconds=187.4
```

Verify in BigQuery:

```sql
SELECT doc_id, COUNT(*) AS chunks, MIN(page_number) AS first_page, MAX(page_number) AS last_page
FROM `your_project.county_budget.budget_chunks`
GROUP BY doc_id
ORDER BY MAX(inserted_at) DESC
LIMIT 5;

SELECT * FROM `your_project.county_budget.budget_documents`
ORDER BY ingested_at DESC;
```

The ingest is idempotent on `doc_id` (the SHA-256 prefix of the PDF bytes): re-running with the same PDF replaces the existing chunks for that document and updates the row in `budget_documents`, so partial-failure retries are safe.

## Endpoint: `POST /internal/search`

Request body:

```json
{ "query": "How much was allocated to roads in Kileleshwa?", "ward": "Kileleshwa", "top_k": 8 }
```

- `query` (required, non-empty string)
- `ward` (optional string): pre-filter `budget_chunks` to rows whose ward heuristic matched this value
- `top_k` (optional int, default 8, max 50)

Response (200):

```json
{
  "results": [
    {
      "chunk_id": "chk_...",
      "page_number": 142,
      "section": "VOTE 4641: ...",
      "ward": "Kileleshwa",
      "text": "...",
      "distance": 0.12
    }
  ],
  "count": 1
}
```

Errors:

- `400` with `{"error": "..."}` for missing/empty `query`, non-integer `top_k`, `top_k` out of `[1, 50]`, or non-string `ward`.
- `500` with `{"error": "internal error"}` for any downstream failure (BigQuery, Vertex). Stack traces are logged server-side, never returned to the caller.

## BigQuery schema

Created on first ingest by `bq.ensure_dataset_and_tables()`. Reference DDL also in [`sql/schema.sql`](sql/schema.sql).

`{project}.{BQ_DATASET}.budget_chunks`:

| column | type | notes |
|--------|------|-------|
| `chunk_id` | STRING, REQUIRED | stable hash of (page, index, prefix); primary key for dedup |
| `page_number` | INT64 | 1-indexed page in the source PDF |
| `section` | STRING | best-effort heading extracted from the page (`VOTE N`, `PROGRAMME N.N`, etc.) |
| `ward` | STRING | first ward name found in the chunk, if any |
| `text` | STRING | chunk text |
| `doc_id` | STRING | links to `budget_documents.doc_id` |
| `embedding` | ARRAY<FLOAT64> | Vertex `text-embedding-004` vector, 768 dims |
| `inserted_at` | TIMESTAMP | defaults to `CURRENT_TIMESTAMP()` |

`{project}.{BQ_DATASET}.budget_documents`:

| column | type | notes |
|--------|------|-------|
| `doc_id` | STRING, REQUIRED | SHA-256 prefix of the PDF bytes |
| `source_url` | STRING | provenance |
| `ingested_at` | TIMESTAMP | defaults to `CURRENT_TIMESTAMP()` |
| `version` | STRING | free-form label (e.g. `draft`, `certified-2025-26`) |

## Deployment notes

The `/internal/*` endpoints have no application-level authentication. Treat them as internal-network-only:

- Behind a private VPC, IAP, or Cloud Run with `--no-allow-unauthenticated` and IAM-scoped invokers.
- Never expose `wsgi.py` directly to the public internet without an auth proxy in front.

The agent layer (person 2) is the intended caller of `/internal/search`.

## Modules

| File | Purpose |
|------|---------|
| `app/services/pdf_ingest.py` | Document AI batching (15 pages/batch), cache to local FS or GCS, page+section extraction |
| `app/services/chunker.py` | 500 to 800 token chunks, paragraph then sentence split, ward heuristic, stable `chunk_id` |
| `app/services/embeddings.py` | Vertex AI `text-embedding-004`, lazy client, 250-input batch limit |
| `app/services/bq.py` | Dataset + tables, idempotent `register_document` (MERGE) and `insert_chunks` (DELETE then load), `VECTOR_SEARCH` with optional ward filter |
| `app/routes/internal.py` | `POST /internal/search` blueprint |
| `scripts/ingest_budget.py` | End-to-end CLI |

## Caveats / known issues

- `pdf_ingest._gcs_blob` constructs a new `storage.Client` per call instead of using a singleton. Low impact (a couple of calls per ingest); aligns with `bq.py`/`embeddings.py` pattern when fixed.
- Section heading extraction is regex-based, best-effort. Pages without a recognisable heading inherit the previous page's section.
- Document AI Layout Parser support is not implemented; the code reads `document.pages` (OCR processor shape).
