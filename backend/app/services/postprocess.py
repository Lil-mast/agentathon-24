"""
Plain-language postprocessing for resident-facing answers.

Integration (Person 2 ask flow — do not wire here):
    from app.services.postprocess import postprocess_answer

    raw = generate(...)  # llm.py
    answer = postprocess_answer(raw, lang=lang or "en")
"""

from __future__ import annotations

import re

ACRONYMS: dict[str, str] = {
    r"\bKES\b": "Kenyan Shillings (KES)",
    r"\bMTEF\b": "Medium-Term Expenditure Framework (MTEF)",
    r"\bCIDP\b": "County Integrated Development Plan (CIDP)",
    r"\bPBB\b": "Programme-Based Budgeting (PBB)",
    r"\bFY\b": "financial year (FY)",
    r"\bNGO\b": "non-governmental organisation (NGO)",
    r"\bWASH\b": "water, sanitation and hygiene (WASH)",
    r"\bPHC\b": "primary health care (PHC)",
    r"\bO&M\b": "operations and maintenance (O&M)",
}

JARGON_REPLACEMENTS: list[tuple[str, str]] = [
    (r"\bappropriation\b", "money set aside"),
    (r"\bdisbursement\b", "payment"),
    (r"\butilisation\b", "use"),
    (r"\butilization\b", "use"),
    (r"\brecurrent expenditure\b", "day-to-day spending"),
    (r"\bdevelopment expenditure\b", "spending on projects and infrastructure"),
    (r"\bprogrammatic\b", "programme"),
    (r"\bsub-county\b", "local area"),
    (r"\bvote\b", "budget line"),
]


def expand_acronyms(text: str) -> str:
    """Expand known budget acronyms once (idempotent for already-expanded forms)."""
    return _expand_acronyms(text)


def soften_jargon(text: str) -> str:
    """Replace common budget jargon with plain-language phrases."""
    return _soften_jargon(text)


def shorten_sentences(text: str, max_words: int = 20) -> str:
    """Split long sentences into shorter clauses (about max_words each)."""
    return _shorten_sentences(text, max_words=max_words)


def _expand_acronyms(text: str) -> str:
    for pattern, replacement in ACRONYMS.items():
        acronym = replacement.split("(")[-1].rstrip(")")
        if acronym not in text:
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text


def _soften_jargon(text: str) -> str:
    for pattern, replacement in JARGON_REPLACEMENTS:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text


def _shorten_sentences(text: str, max_words: int = 20) -> str:
    """Split long sentences at punctuation or conjunctions where possible."""
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    out: list[str] = []

    for sent in sentences:
        words = sent.split()
        if len(words) <= max_words:
            out.append(sent.rstrip(".") + "." if sent and not sent.endswith((".", "!", "?")) else sent)
            continue

        parts = re.split(r",\s*|\s+(?:and|but|or|while|because)\s+", sent, flags=re.IGNORECASE)
        clause: list[str] = []
        for part in parts:
            part = part.strip()
            if not part:
                continue
            part_words = part.split()
            if len(clause) + len(part_words) <= max_words:
                clause.extend(part_words)
            else:
                if clause:
                    chunk = " ".join(clause).strip()
                    if chunk and not chunk.endswith("."):
                        chunk += "."
                    out.append(chunk)
                clause = part_words
        if clause:
            chunk = " ".join(clause).strip()
            if chunk and not chunk.endswith("."):
                chunk += "."
            out.append(chunk)

    return " ".join(out)


def postprocess_answer(text: str, lang: str = "en") -> str:
    """Strip jargon, expand acronyms, and enforce short sentences when lang is set."""
    if not text:
        return text

    text = _expand_acronyms(text)
    text = _soften_jargon(text)
    text = re.sub(r"\s+", " ", text).strip()

    if lang in ("en", "sw"):
        text = _shorten_sentences(text)

    return text
