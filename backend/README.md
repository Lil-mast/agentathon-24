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
