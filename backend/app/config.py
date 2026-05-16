from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


class Config:
    GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID")
    GCP_LOCATION = os.environ.get("GCP_LOCATION", "us")

    DOCAI_PROCESSOR_ID = os.environ.get("DOCAI_PROCESSOR_ID")
    DOCAI_LOCATION = os.environ.get("DOCAI_LOCATION", "us")

    BQ_DATASET = os.environ.get("BQ_DATASET", "county_budget")
    BQ_LOCATION = os.environ.get("BQ_LOCATION", "US")

    EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "text-embedding-004")
    EMBEDDING_DIMENSIONS = int(os.environ.get("EMBEDDING_DIMENSIONS", "768"))

    GCS_BUCKET = os.environ.get("GCS_BUCKET")
    PARSED_OUTPUT_DIR = os.environ.get("PARSED_OUTPUT_DIR", "data/parsed")

    PORT = int(os.environ.get("PORT", "8080"))
    DEBUG = os.environ.get("FLASK_DEBUG", "0") == "1"
