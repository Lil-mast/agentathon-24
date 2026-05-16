from flask import Blueprint, current_app, request

from app.services.amendments import detect_amendments_for_unprocessed
from app.services.digest import send_weekly_digests
from app.services.gazette import poll_and_store_latest_notices


internal_bp = Blueprint("internal", __name__)


def _authorized() -> bool:
    expected = current_app.config.get("APP_INTERNAL_TOKEN", "")
    if not expected:
        return False
    provided = request.headers.get("X-Internal-Token", "")
    return provided == expected


def run_poll_gazette() -> dict:
    poll_result = poll_and_store_latest_notices(current_app.config)
    detect_result = detect_amendments_for_unprocessed(current_app.config)
    return {"poll": poll_result, "detect": detect_result}


def run_send_digests() -> dict:
    return send_weekly_digests(current_app.config)


@internal_bp.post("/internal/poll-gazette")
def poll_gazette_endpoint():
    if not _authorized():
        return {"error": "unauthorized"}, 401
    return run_poll_gazette(), 200


@internal_bp.post("/internal/send-digests")
def send_digests_endpoint():
    if not _authorized():
        return {"error": "unauthorized"}, 401
    return run_send_digests(), 200
