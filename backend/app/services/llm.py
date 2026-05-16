"""Vertex AI Gemini client with mock fallback for local dev without GCP creds."""

from __future__ import annotations

import logging
import os
from typing import Any

from flask import current_app

logger = logging.getLogger(__name__)

_model = None
_vertex_ready = False
_mock_mode = True


def _should_use_mock() -> bool:
    cfg = current_app.config
    mode = (cfg.get("USE_MOCK_LLM") or "auto").strip().lower()
    if mode in ("1", "true", "yes", "on"):
        return True
    if mode in ("0", "false", "no", "off"):
        return False
    # auto: mock if no project or no Application Default Credentials
    if not cfg.get("GCP_PROJECT"):
        return True
    if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS") and not os.getenv(
        "CLOUDSDK_CONFIG"
    ):
        try:
            import google.auth

            google.auth.default()
            return False
        except Exception:
            return True
    return False


def _init_vertex() -> None:
    global _model, _vertex_ready, _mock_mode

    if _vertex_ready:
        return

    _mock_mode = _should_use_mock()
    if _mock_mode:
        logger.info("LLM: using mock mode (no Vertex AI)")
        _vertex_ready = True
        return

    project = current_app.config["GCP_PROJECT"]
    region = current_app.config["GCP_REGION"]
    model_name = current_app.config["VERTEX_MODEL"]

    try:
        import vertexai
        from vertexai.generative_models import GenerativeModel

        vertexai.init(project=project, location=region)
        _model = GenerativeModel(model_name)
        _mock_mode = False
        logger.info("LLM: Vertex AI initialized project=%s model=%s", project, model_name)
    except Exception as exc:
        logger.warning("LLM: Vertex init failed, falling back to mock: %s", exc)
        _mock_mode = True

    _vertex_ready = True


def _mock_generate(prompt: str, context_chunks: list[dict], lang: str = "en") -> str:
    if not context_chunks:
        if lang == "sw":
            return (
                "Samahani, sikuweza kupata taarifa hiyo katika bajeti ya Nairobi "
                "2024-25. Tafadhali uliza swali lingine au angalia ukurasa unaohusika."
            )
        return (
            "I could not find information about that in the Nairobi County "
            "2024-25 budget excerpts I have. Please try rephrasing or ask about "
            "a specific service (water, health, roads)."
        )

    pages = sorted({c.get("page_number") for c in context_chunks if c.get("page_number")})
    page_str = ", ".join(str(p) for p in pages[:5])
    snippet = (context_chunks[0].get("text") or "")[:400].strip()

    if lang == "sw":
        return (
            f"Kulingana na bajeti ya Nairobi 2024-25 (kurasa {page_str}): "
            f"{snippet}… [Jibu la majaribio — weka GCP ili kupata jibu kamili kutoka Gemini.]"
        )
    return (
        f"Based on the Nairobi County 2024-25 budget (pages {page_str}): "
        f"{snippet}… [Dev mock answer — set GCP credentials for full Gemini responses.]"
    )


def generate(prompt: str, context_chunks: list[dict[str, Any]], lang: str = "en") -> str:
    """
    Generate a grounded answer from prompt and retrieved chunks.

    Uses Gemini 1.5 Pro when Vertex is configured; otherwise returns a mock
    response that still cites available pages.
    """
    _init_vertex()

    if _mock_mode:
        return _mock_generate(prompt, context_chunks, lang)

    try:
        from vertexai.generative_models import GenerationConfig

        config = GenerationConfig(
            temperature=0.2,
            max_output_tokens=1024,
        )
        response = _model.generate_content(prompt, generation_config=config)
        text = response.text if response and response.text else ""
        return text.strip() or _mock_generate(prompt, context_chunks, lang)
    except Exception as exc:
        logger.exception("LLM generate failed: %s", exc)
        return _mock_generate(prompt, context_chunks, lang)


def is_mock_mode() -> bool:
    _init_vertex()
    return _mock_mode
