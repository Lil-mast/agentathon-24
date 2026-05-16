from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

import requests

from app.services.bq import insert_notices


def fetch_latest_notices(config: dict) -> list[dict[str, Any]]:
    source_url = config.get("GAZETTE_SOURCE_URL", "").strip()
    if not source_url:
        return []

    response = requests.get(source_url, timeout=20)
    response.raise_for_status()

    # Placeholder parser: expects JSON list payload with notice fields.
    raw_items = response.json()
    notices: list[dict[str, Any]] = []

    for idx, item in enumerate(raw_items):
        title = str(item.get("title", "")).strip()
        raw_text = str(item.get("raw_text", "")).strip() or str(item)
        url = str(item.get("url", source_url)).strip()
        published_at = item.get("published_at") or datetime.now(timezone.utc).isoformat()
        notice_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
        notice_id = str(item.get("notice_id", f"notice-{idx}-{notice_hash[:12]}"))

        notices.append(
            {
                "notice_id": notice_id,
                "published_at": published_at,
                "title": title,
                "url": url,
                "raw_text": raw_text,
                "hash": notice_hash,
                "processed": False,
            }
        )

    return notices


def poll_and_store_latest_notices(config: dict) -> dict[str, Any]:
    notices = fetch_latest_notices(config)
    inserted = insert_notices(config, notices)
    return {"fetched": len(notices), "inserted": inserted}
