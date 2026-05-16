# Backend Tasks — Person 2: Agent & Q&A API

**Focus:** Build the conversational agent that answers ward residents in plain language using the knowledge base from Person 1.

**Stack:** Python, Flask, Vertex AI Agent Builder, Gemini 1.5 Pro (long context).

---

## 1. Vertex AI / Gemini setup

- [ ] Add `google-cloud-aiplatform` and `vertexai` to `requirements.txt`.
- [ ] Create `app/services/llm.py`:
  - Initialize Vertex AI with project + region from config.
  - Wrap a `Gemini 1.5 Pro` client with a helper `generate(prompt, context_chunks, lang="en")`.
- [ ] Define a system prompt in `app/prompts/budget_agent.txt`:
  - Persona: friendly civic assistant for ward residents.
  - Rules: answer in plain language, cite page numbers, refuse to guess if context is missing, support English + Swahili.

## 2. Q&A endpoint

- [ ] Add `app/routes/ask.py` with:
  - `POST /api/ask` — body: `{ "question": str, "ward": str?, "lang": "en"|"sw"? }`.
  - Flow:
    1. Embed the question (reuse Person 1’s embeddings service).
    2. Call `/internal/search` (or the function directly) to get top chunks, filtered by ward if provided.
    3. Build a grounded prompt with the chunks + question.
    4. Call Gemini 1.5 Pro and return `{ answer, citations: [{page, section}], ward }`.
- [ ] Add basic input validation and a 30s timeout.

## 3. Plain-language guardrails

- [ ] In `app/services/postprocess.py`:
  - Strip jargon, expand acronyms (KES, MTEF, CIDP, etc.).
  - Enforce short sentences (max ~20 words) when `lang` is set.
- [ ] Add unit tests in `tests/test_ask.py` with 5 sample resident questions (e.g. "How much was allocated to my ward for water?").

## 4. Vertex AI Agent Builder integration

- [ ] Create an Agent in Vertex AI Agent Builder pointing at:
  - The BigQuery dataset (as a data store) **and/or**
  - A custom tool that calls our Flask `/internal/search` endpoint.
- [ ] Add `app/routes/agent.py`:
  - `POST /api/agent/chat` — multi-turn endpoint that proxies to the Agent Builder session API.
  - Persist `session_id` per user (in-memory dict for the hackathon, swappable later).

## 5. Conversation memory (lightweight)

- [ ] Store the last N turns per `session_id` so follow-ups like "and for health?" still work.
- [ ] Cap context at Gemini 1.5 Pro’s window — trim oldest turns if needed.

## Deliverables

- `POST /api/ask` — single-shot grounded Q&A.
- `POST /api/agent/chat` — multi-turn agent via Vertex AI Agent Builder.
- Prompt file + a small eval set of resident questions with expected behavior.
