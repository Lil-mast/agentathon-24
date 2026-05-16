from __future__ import annotations

from typing import Any

import requests

from app.services.bq import log_sms


def send_sms(config: dict, to: str, message: str) -> dict[str, Any]:
    username = config.get("AFRICASTALKING_USERNAME", "")
    api_key = config.get("AFRICASTALKING_API_KEY", "")
    sender_id = config.get("AFRICASTALKING_SENDER_ID", "")

    if not api_key:
        status = "skipped_missing_api_key"
        log_sms(config, to, message, status)
        return {"provider": "africastalking", "status": status}

    payload = {
        "username": username,
        "to": to,
        "message": message,
    }
    if sender_id:
        payload["from"] = sender_id

    response = requests.post(
        "https://api.africastalking.com/version1/messaging",
        data=payload,
        headers={"apiKey": api_key, "Accept": "application/json"},
        timeout=15,
    )

    status = "sent" if response.ok else f"failed_http_{response.status_code}"
    log_sms(config, to, message, status)
    return {
        "provider": "africastalking",
        "status": status,
        "http_status": response.status_code,
        "body": response.text,
    }
