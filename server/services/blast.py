"""
services.blast - Kumbh-scale zone broadcast + escalation.

Reaching crores of pilgrims can't be done by fanning out to individually opted-in
recipients. So the mass channel is a **per-zone public Telegram channel** that
pilgrims join via a QR code at the booths: a broadcast posts ONE message to each
target zone's channel and reaches every member instantly. Email subscribers are
kept for registered families/officials (a bounded, direct list).

Escalation: a still-open report past T+24h triggers a zone re-broadcast; past
T+72h it escalates to police. Cadence lives in scripts/blast_worker.py.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.logging_utils import get_logger
from db.blast_models import Subscriber
from db.models import CaseEvent, MissingReport, Zone
from schemas.common import EventType
from services import notify
from services.case_events import log_event
from services.neo4j_client import neo4j_client

log = get_logger("nandi.blast")


async def adjacent_zone_ids(zone_id: uuid.UUID) -> set[uuid.UUID]:
    """Graph-adjacent zones (best-effort; empty if Neo4j is unavailable)."""
    try:
        rows = await neo4j_client._run(
            "MATCH (z:Zone {id:$id})-[:ADJACENT_TO]-(a:Zone) RETURN a.id AS id",
            {"id": str(zone_id)},
        )
        return {uuid.UUID(r["id"]) for r in rows if r.get("id")}
    except Exception as exc:
        log.debug("adjacency lookup failed for %s (%s)", zone_id, exc)
        return set()


async def upsert_subscriber(
    session: AsyncSession, *, channel: str, address: str,
    zone_id: uuid.UUID | None = None, name: str | None = None, language: str | None = None,
) -> Subscriber:
    """Add or update a direct subscriber (idempotent on channel+address)."""
    existing = (await session.execute(
        select(Subscriber).where(Subscriber.channel == channel, Subscriber.address == address)
    )).scalar_one_or_none()
    if existing:
        if zone_id:
            existing.zone_id = zone_id
        if name:
            existing.name = name
        if language:
            existing.language = language
        return existing
    sub = Subscriber(channel=channel, address=address, zone_id=zone_id, name=name, language=language)
    session.add(sub)
    await session.flush()
    return sub


async def _zone_emails(session: AsyncSession, zone_ids: set[uuid.UUID]) -> list[str]:
    """Deduplicated email addresses opted into these zones (direct family/official list)."""
    if not zone_ids:
        return []
    rows = (await session.execute(
        select(Subscriber.address).where(
            Subscriber.channel == "email", Subscriber.zone_id.in_(zone_ids)
        )
    )).scalars().all()
    return list(dict.fromkeys(rows))


async def blast_zone(
    session: AsyncSession, *,
    zone_id: uuid.UUID,
    message: str,
    subject: str = "NANDI alert",
    channels: list[str] | None = None,
    report_id: uuid.UUID | None = None,
    event_type: EventType = EventType.blast_zone_sent,
) -> dict:
    """
    Broadcast `message` across `zone_id` (+ adjacent zones if enabled).

    Posts once to each target zone's Telegram channel (mass reach) and emails the
    zone's registered recipients. Returns a summary with the estimated reach.
    """
    zone_ids = {zone_id}
    if settings.BLAST_INCLUDE_ADJACENT:
        zone_ids |= await adjacent_zone_ids(zone_id)

    allow = set(channels) if channels else None
    zones = (await session.execute(select(Zone).where(Zone.id.in_(zone_ids)))).scalars().all()

    # 1) Telegram channels - one post per zone reaches every joined member.
    posts: list[dict] = []
    reach = 0
    if not allow or "telegram" in allow:
        for z in zones:
            if not z.telegram_channel:
                continue
            sent = await notify.send_telegram(z.telegram_channel, f"{subject}\n\n{message}")
            members = await notify.telegram_member_count(z.telegram_channel)
            reach += members or 0
            posts.append({"zone": z.name, "channel": z.telegram_channel,
                          "sent": sent, "members": members})

    # 2) Email - bounded direct list of registered families/officials.
    email_summary = {"targeted": 0, "sent": 0}
    if not allow or "email" in allow:
        emails = await _zone_emails(session, zone_ids)
        email_summary["targeted"] = len(emails)
        for addr in emails:
            if await notify.send_email(addr, message, subject=subject):
                email_summary["sent"] += 1
        reach += len(emails)

    result = {
        "zones": [str(z) for z in zone_ids],
        "channels_posted": posts,
        "email": email_summary,
        "targeted": reach,            # estimated total people reached
    }
    if report_id:
        await log_event(session, report_id=report_id, event_type=event_type, metadata=result)
    log.info("broadcast zone=%s zones=%d channels=%d emails=%d reach≈%d",
             zone_id, len(zone_ids), len(posts), email_summary["targeted"], reach)
    return result


async def open_reports_past(session: AsyncSession, *, hours: int, without_event: EventType) -> list[MissingReport]:
    """Active missing reports older than `hours` that have a zone and no `without_event` yet."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    already = select(CaseEvent.report_id).where(CaseEvent.event_type == without_event.value)
    return (await session.execute(
        select(MissingReport).where(
            MissingReport.status == "active",
            MissingReport.filed_at < cutoff,
            MissingReport.last_seen_zone_id.is_not(None),
            MissingReport.id.not_in(already),
        )
    )).scalars().all()
