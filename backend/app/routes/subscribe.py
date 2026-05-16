from datetime import datetime, timezone

from flask import Blueprint, current_app, request
from phonenumbers import NumberParseException, PhoneNumberFormat, format_number, is_valid_number, parse

from app.services.bq import upsert_subscriber


subscribe_bp = Blueprint("subscribe", __name__)


def normalize_phone(phone: str) -> str:
    try:
        parsed = parse(phone, None)
    except NumberParseException as exc:
        raise ValueError("invalid phone number") from exc

    if not is_valid_number(parsed):
        raise ValueError("invalid phone number")

    return format_number(parsed, PhoneNumberFormat.E164)


@subscribe_bp.post("/api/subscribe")
def subscribe():
    payload = request.get_json(silent=True) or {}
    phone = payload.get("phone", "").strip()
    ward = payload.get("ward", "").strip()
    language = payload.get("language", "").strip().lower()

    if not phone or not ward or language not in {"en", "sw"}:
        return {"error": "phone, ward and language(en|sw) are required"}, 400

    try:
        normalized_phone = normalize_phone(phone)
    except ValueError:
        return {"error": "phone must be valid E.164"}, 400

    row = {
        "phone": normalized_phone,
        "ward": ward,
        "language": language,
        "subscribed_at": datetime.now(timezone.utc).isoformat(),
        "active": True,
    }
    upsert_subscriber(current_app.config, row)
    return {"status": "subscribed", "phone": normalized_phone, "ward": ward, "language": language}, 200


@subscribe_bp.post("/api/unsubscribe")
def unsubscribe():
    payload = request.get_json(silent=True) or {}
    phone = payload.get("phone", "").strip()
    if not phone:
        return {"error": "phone is required"}, 400

    try:
        normalized_phone = normalize_phone(phone)
    except ValueError:
        return {"error": "phone must be valid E.164"}, 400

    upsert_subscriber(
        current_app.config,
        {
            "phone": normalized_phone,
            "ward": "",
            "language": "en",
            "subscribed_at": datetime.now(timezone.utc).isoformat(),
            "active": False,
        },
        unsubscribe_only=True,
    )
    return {"status": "unsubscribed", "phone": normalized_phone}, 200
