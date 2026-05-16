"""Call internal search directly or via HTTP depending on config."""

from __future__ import annotations

from typing import Any

import requests
from flask import current_app

from app.services import local_search


def fetch_chunks(
    question: str,
    ward: str | None = None,
    top_k: int | None = None,
) -> list[dict[str, Any]]:
    mode = current_app.config.get("INTERNAL_SEARCH_MODE", "local")
    k = top_k or current_app.config.get("SEARCH_TOP_K", 8)

    if mode == "local":
        return local_search.search(question, ward=ward, top_k=k)

    url = current_app.config.get("INTERNAL_SEARCH_URL")
    payload: dict[str, Any] = {"query": question, "top_k": k}
    if ward:
        payload["ward"] = ward

    try:
        resp = requests.post(url, json=payload, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data.get("chunks", data.get("results", []))
    except Exception:
        return local_search.search(question, ward=ward, top_k=k)
