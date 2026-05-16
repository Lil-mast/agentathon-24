import os

from dotenv import load_dotenv


def load_config() -> dict:
    load_dotenv()

    return {
        "FLASK_DEBUG": os.getenv("FLASK_ENV", "development") == "development",
        "FLASK_HOST": os.getenv("FLASK_HOST", "0.0.0.0"),
        "FLASK_PORT": int(os.getenv("FLASK_PORT", "5000")),
        "GOOGLE_CLOUD_PROJECT": os.getenv("GOOGLE_CLOUD_PROJECT", ""),
        "GOOGLE_CLOUD_REGION": os.getenv("GOOGLE_CLOUD_REGION", "us-central1"),
        "BQ_DATASET": os.getenv("BQ_DATASET", "county_budget"),
        "APP_INTERNAL_TOKEN": os.getenv("APP_INTERNAL_TOKEN", ""),
        "GEMINI_MODEL": os.getenv("GEMINI_MODEL", "gemini-1.5-pro"),
        "AFRICASTALKING_USERNAME": os.getenv("AFRICASTALKING_USERNAME", "sandbox"),
        "AFRICASTALKING_API_KEY": os.getenv("AFRICASTALKING_API_KEY", ""),
        "AFRICASTALKING_SENDER_ID": os.getenv("AFRICASTALKING_SENDER_ID", ""),
        "ASK_API_URL": os.getenv("ASK_API_URL", "http://localhost:5000/api/ask"),
        "GAZETTE_SOURCE_URL": os.getenv("GAZETTE_SOURCE_URL", ""),
        "ENABLE_DEV_SCHEDULER": os.getenv("ENABLE_DEV_SCHEDULER", "false").lower() == "true",
    }
