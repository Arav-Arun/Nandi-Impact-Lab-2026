"""
services.extraction — free-text/voice → structured report fields (M2 intake).

Turns a messy multilingual message (typed, or transcribed by services.sarvam)
into the exact columns the matcher needs on db.models.MissingReport /
FoundReport. Uses Claude tool-calling when ANTHROPIC_API_KEY is set; otherwise a
deterministic heuristic so intake — and the demo — always works without a key.

Output field names map 1:1 to the report columns (subject_name, subject_age,
subject_gender ∈ male|female|unknown, physical_description, last_seen_landmark,
language_spoken, origin_city, reporter_mobile).
"""

from __future__ import annotations

import re

from pydantic import BaseModel

from core.config import settings
from core.logging_utils import get_logger
from services.sarvam import LANG_NAME

log = get_logger("nandi.extraction")


class Extracted(BaseModel):
    subject_name: str | None = None
    subject_age: int | None = None
    subject_gender: str | None = None          # male | female | unknown
    physical_description: str | None = None
    last_seen_landmark: str | None = None
    language_spoken: str | None = None
    origin_city: str | None = None
    reporter_mobile: str | None = None
    missing_fields: list[str] = []
    confidence: float = 0.0


_TOOL = {
    "name": "file_report",
    "description": "Record the structured missing/found-person report extracted from the message.",
    "input_schema": {
        "type": "object",
        "properties": {
            "subject_name": {"type": ["string", "null"], "description": "Name of the person, in the original script if given, else null."},
            "subject_gender": {"type": ["string", "null"], "enum": ["male", "female", "unknown", None]},
            "subject_age": {"type": ["integer", "null"], "description": "Approximate age in years if stated."},
            "physical_description": {"type": ["string", "null"], "description": "Clothing/appearance, in clear English for the operator."},
            "last_seen_landmark": {"type": ["string", "null"], "description": "Where last seen, as named in the message (e.g. Ramkund)."},
            "language_spoken": {"type": ["string", "null"], "description": "Primary language the person speaks (English name)."},
            "origin_city": {"type": ["string", "null"], "description": "Home city/town/district of origin (English)."},
            "reporter_mobile": {"type": ["string", "null"], "description": "Reporter's phone number if mentioned."},
            "missing_fields": {"type": "array", "items": {"type": "string"}, "description": "Important fields NOT present, to ask about next."},
            "confidence": {"type": "number", "description": "0-1 confidence this is a usable report."},
        },
        "required": ["missing_fields", "confidence"],
    },
}

_SYSTEM = (
    "You are NANDI's intake assistant at the Simhastha Kumbh Mela. Families report "
    "missing relatives (mostly elderly, rural, multilingual) by speaking or typing in "
    "their own language — Marathi, Hindi, Telugu, Bengali, Tamil and more. Extract a "
    "structured report by calling the file_report tool. Be faithful: never invent "
    "details that aren't stated. Normalize subject_gender to male/female/unknown. "
    "Translate the physical description to clear English for the operator, but keep "
    "names in their original script. List genuinely-missing key fields (subject_name, "
    "subject_age, last_seen_landmark, physical_description, reporter_mobile) in "
    "missing_fields."
)

_GENDER = {
    "male": "male", "female": "female", "m": "male", "f": "female",
    "boy": "male", "girl": "female", "man": "male", "woman": "female",
    "पुरुष": "male", "स्त्री": "female", "मुलगा": "male", "मुलगी": "female",
}


def _norm_gender(g: str | None) -> str | None:
    if not g:
        return None
    return _GENDER.get(g.strip().lower())


async def extract(text: str, detected_language: str | None = None) -> Extracted:
    """Structured extraction via Claude, falling back to the heuristic on any failure."""
    if not settings.claude_enabled:
        return _heuristic(text, detected_language)

    from anthropic import AsyncAnthropic

    client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    hint = f"\n(Audio was auto-detected as language: {detected_language}.)" if detected_language else ""
    try:
        msg = await client.messages.create(
            model=settings.ANTHROPIC_MODEL,
            max_tokens=700,
            system=_SYSTEM,
            tools=[_TOOL],
            tool_choice={"type": "tool", "name": "file_report"},
            messages=[{"role": "user", "content": f'Report message:\n"""\n{text}\n"""{hint}'}],
        )
    except Exception as e:  # network / auth / rate-limit — degrade, never drop the report
        log.warning("Claude extract failed (%s); using heuristic fallback", e)
        return _heuristic(text, detected_language)

    data = next((b.input for b in msg.content if getattr(b, "type", None) == "tool_use"), {})
    data = {k: v for k, v in data.items() if k in Extracted.model_fields}
    data["subject_gender"] = _norm_gender(data.get("subject_gender"))
    if not data.get("language_spoken") and detected_language:
        data["language_spoken"] = LANG_NAME.get(detected_language)
    if not data.get("physical_description"):
        data["physical_description"] = (text or "").strip()[:200] or None
    return Extracted(**data)


def _heuristic(text: str, detected_language: str | None) -> Extracted:
    """No-key fallback: light regex for phone/age/language; description = the message."""
    t = (text or "").strip()
    phone = re.search(r"(\+?\d[\d\s-]{8,}\d)", t)
    age = re.search(r"(\d{1,3})\s*(?:वर्ष|साल|years|year|yrs|वयाचे|वर्षांचे)", t)
    age_years = int(age.group(1)) if age else None
    lang = LANG_NAME.get(detected_language or "")
    missing = [
        f for f, present in [
            ("last_seen_landmark", "near" in t.lower() or "जवळ" in t),
            ("reporter_mobile", bool(phone)),
        ] if not present
    ]
    return Extracted(
        subject_age=age_years,
        language_spoken=lang,
        reporter_mobile=phone.group(1).strip() if phone else None,
        physical_description=t[:200] or None,
        missing_fields=missing or ["subject_name", "last_seen_landmark"],
        confidence=0.4 if t else 0.0,
    )
