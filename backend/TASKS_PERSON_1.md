# Backend Tasks — Person 1: Document Ingestion & Knowledge Base

**Focus:** Turn the 400-page county budget PDF into clean, searchable, structured data the agent can use.

**Stack:** Python, Flask, Google Document AI, BigQuery, Vertex AI embeddings.

---

## 1. Project skeleton

- [ ] Create the Flask app in `backend/app/`.
  - `app/__init__.py` — Flask app factory.
  - `app/config.py` — load env vars (GCP project, Document AI processor ID, BigQuery dataset, etc.).
  - `app/routes/` — blueprint folder for the other two people to plug into.
  - `wsgi.py` — entry point.
- [ ] Add `requirements.txt` with: `flask`, `google-cloud-documentai`, `google-cloud-bigquery`, `google-cloud-aiplatform`, `python-dotenv`, `pypdf`.
- [ ] Add `.env.example` and a `README.md` with run instructions.
- [ ] Add a simple `/health` endpoint.

## 2. PDF ingestion with Document AI

- [ ] Write `app/services/pdf_ingest.py`:
  - Function `parse_pdf(file_path) -> list[dict]` that calls Document AI and returns structured pages with text, tables, page number, and section heading.
  - Handle the 400-page document by splitting into batches Document AI can accept.
- [ ] Save the raw parsed output to GCS (or local `data/parsed/` for dev) so we don’t re-parse on every run.

## 3. Chunking & embeddings

- [ ] Write `app/services/chunker.py`:
  - Split parsed pages into ~500–800 token chunks, keeping section/heading metadata.
  - Each chunk should carry: `chunk_id`, `page_number`, `section`, `ward` (if present), `text`.
- [ ] Write `app/services/embeddings.py`:
  - Use Vertex AI text-embedding model to embed each chunk.

## 4. BigQuery as the knowledge base

- [ ] Create a BigQuery dataset `county_budget` with tables:
  - `budget_chunks` — `chunk_id, page_number, section, ward, text, embedding (ARRAY<FLOAT64>)`.
  - `budget_documents` — `doc_id, source_url, ingested_at, version`.
- [ ] Write `app/services/bq.py` with helpers:
  - `insert_chunks(chunks)`
  - `vector_search(query_embedding, top_k=8, ward=None)` using BigQuery `VECTOR_SEARCH` or cosine similarity SQL.
- [ ] Add a CLI script `scripts/ingest_budget.py` so anyone can run:
  `python scripts/ingest_budget.py --pdf path/to/budget.pdf`.

## 5. Internal endpoint for Person 2

- [ ] Expose `POST /internal/search` that takes `{query, ward?}` and returns the top-K budget chunks. Person 2 will call this from the agent.

## Deliverables

- A reproducible pipeline: PDF in → chunks + embeddings in BigQuery.
- A working `/internal/search` endpoint.
- A README section explaining how to ingest a new budget PDF.
