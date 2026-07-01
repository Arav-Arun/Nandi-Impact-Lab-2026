"""
services.intake_pipeline - the one funnel every intake channel shares (M2).

Web form, Telegram, and WhatsApp all end here. Given already-extracted fields it:
  1. writes the SQL row (MissingReport / FoundReport) with a passage embedding,
  2. MERGEs the graph node (services.neo4j_client - for the validation queries),
  3. flags likely duplicates (services.dedup - non-blocking),
  4. logs a `filed` audit event (services.case_events),
  5. broadcasts a feed item to live dashboard sockets (services.hub).

Steps 2–5 are best-effort and never block a report being filed. All M1 surfaces
are used per INTEGRATION.md §3.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.logging_utils import get_logger, mask_phone
from db.models import Booth, FoundReport, MissingReport, Zone
from schemas.common import EventType
from services.case_events import log_event
from services.dedup import flag_duplicates_on_intake
from services.embedding import embed_text
from services.hub import hub
from services.neo4j_client import neo4j_client

log = get_logger("nandi.intake")


_AGE_BANDS = [(0, 12, "0-12"), (13, 17, "13-17"), (18, 40, "18-40"),
              (41, 60, "41-60"), (61, 70, "61-70"), (71, 80, "71-80")]


def age_band(age: int | None) -> str | None:
    if age is None:
        return None
    for lo, hi, band in _AGE_BANDS:
        if lo <= age <= hi:
            return band
    return "80+" if age > 80 else None


def is_priority(age: int | None, status: str) -> bool:
    """Vulnerable-person flag: an open case for a child (≤12) or elder (≥70).

    Learnt from past-Kumbh lapses - the most at-risk (small children, frail
    elders) must jump the queue and can be broadcast immediately, not after the
    normal 24h escalation window.
    """
    if status in ("reunited", "closed"):
        return False
    return age is not None and (age <= 12 or age >= 70)


async def resolve_zone_by_text(session: AsyncSession, text: str | None) -> "uuid.UUID | None":
    """Best-effort map a landmark/place string to a seeded zone id (for blasts)."""
    if not text:
        return None
    kw = text.strip().split()[0]
    if len(kw) < 3:
        return None
    zid = (await session.execute(
        select(Zone.id).where(Zone.name.ilike(f"%{kw}%")).limit(1)
    )).scalar_one_or_none()
    if zid:
        return zid
    return (await session.execute(
        select(Booth.zone_id).where(Booth.name.ilike(f"%{kw}%"), Booth.zone_id.is_not(None)).limit(1)
    )).scalar_one_or_none()


def feed_item(report: MissingReport | FoundReport, kind: str, channel: str = "web") -> dict:
    """Feed row shape shared by the dashboard, the operator console, and the live
    socket. Mirrors the frontend Report contract so one shape renders everywhere."""
    if isinstance(report, MissingReport):
        name, age, gender = report.subject_name, report.subject_age, report.subject_gender
        where, origin, at = report.last_seen_landmark, report.origin_city, report.filed_at
        phone = report.filed_by_phone
    else:
        name, age, gender = report.name_if_known, report.approximate_age, report.gender
        where, origin, at = None, report.apparent_city_origin, report.found_at
        phone = None
    masked = None
    if phone and not str(phone).startswith("tg:"):
        masked = mask_phone(phone)
    return {
        "id": str(report.id),
        "case_id": "K-" + str(report.id)[:8].upper(),
        "report_type": kind,                       # "missing" | "found"
        "channel": channel,
        "status": report.status,
        "reported_at": (at or datetime.now(timezone.utc)).isoformat(),
        "person_name": name,
        "gender": gender.capitalize() if gender else None,
        "age_band": age_band(age),
        "state": None,
        "district": origin,
        "language": report.language_spoken,
        "last_seen_location": where,
        "physical_description": report.physical_description,
        "reporter_mobile_masked": masked,
        "reporting_center": f"{channel.title()} intake",
        "is_duplicate_report": False,
        "detected_language": report.language_spoken,
        "extraction_confidence": None,
        "photo_url": report.photo_url,
        "priority": is_priority(age, report.status),
    }


async def file_missing(
    session: AsyncSession,
    *,
    filed_by_phone: str | None,
    physical_description: str | None,
    subject_name: str | None = None,
    subject_age: int | None = None,
    subject_gender: str | None = None,
    last_seen_landmark: str | None = None,
    last_seen_zone_id: uuid.UUID | None = None,
    last_seen_time: datetime | None = None,
    language_spoken: str | None = None,
    origin_city: str | None = None,
    photo_url: str | None = None,
    channel: str = "web",
) -> MissingReport:
    desc = (physical_description or "").strip() or "-"
    if last_seen_zone_id is None:
        last_seen_zone_id = await resolve_zone_by_text(session, last_seen_landmark)

    report = MissingReport(
        filed_by_phone=(filed_by_phone or "unknown").strip() or "unknown",
        physical_description=desc,
        subject_name=subject_name,
        subject_age=subject_age,
        subject_gender=subject_gender,
        last_seen_landmark=last_seen_landmark,
        last_seen_zone_id=last_seen_zone_id,
        last_seen_time=last_seen_time,
        language_spoken=language_spoken,
        origin_city=origin_city,
        photo_url=photo_url,
        status="active",
        embedding=embed_text(desc, kind="passage"),
    )
    session.add(report)
    await session.flush()  # assign id + server defaults (filed_at)

    await neo4j_client.sync_missing_report(
        report_id=report.id, filed_at=report.filed_at, status=report.status,
        subject_name=subject_name, subject_age=subject_age, subject_gender=subject_gender,
        origin_city=origin_city, language_spoken=language_spoken,
        last_seen_time=last_seen_time, last_seen_landmark=last_seen_landmark,
        last_seen_zone_id=last_seen_zone_id, booth_id=None, filer_phone=filed_by_phone,
    )
    await flag_duplicates_on_intake(session, report)
    await log_event(session, report_id=report.id, event_type=EventType.filed,
                    metadata={"channel": channel, "filed_by_phone": filed_by_phone})
    await hub.broadcast("report.new", feed_item(report, "missing", channel))
    log.info("missing filed id=%s channel=%s", report.id, channel)
    return report


async def file_found(
    session: AsyncSession,
    *,
    physical_description: str | None,
    name_if_known: str | None = None,
    approximate_age: int | None = None,
    gender: str | None = None,
    current_zone_id: uuid.UUID | None = None,
    registered_at_booth: uuid.UUID | None = None,
    language_spoken: str | None = None,
    apparent_city_origin: str | None = None,
    photo_url: str | None = None,
) -> FoundReport:
    desc = (physical_description or "").strip() or "-"
    if current_zone_id is None and registered_at_booth is not None:
        current_zone_id = (await session.execute(
            select(Booth.zone_id).where(Booth.id == registered_at_booth)
        )).scalar_one_or_none()

    report = FoundReport(
        physical_description=desc,
        name_if_known=name_if_known,
        approximate_age=approximate_age,
        gender=gender,
        current_zone_id=current_zone_id,
        registered_at_booth=registered_at_booth,
        language_spoken=language_spoken,
        apparent_city_origin=apparent_city_origin,
        photo_url=photo_url,
        status="unmatched",
        embedding=embed_text(desc, kind="passage"),
    )
    session.add(report)
    await session.flush()

    await neo4j_client.sync_found_report(
        report_id=report.id, found_at=report.found_at, status=report.status,
        name_if_known=name_if_known, approximate_age=approximate_age, gender=gender,
        apparent_city_origin=apparent_city_origin, language_spoken=language_spoken,
        booth_id=registered_at_booth, current_zone_id=current_zone_id,
    )
    await log_event(session, report_id=report.id, event_type=EventType.filed,
                    booth_id=registered_at_booth, metadata={"channel": "booth"})
    await hub.broadcast("report.new", feed_item(report, "found", "booth"))
    log.info("found filed id=%s", report.id)
    return report
