"""The shared intake funnel.

Every channel (web form, Telegram, WhatsApp) produces an `IntakeMessage`; this
module turns it into a stored, broadcast `Report`:

    IntakeMessage → (Sarvam STT if audio) → (Claude extraction) → Report → store + WS

Channels are thin adapters; this is the one brain they all share.
"""
from __future__ import annotations

import logging
import random
import uuid

import httpx

from app.models.db_models import Report
from app.models.schemas import ExtractedReport, IntakeMessage
from app.realtime import hub
from app.services import claude, sarvam, store

log = logging.getLogger("nandi.pipeline")


def new_case_id() -> str:
    return f"KMP-2027-{random.randint(0, 99999):05d}"


async def persist_and_broadcast(report: Report) -> Report:
    """Single funnel exit: store the report, then push it live to all clients."""
    saved = await store.add_report(report)
    out = store.to_out(saved)
    await hub.broadcast("report.new", out.model_dump(mode="json"))
    log.info("report.new  channel=%s case=%s lang=%s", saved.channel, saved.case_id, saved.detected_language)
    return saved


def build_report(
    extracted: ExtractedReport,
    *,
    channel: str,
    report_type: str = "missing",
    raw_text: str | None = None,
    detected_language: str | None = None,
    reporter_mobile: str | None = None,
) -> Report:
    return Report(
        id=str(uuid.uuid4()),
        case_id=new_case_id(),
        report_type=report_type,
        channel=channel,
        status="active",
        person_name=extracted.person_name,
        gender=extracted.gender,
        age_band=extracted.age_band,
        state=extracted.state,
        district=extracted.district,
        language=extracted.language,
        last_seen_location=extracted.last_seen_location,
        physical_description=extracted.physical_description,
        reporter_mobile=reporter_mobile or extracted.reporter_mobile,
        reporting_center=f"{channel.title()} intake",
        raw_text=raw_text,
        detected_language=detected_language,
        extraction_confidence=extracted.confidence,
        extra=extracted.model_dump(),
    )


async def _download(url: str, auth: tuple[str, str] | None = None) -> tuple[bytes, str]:
    async with httpx.AsyncClient(timeout=45.0, follow_redirects=True) as client:
        r = await client.get(url, auth=auth)
        r.raise_for_status()
        return r.content, r.headers.get("content-type", "audio/ogg")


async def transcribe(audio: bytes, filename: str, content_type: str) -> dict:
    return await sarvam.stt(audio, filename=filename, content_type=content_type)


async def extract_only(text: str, channel: str = "web", detected_language: str | None = None) -> ExtractedReport:
    """Run extraction WITHOUT saving — lets the web form preview/confirm first."""
    return await claude.extract_report(text, channel=channel, detected_language=detected_language)


async def ingest(msg: IntakeMessage, audio_auth: tuple[str, str] | None = None) -> Report:
    """Full path used by the bots: transcribe (if audio) → extract → store → broadcast."""
    text = msg.text or ""
    detected_language = msg.language_hint

    if msg.audio_url:
        audio, ctype = await _download(msg.audio_url, auth=audio_auth)
        result = await sarvam.stt(audio, filename="voice.ogg", content_type=ctype)
        text = (text + " " + result["transcript"]).strip()
        detected_language = result.get("language_code") or detected_language

    extracted = await claude.extract_report(text, channel=msg.channel, detected_language=detected_language)
    report = build_report(
        extracted,
        channel=msg.channel,
        report_type=msg.report_type,
        raw_text=text or None,
        detected_language=detected_language,
        reporter_mobile=msg.reporter_mobile,
    )
    return await persist_and_broadcast(report)
