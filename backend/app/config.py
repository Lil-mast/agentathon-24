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
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    DEBUG = _bool(os.getenv("FLASK_DEBUG"), default=True)

    GCP_PROJECT = os.getenv("GCP_PROJECT", "")
    GCP_REGION = os.getenv("GCP_REGION", "us-central1")
    VERTEX_MODEL = os.getenv("VERTEX_MODEL", "gemini-1.5-pro-002")
    USE_MOCK_LLM = os.getenv("USE_MOCK_LLM", "auto").strip().lower()

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

    INTERNAL_SEARCH_MODE = os.getenv("INTERNAL_SEARCH_MODE", "local").strip().lower()
    INTERNAL_SEARCH_URL = os.getenv(
        "INTERNAL_SEARCH_URL", "http://127.0.0.1:5000/internal/search"
    )

    AGENT_MAX_TURNS = int(os.getenv("AGENT_MAX_TURNS", "10"))
    AGENT_CONTEXT_TURNS = int(os.getenv("AGENT_CONTEXT_TURNS", "6"))

    ASK_TIMEOUT_SECONDS = int(os.getenv("ASK_TIMEOUT_SECONDS", "30"))
    SEARCH_TOP_K = int(os.getenv("SEARCH_TOP_K", "8"))

    PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
