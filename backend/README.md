# Backend — County Budget Agent

Flask backend for an agent that turns a 400-page county budget PDF into plain-language answers for ward residents, monitors the gazette for amendments, and sends SMS digests.

## Stack

- Python + Flask
- Vertex AI Agent Builder
- Gemini 1.5 Pro (long context)
- Document AI
- BigQuery
- Africa's Talking / Twilio (SMS)

## Team split

| Person | Area | Tasks |
|--------|------|-------|
| 1 | Document ingestion & knowledge base | [TASKS_PERSON_1.md](./TASKS_PERSON_1.md) |
| 2 | Agent & Q&A API | [TASKS_PERSON_2.md](./TASKS_PERSON_2.md) |
| 3 | Gazette monitor & SMS digests | [TASKS_PERSON_3.md](./TASKS_PERSON_3.md) |

## Suggested layout

```
backend/
├── app/
│   ├── __init__.py
│   ├── config.py
│   ├── routes/        # ask, agent, subscribe, internal
│   ├── services/      # pdf_ingest, chunker, embeddings, bq, llm, gazette, digest, sms
│   ├── prompts/
│   └── scheduler.py
├── scripts/           # ingest_budget.py, poll_gazette.py
├── tests/
├── requirements.txt
├── .env.example
└── wsgi.py
```

## Shared conventions

- One Flask app factory in `app/__init__.py`. Each person owns a blueprint under `app/routes/`.
- Shared services live in `app/services/`. Don’t duplicate Gemini or BigQuery clients — import from there.
- All config via env vars (see `.env.example`). No secrets in code.
- BigQuery tables are the source of truth for chunks, subscribers, amendments, and SMS logs.

## Setup

Requires Python 3.11+ and a GCP project with Document AI, BigQuery, and Vertex AI enabled.

1. Create and activate a virtualenv from inside `backend/`:

   ```powershell
   python -m venv .venv
   .venv\Scripts\Activate.ps1     # Windows PowerShell
   # or
   source .venv/bin/activate      # macOS / Linux
   ```

2. Install dependencies:

   ```
   pip install -r requirements.txt
   ```

3. Copy `.env.example` to `.env` and fill in your GCP values:

   ```
   cp .env.example .env
   ```

4. Authenticate the local environment with Application Default Credentials:

   ```
   gcloud auth application-default login
   ```

## Run

From inside `backend/`:

```
python wsgi.py
```

Smoke test:

```
curl http://localhost:8080/health
# {"status":"ok"}
```

## Endpoints

| Method | Path | Owner | Status | Description |
|--------|------|-------|--------|-------------|
| GET | `/health` | person 1 | done | Liveness probe |
| POST | `/internal/search` | person 1 | done | Vector search over budget chunks; called by the agent layer |

## Per-person docs

Operational details, ingest procedures, endpoint contracts, and deployment notes live per person:

- Person 1 (data layer): [`TASKS_PERSON_1_README.md`](TASKS_PERSON_1_README.md)
- Person 2 (agent + Q&A): see their own README once added
- Person 3 (gazette monitor + SMS): see their own README once added
