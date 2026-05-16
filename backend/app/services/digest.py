from __future__ import annotations

from typing import Any

import requests

from app.routes.subscribe import normalize_phone
from app.services.bq import (
    get_subscriber,
    list_active_subscribers,
    list_recent_amendments_for_ward,
    list_top_allocations_for_ward,
)
from app.services.llm import generate_text
from app.services.sms import send_sms


def _build_digest_prompt(ward: str, language: str, allocations: list[dict], amendments: list[dict]) -> str:
    return f"""
Create an SMS digest for ward residents.
Language: {language}
Max length: 160 chars total.
Include:
1) Top 3 budget allocations for ward {ward}
2) Any amendments in last 7 days

Top allocations: {allocations}
Recent amendments: {amendments}

Return plain text only, no quotes, no markdown.
"""


def generate_digest_for_ward(config: dict, ward: str, language: str) -> str:
    allocations = list_top_allocations_for_ward(config, ward=ward, top_k=3)
    amendments = list_recent_amendments_for_ward(config, ward=ward, days=7)
    prompt = _build_digest_prompt(ward, language, allocations, amendments)
    text = generate_text(config, prompt).replace("\n", " ").strip()
    return text[:160]


def send_weekly_digests(config: dict) -> dict[str, Any]:
    subscribers = list_active_subscribers(config)
    sent = 0
    failed = 0

    cache: dict[tuple[str, str], str] = {}

    for sub in subscribers:
        ward = (sub.get("ward") or "").strip()
        language = (sub.get("language") or "en").strip().lower()
        key = (ward, language)

        if key not in cache:
            cache[key] = generate_digest_for_ward(config, ward=ward, language=language)

        result = send_sms(config, to=sub["phone"], message=cache[key])
        if result.get("status", "").startswith("sent"):
            sent += 1
        else:
            failed += 1

    return {"subscribers": len(subscribers), "sent": sent, "failed": failed}


def build_reply_for_question(config: dict, phone: str, question: str) -> str:
    normalized = normalize_phone(phone)
    subscriber = get_subscriber(config, normalized)
    ward = subscriber.get("ward") if subscriber else None
    lang = subscriber.get("language") if subscriber else "en"

    ask_api_url = config.get("ASK_API_URL", "").strip()
    if ask_api_url:
        try:
            response = requests.post(
                ask_api_url,
                json={"question": question, "ward": ward, "lang": lang},
                timeout=25,
            )
            if response.ok:
                answer = (response.json().get("answer") or "").strip()
                if answer:
                    return answer[:160]
        except requests.RequestException:
            pass

    fallback = "Swali limepokelewa. Tafadhali jaribu tena baadaye." if lang == "sw" else "Question received. Please try again later."
    return fallback[:160]
