from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_BACKEND_ROOT / ".env")


def _bool(val: str | None, default: bool = False) -> bool:
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


class Config:
    # --- Flask ---
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    DEBUG = _bool(os.getenv("FLASK_DEBUG"), default=False)
    PORT = int(os.environ.get("PORT", "8080"))

    # --- GCP project + locations ---
    # GCP_PROJECT_ID is the canonical name; GOOGLE_CLOUD_PROJECT kept as an
    # alias for Person 2 code that reads the older key.
    GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID") or os.environ.get("GOOGLE_CLOUD_PROJECT", "")
    GOOGLE_CLOUD_PROJECT = GCP_PROJECT_ID

    GCP_LOCATION = os.environ.get("GCP_LOCATION", "us")
    VERTEX_LOCATION = os.environ.get("VERTEX_LOCATION", "us-central1")
    GOOGLE_CLOUD_REGION = os.environ.get("GOOGLE_CLOUD_REGION", VERTEX_LOCATION)

    # --- BigQuery ---
    BQ_DATASET = os.environ.get("BQ_DATASET", "county_budget")
    BQ_LOCATION = os.environ.get("BQ_LOCATION", "US")

    # --- Document AI (Person 1 ingest fallback) ---
    DOCAI_PROCESSOR_ID = os.environ.get("DOCAI_PROCESSOR_ID")
    DOCAI_LOCATION = os.environ.get("DOCAI_LOCATION", "us")

    # --- Vertex AI embeddings (Person 1) ---
    EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "text-embedding-004")
    EMBEDDING_DIMENSIONS = int(os.environ.get("EMBEDDING_DIMENSIONS", "768"))

    # --- LLM (Person 3) ---
    VERTEX_MODEL = os.getenv("VERTEX_MODEL", "gemini-1.5-pro-002")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-pro")
    USE_MOCK_LLM = os.getenv("USE_MOCK_LLM", "auto").strip().lower()
    USE_MOCK_AGENT = os.getenv("USE_MOCK_AGENT", "auto").strip().lower()
    AGENT_ENGINE_ID = os.getenv("AGENT_ENGINE_ID", "")

    # --- Storage ---
    GCS_BUCKET = os.environ.get("GCS_BUCKET")
    PARSED_OUTPUT_DIR = os.environ.get("PARSED_OUTPUT_DIR", "data/parsed")

    # --- Internal auth ---
    APP_INTERNAL_TOKEN = os.getenv("APP_INTERNAL_TOKEN", "")

    # --- Internal search routing ---
    INTERNAL_SEARCH_MODE = os.getenv("INTERNAL_SEARCH_MODE", "local").strip().lower()
    INTERNAL_SEARCH_URL = os.getenv("INTERNAL_SEARCH_URL", "http://127.0.0.1:8080/internal/search")

    # --- Africa's Talking SMS (Person 2) ---
    AFRICASTALKING_USERNAME = os.getenv("AFRICASTALKING_USERNAME", "sandbox")
    AFRICASTALKING_API_KEY = os.getenv("AFRICASTALKING_API_KEY", "")
    AFRICASTALKING_SENDER_ID = os.getenv("AFRICASTALKING_SENDER_ID", "")

    # --- Gazette monitor (Person 2) ---
    GAZETTE_SOURCE_URL = os.getenv("GAZETTE_SOURCE_URL", "")
    ASK_API_URL = os.getenv("ASK_API_URL", "http://localhost:8080/api/ask")
    ENABLE_DEV_SCHEDULER = _bool(os.getenv("ENABLE_DEV_SCHEDULER"), default=False)

    # --- Local fallback search (Person 3) ---
    LOCAL_CHUNKS_PATH = Path(
        os.getenv("LOCAL_CHUNKS_PATH", str(_BACKEND_ROOT / "data" / "chunks.json"))
    )
    if not LOCAL_CHUNKS_PATH.is_absolute():
        LOCAL_CHUNKS_PATH = _BACKEND_ROOT / LOCAL_CHUNKS_PATH

    BUDGET_PDF_PATH = Path(
        os.getenv(
            "BUDGET_PDF_PATH",
            str(_BACKEND_ROOT.parent / "2024-25-FY-Budget-Submission-PBB-DRAFT Nairobi.pdf"),
        )
    )
    if not BUDGET_PDF_PATH.is_absolute():
        BUDGET_PDF_PATH = _BACKEND_ROOT / BUDGET_PDF_PATH

    # --- Agent runtime ---
    AGENT_MAX_TURNS = int(os.getenv("AGENT_MAX_TURNS", "10"))
    AGENT_CONTEXT_TURNS = int(os.getenv("AGENT_CONTEXT_TURNS", "6"))
    ASK_TIMEOUT_SECONDS = int(os.getenv("ASK_TIMEOUT_SECONDS", "30"))
    SEARCH_TOP_K = int(os.getenv("SEARCH_TOP_K", "8"))

    PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
