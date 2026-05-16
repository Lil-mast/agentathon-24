# Person 2 — Agent & Q&A API (Complete)

Implementation checklist vs [TASKS_PERSON_2.md](./TASKS_PERSON_2.md).

## Checklist

| Task | Status | Notes |
|------|--------|-------|
| Vertex AI / `llm.py` | Done | Gemini 1.5 Pro when GCP creds present; mock fallback otherwise |
| `budget_agent.txt` prompt | Done | Plain language, citations, en/sw, refuse to guess |
| `POST /api/ask` | Done | Search → prompt → generate → postprocess; 30s timeout |
| `postprocess.py` | Done | Acronyms (KES, MTEF, CIDP, …), jargon softening, short sentences |
| `POST /api/agent/chat` | Done | In-memory sessions, follow-up context, trim old turns |
| Local dev search | Done | `local_search.py`, `POST /internal/search`, `build_local_index.py` |
| Tests (`test_ask.py`) | Done | 5 resident questions + validation, agent, health |
| Vertex Agent Builder (cloud) | **Deferred** | Documented below — needs Person 1 BigQuery + GCP console setup |

## Python environment

```bash
cd backend
python -m venv .venv

# Windows (Git Bash / cmd)
source .venv/Scripts/activate   # Git Bash
# .venv\Scripts\activate        # cmd/PowerShell

pip install -r requirements.txt
cp .env.example .env            # edit GCP_* if using real Vertex
```

Use `backend/.venv` (documented here) or `backend/venv` — both are fine; this repo standardizes on `.venv`.

## Build local index from Nairobi budget PDF

The repo-root PDF is used for chunking and search:

`2024-25-FY-Budget-Submission-PBB-DRAFT Nairobi.pdf`

```bash
cd backend
source .venv/Scripts/activate
python scripts/build_local_index.py
# optional: python scripts/build_local_index.py --pdf "../2024-25-FY-Budget-Submission-PBB-DRAFT Nairobi.pdf" --out data/chunks.json
```

This writes `backend/data/chunks.json` (~400 pages; extraction may take several minutes).

## Run the server

```bash
cd backend
source .venv/Scripts/activate
set FLASK_APP=wsgi.py          # Windows cmd: set FLASK_APP=wsgi
export FLASK_APP=wsgi.py       # Git Bash
python wsgi.py
# or: flask --app wsgi run --host 0.0.0.0 --port 5000
```

### Test endpoints (curl)

**Health**

```bash
curl http://127.0.0.1:5000/health
```

**Single-shot Q&A**

```bash
curl -X POST http://127.0.0.1:5000/api/ask \
  -H "Content-Type: application/json" \
  -d "{\"question\": \"How much was allocated for water in Westlands?\", \"ward\": \"Westlands\", \"lang\": \"en\"}"
```

**Internal search (dev)**

```bash
curl -X POST http://127.0.0.1:5000/internal/search \
  -H "Content-Type: application/json" \
  -d "{\"query\": \"health primary care\", \"top_k\": 5}"
```

**Multi-turn agent**

```bash
curl -X POST http://127.0.0.1:5000/api/agent/chat \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"What does the budget say about county health spending?\", \"lang\": \"en\"}"

# follow-up (use session_id from response)
curl -X POST http://127.0.0.1:5000/api/agent/chat \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"and for roads?\", \"session_id\": \"<SESSION_ID>\", \"lang\": \"en\"}"
```

## Tests

```bash
cd backend
source .venv/Scripts/activate
pytest -v
```

Tests use mock LLM and fixture chunks — no GCP required for CI.

## Person 1 vs Person 2

| Capability | Person 2 (now) | Person 1 (still needed) |
|------------|----------------|-------------------------|
| PDF parsing | pypdf + local chunks | Document AI, GCS `data/parsed/` |
| Chunking / embeddings | Char-based local chunks | `chunker.py`, Vertex embeddings |
| Search | TF-IDF on `chunks.json` | BigQuery `budget_chunks` + vector search |
| `/internal/search` | Local stub | Production implementation + BQ |
| Agent Builder | Flask in-memory chat | Vertex Agent Builder + BQ data store |

Set `INTERNAL_SEARCH_MODE=http` and `INTERNAL_SEARCH_URL=...` when Person 1’s search is deployed.

## Vertex AI (optional)

In `.env`:

```
GCP_PROJECT=your-project
GCP_REGION=us-central1
VERTEX_MODEL=gemini-1.5-pro-002
USE_MOCK_LLM=false
GOOGLE_APPLICATION_CREDENTIALS=path/to/service-account.json
```

**Vertex AI Agent Builder** (TASKS §4): create in GCP Console with BigQuery data store and/or a tool calling `POST /internal/search` once Person 1’s pipeline is live. `POST /api/agent/chat` currently uses the same grounded Gemini/mock path with session memory.

## Files added

```
backend/
├── .env.example
├── PERSON_2_DONE.md
├── requirements.txt
├── wsgi.py
├── pytest.ini
├── app/
│   ├── __init__.py
│   ├── config.py
│   ├── prompts/budget_agent.txt
│   ├── routes/ (health, ask, agent, internal)
│   └── services/ (llm, postprocess, local_search, search_client)
├── scripts/build_local_index.py
├── data/chunks.json          # generated
└── tests/ (conftest, test_ask)
```

## Nairobi 2024-25 FY Budget PDF

All prompts and local search reference the **Nairobi County 2024-25 Programme-Based Budget (PBB draft)** at the repository root. Page numbers in citations come from PDF page indices during indexing. Re-run `build_local_index.py` if the PDF is updated.
