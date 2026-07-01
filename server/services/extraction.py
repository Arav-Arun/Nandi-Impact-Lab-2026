"""
services.extraction - free-text/voice → structured report fields.

Turns a messy multilingual message (typed, or transcribed by services.sarvam)
into the columns the matcher needs. Provider order: OpenAI → Anthropic → a
deterministic heuristic, so intake always works even with no LLM key.

Output field names map 1:1 to the report columns (subject_name, subject_age,
subject_gender ∈ male|female|unknown, physical_description, last_seen_landmark,
language_spoken, origin_city, reporter_mobile).
"""

from __future__ import annotations

import json
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


# JSON-schema for the structured output, shared by both LLM providers.
_SCHEMA = {
    "type": "object",
    "properties": {
        "subject_name": {"type": ["string", "null"], "description": "Person's name, in the original script if given."},
        "subject_gender": {"type": ["string", "null"], "enum": ["male", "female", "unknown", None]},
        "subject_age": {"type": ["integer", "null"], "description": "Approximate age in years if stated."},
        "physical_description": {"type": ["string", "null"], "description": "Clothing/appearance, in clear English for the operator."},
        "last_seen_landmark": {"type": ["string", "null"], "description": "Where last seen, as named (e.g. Ramkund)."},
        "language_spoken": {"type": ["string", "null"], "description": "Primary language the person speaks (English name)."},
        "origin_city": {"type": ["string", "null"], "description": "Home city/town/district of origin (English)."},
        "reporter_mobile": {"type": ["string", "null"], "description": "Reporter's phone number if mentioned."},
        "missing_fields": {"type": "array", "items": {"type": "string"}, "description": "Important fields NOT present, to ask next."},
        "confidence": {"type": "number", "description": "0-1 confidence this is a usable report."},
    },
    "required": ["missing_fields", "confidence"],
}

_SYSTEM = (
    "You are NANDI's intake assistant at the Simhastha Kumbh Mela. Families report "
    "missing relatives (mostly elderly, rural, multilingual) by speaking or typing in "
    "their own language. Extract a structured report. Be faithful: never invent "
    "details. Normalize gender to male/female/unknown. Translate the physical "
    "description to clear English but keep names in their original script. List "
    "genuinely-missing key fields (subject_name, subject_age, last_seen_landmark, "
    "physical_description, reporter_mobile) in missing_fields."
)

_GENDER = {
    "male": "male", "female": "female", "m": "male", "f": "female",
    "boy": "male", "girl": "female", "man": "male", "woman": "female",
    "पुरुष": "male", "स्त्री": "female", "मुलगा": "male", "मुलगी": "female",
}


def _norm_gender(g: str | None) -> str | None:
    return _GENDER.get(g.strip().lower()) if g else None


def _user_prompt(text: str, detected_language: str | None) -> str:
    hint = f"\n(Audio auto-detected as language: {detected_language}.)" if detected_language else ""
    return f'Report message:\n"""\n{text}\n"""{hint}'


async def extract(text: str, detected_language: str | None = None) -> Extracted:
    """Structured extraction via the best available provider, degrading gracefully."""
    data: dict | None = None
    if settings.openai_enabled:
        data = await _extract_openai(text, detected_language)
    if data is None and settings.claude_enabled:
        data = await _extract_anthropic(text, detected_language)
    if data is None:
        return _heuristic(text, detected_language)
    return _finalize(data, text, detected_language)


async def _extract_openai(text: str, detected_language: str | None) -> dict | None:
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    tool = {"type": "function", "function": {"name": "file_report",
            "description": "Record the structured missing/found-person report.", "parameters": _SCHEMA}}
    try:
        resp = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[{"role": "system", "content": _SYSTEM},
                      {"role": "user", "content": _user_prompt(text, detected_language)}],
            tools=[tool],
            tool_choice={"type": "function", "function": {"name": "file_report"}},
        )
        calls = resp.choices[0].message.tool_calls
        return json.loads(calls[0].function.arguments) if calls else None
    except Exception as e:  # network / auth / quota - degrade, never drop the report
        log.warning("OpenAI extract failed (%s); trying next provider", e)
        return None


async def _extract_anthropic(text: str, detected_language: str | None) -> dict | None:
    from anthropic import AsyncAnthropic

    client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    tool = {"name": "file_report", "description": "Record the structured report.", "input_schema": _SCHEMA}
    try:
        msg = await client.messages.create(
            model=settings.ANTHROPIC_MODEL, max_tokens=700, system=_SYSTEM, tools=[tool],
            tool_choice={"type": "tool", "name": "file_report"},
            messages=[{"role": "user", "content": _user_prompt(text, detected_language)}],
        )
        return next((b.input for b in msg.content if getattr(b, "type", None) == "tool_use"), None)
    except Exception as e:
        log.warning("Anthropic extract failed (%s); using heuristic fallback", e)
        return None


def _finalize(data: dict, text: str, detected_language: str | None) -> Extracted:
    """Clean an LLM tool-call payload into an Extracted row."""
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
    missing = [
        f for f, present in [
            ("last_seen_landmark", "near" in t.lower() or "जवळ" in t),
            ("reporter_mobile", bool(phone)),
        ] if not present
    ]
    return Extracted(
        subject_age=int(age.group(1)) if age else None,
        language_spoken=LANG_NAME.get(detected_language or ""),
        reporter_mobile=phone.group(1).strip() if phone else None,
        physical_description=t[:200] or None,
        missing_fields=missing or ["subject_name", "last_seen_landmark"],
        confidence=0.4 if t else 0.0,
    )
