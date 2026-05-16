import json
from pathlib import Path

import pytest

from app import create_app

SAMPLE_CHUNKS = [
    {
        "chunk_id": "test-001",
        "page_number": 42,
        "section": "Water and Sanitation",
        "ward": "Westlands",
        "text": (
            "Westlands ward water and sanitation allocation for FY 2024-25 "
            "is KES 120 million for borehole rehabilitation and pipeline repairs."
        ),
    },
    {
        "chunk_id": "test-002",
        "page_number": 88,
        "section": "Health Services",
        "ward": None,
        "text": (
            "County health programmes include KES 2.1 billion for primary health care, "
            "community health volunteers, and facility operations across all sub-counties."
        ),
    },
    {
        "chunk_id": "test-003",
        "page_number": 156,
        "section": "Transport and Roads",
        "ward": "Embakasi",
        "text": (
            "Embakasi roads maintenance vote is KES 85 million for grading, "
            "drainage, and street lighting on feeder roads."
        ),
    },
    {
        "chunk_id": "test-004",
        "page_number": 12,
        "section": "Overview",
        "ward": None,
        "text": (
            "Nairobi County 2024-25 Programme-Based Budget total proposed expenditure "
            "is published in the PBB draft submission document."
        ),
    },
    {
        "chunk_id": "test-005",
        "page_number": 201,
        "section": "Education and Youth",
        "ward": "Kasarani",
        "text": (
            "Kasarani ward bursary and ECD support allocation is KES 15 million "
            "for school feeding and early childhood centres."
        ),
    },
]


@pytest.fixture
def chunks_file(tmp_path: Path) -> Path:
    path = tmp_path / "chunks.json"
    path.write_text(json.dumps(SAMPLE_CHUNKS), encoding="utf-8")
    return path


@pytest.fixture
def app(chunks_file: Path):
    application = create_app()
    application.config.update(
        {
            "TESTING": True,
            "USE_MOCK_LLM": "true",
            "LOCAL_CHUNKS_PATH": chunks_file,
            "INTERNAL_SEARCH_MODE": "local",
            "ASK_TIMEOUT_SECONDS": 30,
        }
    )
    return application


@pytest.fixture
def client(app):
    return app.test_client()
