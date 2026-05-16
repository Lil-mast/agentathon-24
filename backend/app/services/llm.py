from __future__ import annotations

import json
from typing import Any

import vertexai
from vertexai.generative_models import GenerativeModel


def _model(config: dict) -> GenerativeModel:
    vertexai.init(project=config["GOOGLE_CLOUD_PROJECT"], location=config["GOOGLE_CLOUD_REGION"])
    return GenerativeModel(config["GEMINI_MODEL"])


def generate_text(config: dict, prompt: str) -> str:
    response = _model(config).generate_content(prompt)
    return (response.text or "").strip()


def generate_json(config: dict, prompt: str) -> dict[str, Any]:
    text = generate_text(config, prompt)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Lightweight fallback for fenced JSON responses.
        cleaned = text.replace("```json", "").replace("```", "").strip()
        return json.loads(cleaned)


def generate(prompt: str, chunks: list[dict] | None = None, lang: str = "en") -> str:
    """Adapter used by routes/ask.py. `chunks` and `lang` are accepted for
    signature parity; the grounding is already in `prompt` and lang is applied
    by the postprocess step that runs after this call."""
    from flask import current_app
    return generate_text(current_app.config, prompt)
