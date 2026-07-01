"""
api.routes.intake - Member 2's intake endpoints (web form + structured filing).

Auto-mounted by api.main under /api/v1. Reuses M1 surfaces via
services.intake_pipeline (embedding, graph sync, dedup, audit, live broadcast).
Speaks the frontend's field contract (person_name / age_band / last_seen_location)
and maps it onto M1's report columns.

  POST /api/v1/intake/extract   preview structured fields from free text (no save)
  POST /api/v1/intake/missing   file a missing OR found report (web form)
  POST /api/v1/intake/found     register a found person (booth) → returns found_id
"""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_session
from core.responses import ok
from services import extraction, intake_pipeline
from services.intake_pipeline import age_band

router = APIRouter(prefix="/intake", tags=["intake"])

# Representative age for a band, so the matcher's ±-years window has a number.
_BAND_AGE = {"0-12": 6, "13-17": 15, "18-40": 29, "41-60": 50,
             "61-70": 65, "71-80": 75, "80+": 82}


def _age_from_band(band: str | None) -> int | None:
    return _BAND_AGE.get(band or "")


def _gender(g: str | None) -> str | None:
    g = (g or "").strip().lower()
    return g if g in {"male", "female", "unknown"} else None


def _case_id(report) -> str:
    return "K-" + str(report.id)[:8].upper()


class ExtractIn(BaseModel):
    text: str
    detected_language: Optional[str] = None


class WebReportIn(BaseModel):
    report_type: str = "missing"
    person_name: Optional[str] = None
    gender: Optional[str] = None
    age_band: Optional[str] = None
    language: Optional[str] = None
    last_seen_location: Optional[str] = None
    physical_description: Optional[str] = None
    reporter_mobile: Optional[str] = None
    state: Optional[str] = None
    district: Optional[str] = None
    raw_text: Optional[str] = None
    detected_language: Optional[str] = None
    photo_url: Optional[str] = None


class FoundIn(BaseModel):
    physical_description: Optional[str] = None
    name_if_known: Optional[str] = None
    approximate_age: Optional[int] = None
    gender: Optional[str] = None
    language_spoken: Optional[str] = None
    apparent_city_origin: Optional[str] = None
    current_zone_id: Optional[uuid.UUID] = None
    registered_at_booth: Optional[uuid.UUID] = None
    photo_url: Optional[str] = None


@router.post("/extract")
async def intake_extract(body: ExtractIn):
    """Preview the structured fields the form will file - never saves."""
    ex = await extraction.extract(body.text, detected_language=body.detected_language)
    return ok({
        "person_name": ex.subject_name,
        "gender": ex.subject_gender.capitalize() if ex.subject_gender else None,
        "age_band": age_band(ex.subject_age),
        "age_years": ex.subject_age,
        "state": None,
        "district": ex.origin_city,
        "language": ex.language_spoken,
        "last_seen_location": ex.last_seen_landmark,
        "physical_description": ex.physical_description,
        "reporter_relation": None,
        "reporter_mobile": ex.reporter_mobile,
        "missing_fields": ex.missing_fields,
        "confidence": ex.confidence,
    })


@router.post("/missing")
async def intake_missing(body: WebReportIn, session: AsyncSession = Depends(get_session)):
    desc = body.physical_description or body.raw_text
    origin = body.district or body.state
    if body.report_type == "found":
        report = await intake_pipeline.file_found(
            session,
            physical_description=desc,
            name_if_known=body.person_name,
            approximate_age=_age_from_band(body.age_band),
            gender=_gender(body.gender),
            language_spoken=body.language,
            apparent_city_origin=origin,
            photo_url=body.photo_url,
        )
    else:
        report = await intake_pipeline.file_missing(
            session,
            filed_by_phone=body.reporter_mobile,
            physical_description=desc,
            subject_name=body.person_name,
            subject_age=_age_from_band(body.age_band),
            subject_gender=_gender(body.gender),
            last_seen_landmark=body.last_seen_location,
            language_spoken=body.language,
            origin_city=origin,
            photo_url=body.photo_url,
            channel="web",
        )
    return ok({"id": str(report.id), "case_id": _case_id(report)})


@router.post("/found")
async def intake_found(body: FoundIn, session: AsyncSession = Depends(get_session)):
    report = await intake_pipeline.file_found(
        session,
        physical_description=body.physical_description,
        name_if_known=body.name_if_known,
        approximate_age=body.approximate_age,
        gender=_gender(body.gender),
        language_spoken=body.language_spoken,
        apparent_city_origin=body.apparent_city_origin,
        current_zone_id=body.current_zone_id,
        registered_at_booth=body.registered_at_booth,
        photo_url=body.photo_url,
    )
    return ok({"found_id": str(report.id), "case_id": _case_id(report), "status": report.status})
