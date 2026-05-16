# Vertex AI Agent Builder setup

Multi-turn chat is handled by **Vertex AI Agent Builder** (Reasoning Engine). The Flask route `POST /api/agent/chat` proxies to the engine; single-shot grounded Q&A stays on `POST /api/ask`.

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GCP_PROJECT` | Live mode | Google Cloud project ID |
| `GCP_REGION` | Live mode | Region (e.g. `us-central1`) |
| `AGENT_ID` | Live mode | Reasoning Engine ID (alias: `AGENT_ENGINE_ID`, `REASONING_ENGINE_ID`) |
| `USE_MOCK_AGENT` | No | `auto` (default): mock if project/agent missing; `true` / `false` |
| `AGENT_TIMEOUT_SECONDS` | No | HTTP timeout for `:query` (default `60`) |

Application Default Credentials (`gcloud auth application-default login` or a service account) are required for live calls.

## Create the agent (console)

1. Open [Vertex AI Agent Builder](https://console.cloud.google.com/gen-app-builder/engines).
2. Create an app / agent for **Nairobi County budget Q&A**.
3. **Data store (option A — BigQuery):** connect the Person 1 BigQuery dataset table of budget chunks as a structured or unstructured data store.
4. **Custom tool (option B — Flask search):** add an OpenAPI tool pointing at your deployed backend:
   - `POST /internal/search`
   - Body: `{ "query": string, "ward": string?, "top_k": number? }`
   - Returns `{ "chunks": [...] }` with `page_number`, `section`, `text`, `ward`.
5. System instructions: plain language, cite page numbers, refuse when context is missing, support English and Swahili (align with `app/prompts/budget_agent.txt`).
6. Deploy to **Agent Engine** / Reasoning Engine and copy the engine ID into `AGENT_ID`.

## Reasoning Engine API (what Flask calls)

Resource name:

```text
projects/{GCP_PROJECT}/locations/{GCP_REGION}/reasoningEngines/{AGENT_ID}
```

Query (non-streaming):

```http
POST https://{GCP_REGION}-aiplatform.googleapis.com/v1/{resource}:query
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "input": {
    "message": "<user message>",
    "session_id": "<vertex or client session id>",
    "user_id": "<client session_id>",
    "ward": "<optional ward>",
    "lang": "en"
  }
}
```

Your deployed agent’s `input` / `output` JSON shape may differ; adjust `app/services/agent_builder.py` `_live_chat` to match the engine’s contract.

## Flask endpoint contract

`POST /api/agent/chat`

```json
{
  "message": "How much for water in Westlands?",
  "session_id": "optional-uuid",
  "ward": "Westlands",
  "lang": "en"
}
```

Response:

```json
{
  "session_id": "...",
  "answer": "...",
  "citations": [],
  "ward": "Westlands",
  "lang": "en",
  "mock": true,
  "agent_configured": false
}
```

When `mock` is `true`, credentials or `AGENT_ID` are missing and the server returns a dev placeholder (tests and local UI still work).

## In-memory sessions (hackathon)

`app/services/agent_builder.py` keeps `session_id → { vertex_session, ward, lang, turns }` in process memory. Replace with Redis or Agent Platform Sessions API for production.

## Local dev without GCP

```bash
export USE_MOCK_AGENT=true
# or leave GCP_PROJECT / AGENT_ID unset (auto mock)
flask --app wsgi run
```
