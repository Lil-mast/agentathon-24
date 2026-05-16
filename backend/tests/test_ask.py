"""Resident Q&A tests — postprocess unit tests + optional route integration."""

import pytest

from app.services import agent_builder
from app.services.postprocess import (
    expand_acronyms,
    postprocess_answer,
    shorten_sentences,
    soften_jargon,
)

RESIDENT_QUESTIONS = [
    "How much was allocated to my ward for water?",
    "What does the county budget say about health and primary care?",
    "How much is set aside for roads in Embakasi?",
    "What is the total proposed expenditure in the 2024-25 PBB draft?",
    "Are there bursaries or education funds for Kasarani ward?",
]


@pytest.fixture(autouse=True)
def _clear_agent_sessions():
    agent_builder.reset_sessions()
    yield
    agent_builder.reset_sessions()


@pytest.mark.parametrize("question", RESIDENT_QUESTIONS)
def test_resident_questions_postprocess_smoke(question):
    """Each sample question can be wrapped in a mock answer and postprocessed."""
    raw = (
        f"Regarding your question ({question}), the MTEF and CIDP guide "
        "KES appropriations for recurrent expenditure in the PBB draft."
    )
    out = postprocess_answer(raw, lang="en")
    assert out
    assert "Kenyan Shillings" in out or "KES" in out
    assert len(out.split()) > 5


def test_postprocess_expands_acronyms():
    text = "The MTEF and CIDP guide KES allocations."
    out = expand_acronyms(text)
    assert "Medium-Term Expenditure Framework" in out
    assert "County Integrated Development Plan" in out
    assert "Kenyan Shillings" in out


def test_postprocess_softens_jargon():
    text = "Recurrent expenditure and appropriation for WASH programmes."
    out = soften_jargon(text)
    assert "day-to-day spending" in out.lower()
    assert "money set aside" in out.lower()


def test_postprocess_shortens_long_sentences():
    long = (
        "The county proposed a very large allocation for water, sanitation, roads, "
        "health, education, and youth programmes across all wards in the financial year "
        "and the Medium-Term Expenditure Framework requires detailed reporting."
    )
    out = shorten_sentences(long, max_words=12)
    for chunk in out.split(". "):
        chunk = chunk.strip()
        if chunk:
            assert len(chunk.split()) <= 14


def test_postprocess_empty_string():
    assert postprocess_answer("") == ""


def test_postprocess_swahili_lang_still_shortens():
    text = "Pesa KES kwa maji na afya katika bajeti ya kaunti kwa mwaka wa fedha 2024-25."
    out = postprocess_answer(text, lang="sw")
    assert out


@pytest.mark.parametrize("case", [
    {
        "question": "How much was allocated to Westlands ward for water and sanitation?",
        "ward": "Westlands",
        "expect_in_answer": ["water", "Westlands"],
    },
    {
        "question": "What does the county budget say about health and primary care?",
        "ward": None,
        "expect_in_answer": ["health"],
    },
    {
        "question": "How much is set aside for roads in Embakasi?",
        "ward": "Embakasi",
        "expect_in_answer": ["road", "Embakasi"],
    },
    {
        "question": "What is the total proposed expenditure in the 2024-25 PBB draft?",
        "ward": None,
        "expect_in_answer": ["budget"],
    },
    {
        "question": "Are there bursaries or education funds for Kasarani ward?",
        "ward": "Kasarani",
        "expect_in_answer": ["Kasarani"],
    },
], ids=lambda c: c["question"][:40])
def test_ask_resident_questions(client, case):
    payload = {"question": case["question"], "lang": "en"}
    if case["ward"]:
        payload["ward"] = case["ward"]

    resp = client.post("/api/ask", json=payload)
    assert resp.status_code == 200
    data = resp.get_json()

    assert data["answer"]
    assert isinstance(data["citations"], list)
    assert len(data["citations"]) >= 1

    answer_lower = data["answer"].lower()
    for token in case["expect_in_answer"]:
        assert token.lower() in answer_lower


def test_ask_validation_errors(client):
    assert client.post("/api/ask", json={}).status_code == 400
    assert (
        client.post("/api/ask", json={"question": "Hi", "lang": "fr"}).status_code
        == 400
    )


def test_ask_swahili(client):
    resp = client.post(
        "/api/ask",
        json={
            "question": "Pesa ngapi kwa maji Westlands?",
            "ward": "Westlands",
            "lang": "sw",
        },
    )
    assert resp.status_code == 200
    assert resp.get_json().get("lang") == "sw"


def test_internal_search(client):
    resp = client.post(
        "/internal/search",
        json={"query": "water Westlands", "ward": "Westlands", "top_k": 3},
    )
    assert resp.status_code == 200
    assert len(resp.get_json().get("chunks", [])) >= 1


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json().get("status") == "ok"


def test_agent_chat_follow_up(client):
    r1 = client.post(
        "/api/agent/chat",
        json={"message": "How much for health in the county budget?", "lang": "en"},
    )
    assert r1.status_code == 200
    data1 = r1.get_json()
    session_id = data1["session_id"]
    assert data1.get("mock") is True
    assert data1["answer"]

    r2 = client.post(
        "/api/agent/chat",
        json={"message": "and for roads?", "session_id": session_id, "lang": "en"},
    )
    assert r2.status_code == 200
    data2 = r2.get_json()
    assert data2["session_id"] == session_id
    assert data2["answer"]
    assert "following up" in data2["answer"].lower() or "roads" in data2["answer"].lower()


def test_agent_chat_validation(client):
    assert client.post("/api/agent/chat", json={}).status_code == 400
    assert (
        client.post("/api/agent/chat", json={"message": "Hi", "lang": "fr"}).status_code
        == 400
    )
