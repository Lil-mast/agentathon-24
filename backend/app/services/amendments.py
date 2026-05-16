from __future__ import annotations

from typing import Any

from app.services.bq import insert_amendment, list_unprocessed_notices, mark_notice_processed
from app.services.llm import generate_json


PROMPT_TEMPLATE = """
You are a strict information extraction assistant.
Given this gazette notice text, answer in valid JSON only.

Question: Does this notice amend the county budget?

Return this JSON shape exactly:
{
  "is_amendment": true|false,
  "ward": "string or empty",
  "sector": "string or empty",
  "change_summary": "short text",
  "amount_delta": number or null
}

Notice title: {title}
Notice text:
{raw_text}
"""


def detect_amendments_for_unprocessed(config: dict) -> dict[str, Any]:
    notices = list_unprocessed_notices(config)
    processed = 0
    detected = 0

    for notice in notices:
        prompt = PROMPT_TEMPLATE.format(title=notice.get("title", ""), raw_text=notice.get("raw_text", ""))
        result = generate_json(config, prompt)

        if result.get("is_amendment"):
            insert_amendment(
                config,
                {
                    "notice_id": notice["notice_id"],
                    "ward": result.get("ward") or "",
                    "sector": result.get("sector") or "",
                    "change_summary": result.get("change_summary") or "",
                    "amount_delta": result.get("amount_delta"),
                },
            )
            detected += 1

        mark_notice_processed(config, notice["notice_id"])
        processed += 1

    return {"processed": processed, "detected": detected}
