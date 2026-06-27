"""
services.blast — location-based multi-channel blast + escalation (M2).

Given a zone, gather everyone reachable there (opt-in `subscribers` across SMS /
WhatsApp / Telegram / Email, plus the IVR `registrants` phone list), optionally
widen to graph-adjacent zones, and fan the message out via services.notify. Every
blast writes a `blast_zone_sent` audit event (SoW §5.1) through the shared writer.

Escalation timeline (SoW): a still-open report past T+24h triggers a zone re-blast;
past T+72h it is escalated to police. The cadence is driven by scripts/blast_worker.py.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.logging_utils import get_logger
from db.blast_models import Subscriber
from db.models import CaseEvent, MissingReport, Registrant
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
    """Add or update a blast subscriber (idempotent on channel+address)."""
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


async def resolve_recipients(session: AsyncSession, zone_ids: set[uuid.UUID]) -> dict[str, list[str]]:
    """Addresses to reach in these zones, grouped by channel (deduplicated)."""
    out: dict[str, list[str]] = defaultdict(list)
    if not zone_ids:
        return out
    subs = (await session.execute(
        select(Subscriber.channel, Subscriber.address).where(Subscriber.zone_id.in_(zone_ids))
    )).all()
    for channel, address in subs:
        out[channel].append(address)
    regs = (await session.execute(
        select(Registrant.phone).where(Registrant.zone_id.in_(zone_ids))
    )).all()
    for (phone,) in regs:
        out["sms"].append(phone)
    return {ch: list(dict.fromkeys(addrs)) for ch, addrs in out.items()}


async def blast_zone(
    session: AsyncSession, *,
    zone_id: uuid.UUID,
    message: str,
    subject: str = "NANDI alert",
    channels: list[str] | None = None,
    report_id: uuid.UUID | None = None,
    event_type: EventType = EventType.blast_zone_sent,
) -> dict:
    """Fan `message` out to everyone in `zone_id` (+ adjacent zones if enabled)."""
    zone_ids = {zone_id}
    if settings.BLAST_INCLUDE_ADJACENT:
        zone_ids |= await adjacent_zone_ids(zone_id)

    recipients = await resolve_recipients(session, zone_ids)
    allowed = set(channels) if channels else None

    summary: dict[str, dict] = {}
    for channel, addresses in recipients.items():
        if allowed and channel not in allowed:
            continue
        sent = 0
        for addr in addresses:
            if await notify.send(channel, addr, message, subject=subject):
                sent += 1
        summary[channel] = {"targeted": len(addresses), "sent": sent}

    targeted = sum(v["targeted"] for v in summary.values())
    if report_id:
        await log_event(session, report_id=report_id, event_type=event_type, metadata={
            "zones": [str(z) for z in zone_ids],
            "channels": summary,
            "targeted": targeted,
        })
    log.info("blast zone=%s zones=%d targeted=%d sent=%s",
             zone_id, len(zone_ids), targeted, {k: v["sent"] for k, v in summary.items()})
    return {"zones": [str(z) for z in zone_ids], "channels": summary, "targeted": targeted}


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
