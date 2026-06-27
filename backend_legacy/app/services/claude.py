"""Claude — the AI brain of the intake layer.

Its core job: take a messy, free-form message in ANY Indian language (typed or
transcribed from voice) and return a clean, structured missing/found report.
Also drives the short conversational follow-ups used by the bots (Phase 2/3).

Falls back to a lightweight heuristic extractor when ANTHROPIC_API_KEY is absent.
"""
from __future__ import annotations

import json
import logging
import re

from app.config import settings
from app.models.schemas import ExtractedReport

log = logging.getLogger("nandi.claude")

AGE_BANDS = ["0-12", "13-17", "18-40", "41-60", "61-70", "71-80", "80+"]

_EXTRACT_TOOL = {
    "name": "file_report",
    "description": "Record the structured missing/found-person report extracted from the message.",
    "input_schema": {
        "type": "object",
        "properties": {
            "person_name": {"type": ["string", "null"], "description": "Name of the missing/found person, in the original script if given, else null."},
            "gender": {"type": ["string", "null"], "enum": ["Male", "Female", "Unknown", None]},
            "age_years": {"type": ["integer", "null"], "description": "Approximate age in years if stated."},
            "age_band": {"type": ["string", "null"], "enum": AGE_BANDS + [None]},
            "state": {"type": ["string", "null"], "description": "Home state of origin (English)."},
            "district": {"type": ["string", "null"]},
            "language": {"type": ["string", "null"], "description": "Primary language the person speaks (English name)."},
            "last_seen_location": {"type": ["string", "null"], "description": "Where last seen, as named in the message."},
            "physical_description": {"type": ["string", "null"], "description": "Clothing/appearance, in English for the operator."},
            "reporter_relation": {"type": ["string", "null"], "description": "Reporter's relation to the person, e.g. son, wife."},
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
    "details that aren't stated. Normalize gender and age_band to the allowed values; "
    "if only an age in years is given, also map it to the right band. Translate the "
    "physical description to clear English for the operator, but keep names in their "
    "original script. List genuinely-missing key fields (name, age, last_seen_location, "
    "physical_description, reporter_mobile) in missing_fields."
)


def _band_for(age: int | None) -> str | None:
    if age is None:
        return None
    for lo, hi, band in [(0, 12, "0-12"), (13, 17, "13-17"), (18, 40, "18-40"),
                         (41, 60, "41-60"), (61, 70, "61-70"), (71, 80, "71-80")]:
        if lo <= age <= hi:
            return band
    return "80+" if age > 80 else None


async def extract_report(text: str, channel: str = "web", detected_language: str | None = None) -> ExtractedReport:
    if not settings.claude_enabled:
        return _mock_extract(text, detected_language)

    from anthropic import AsyncAnthropic

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    hint = f"\n(Audio was auto-detected as language: {detected_language}.)" if detected_language else ""
    try:
        msg = await client.messages.create(
            model=settings.anthropic_model,
            max_tokens=700,
            system=_SYSTEM,
            tools=[_EXTRACT_TOOL],
            tool_choice={"type": "tool", "name": "file_report"},
            messages=[{"role": "user", "content": f"Report message:\n\"\"\"\n{text}\n\"\"\"{hint}"}],
        )
    except Exception as e:  # network / auth / rate-limit — degrade, don't drop the report
        log.warning("Claude extract failed (%s); using heuristic fallback", e)
        return _mock_extract(text, detected_language)

    data = next((b.input for b in msg.content if getattr(b, "type", None) == "tool_use"), {})
    if data.get("age_band") is None and data.get("age_years") is not None:
        data["age_band"] = _band_for(data["age_years"])
    if not data.get("language") and detected_language:
        from app.services.sarvam import LANG_NAME
        data["language"] = LANG_NAME.get(detected_language)
    return ExtractedReport(**{k: v for k, v in data.items() if k in ExtractedReport.model_fields})


async def summarize_for_operator(report: ExtractedReport) -> str:
    """One plain-English line for the operator feed."""
    who = report.person_name or "Unknown person"
    bits = [b for b in [report.gender, report.age_band, report.language] if b]
    where = f", last seen {report.last_seen_location}" if report.last_seen_location else ""
    return f"{who} ({', '.join(bits)}){where}."


# --- Heuristic fallback (no key) -------------------------------------------------
def _mock_extract(text: str, detected_language: str | None) -> ExtractedReport:
    t = text or ""
    phone = re.search(r"(\+?\d[\d\s-]{8,}\d)", t)
    age = re.search(r"(\d{1,3})\s*(?:वर्ष|साल|years|year|yrs|वयाचे|वर्षांचे)", t)
    age_years = int(age.group(1)) if age else None
    from app.services.sarvam import LANG_NAME
    lang = LANG_NAME.get(detected_language or "", None)
    missing = [f for f, ok in [("last_seen_location", "near" in t.lower() or "जवळ" in t),
                               ("reporter_mobile", bool(phone))] if not ok]
    return ExtractedReport(
        age_years=age_years,
        age_band=_band_for(age_years),
        language=lang,
        reporter_mobile=phone.group(1).strip() if phone else None,
        physical_description=t[:160] if t else None,
        missing_fields=missing or ["name", "last_seen_location"],
        confidence=0.4 if t else 0.0,
    )
