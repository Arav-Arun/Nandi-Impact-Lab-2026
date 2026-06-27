"""Intake + dashboard API.

Phase 0 surface:
  GET  /api/v1/stats            aggregate stats for the Overview
  GET  /api/v1/feed             recent reports for the Operator console
  POST /api/v1/intake/missing   file a structured report (web form)
  WS   /api/v1/ws/feed          live push of new reports

Phase 1 adds the voice/free-text path (/media/transcribe + Claude extraction).
"""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from app.api.responses import ok
from app.models.db_models import Report
from app.models.schemas import mask_phone
from app.realtime import hub
from app.services import pipeline, store
from app.services.pipeline import new_case_id, persist_and_broadcast

router = APIRouter(prefix="/api/v1", tags=["intake"])


class WebReportIn(BaseModel):
    report_type: str = "missing"
    person_name: Optional[str] = None
    gender: Optional[str] = None
    age_band: Optional[str] = None
    state: Optional[str] = None
    district: Optional[str] = None
    language: Optional[str] = None
    last_seen_location: Optional[str] = None
    physical_description: Optional[str] = None
    reporter_mobile: Optional[str] = None
    reporting_center: Optional[str] = None
    raw_text: Optional[str] = None
    detected_language: Optional[str] = None
    extraction_confidence: Optional[float] = None


class ExtractIn(BaseModel):
    text: str
    channel: str = "web"
    detected_language: Optional[str] = None


@router.post("/intake/extract")
async def intake_extract(body: ExtractIn):
    """Run Claude extraction on free text WITHOUT saving — the web form previews
    the structured result so the family can confirm/edit before filing."""
    extracted = await pipeline.extract_only(
        body.text, channel=body.channel, detected_language=body.detected_language
    )
    return ok(extracted.model_dump())


@router.get("/stats")
async def get_stats():
    stats = await store.compute_stats()
    return ok(stats.model_dump(mode="json"))


@router.get("/feed")
async def get_feed(limit: int = Query(40, le=200), channel: Optional[str] = None):
    items = await store.list_feed(limit=limit, channel=channel)
    return ok([i.model_dump(mode="json") for i in items])


@router.post("/intake/missing")
async def intake_missing(body: WebReportIn):
    report = Report(
        id=str(uuid.uuid4()),
        case_id=new_case_id(),
        report_type=body.report_type or "missing",
        channel="web",
        status="active",
        person_name=body.person_name,
        gender=body.gender,
        age_band=body.age_band,
        state=body.state,
        district=body.district,
        language=body.language,
        last_seen_location=body.last_seen_location,
        physical_description=body.physical_description,
        reporter_mobile=body.reporter_mobile,
        reporting_center=body.reporting_center or "Web intake",
        raw_text=body.raw_text,
        detected_language=body.detected_language,
        extraction_confidence=body.extraction_confidence,
    )
    saved = await persist_and_broadcast(report)
    return ok({"id": saved.id, "case_id": saved.case_id,
               "reporter_mobile_masked": mask_phone(saved.reporter_mobile)})


@router.websocket("/ws/feed")
async def ws_feed(ws: WebSocket):
    await hub.connect(ws)
    try:
        while True:
            # We don't expect inbound messages; this keeps the socket open.
            await ws.receive_text()
    except WebSocketDisconnect:
        await hub.disconnect(ws)
    except Exception:
        await hub.disconnect(ws)
