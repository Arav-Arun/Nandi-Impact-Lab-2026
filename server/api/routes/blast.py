"""
api.routes.blast - location-blast + subscriber management (M2).

Auto-mounted under /api/v1.

  GET  /api/v1/channels           which notify channels are live (keys present)
  POST /api/v1/subscribers        opt a recipient into zone blasts (any channel)
  GET  /api/v1/subscribers        list subscribers (optionally by zone)
  POST /api/v1/blast/zone         blast a free-text message to a zone (+ adjacent)
  POST /api/v1/blast/found/{id}   blast a found person's zone ("come identify")
"""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_session
from core.config import settings
from core.responses import ApiError, ok
from db.blast_models import Subscriber
from db.models import FoundReport, Registrant, Zone
from services import blast

router = APIRouter(tags=["blast"])


class SubscriberIn(BaseModel):
    channel: str                       # telegram | email
    address: str                       # chat id | email
    zone_id: Optional[uuid.UUID] = None
    name: Optional[str] = None
    language: Optional[str] = None


class ZoneBlastIn(BaseModel):
    zone_id: uuid.UUID
    message: str
    subject: str = "NANDI alert"
    channels: Optional[list[str]] = None   # restrict to a subset; default = all live


class ZoneChannelIn(BaseModel):
    telegram_channel: Optional[str] = None   # @username or -100… chat id; null to clear


def _join_link(channel: str | None) -> Optional[str]:
    """Public t.me join link for an @username channel (pilgrims scan this as a QR)."""
    return f"https://t.me/{channel.lstrip('@')}" if channel and channel.startswith("@") else None


@router.get("/channels")
async def channels():
    """Which channels will actually send (have keys) vs. log a no-op."""
    return ok(settings.enabled_channels)


@router.get("/zones")
async def list_zones(session: AsyncSession = Depends(get_session)):
    """All zones with the count of recipients reachable there (for the blast picker)."""
    zones = (await session.execute(select(Zone).order_by(Zone.venue, Zone.name))).scalars().all()

    sub_counts = dict((await session.execute(
        select(Subscriber.zone_id, func.count()).group_by(Subscriber.zone_id)
    )).all())
    reg_counts = dict((await session.execute(
        select(Registrant.zone_id, func.count()).group_by(Registrant.zone_id)
    )).all())

    return ok([
        {
            "id": str(z.id),
            "name": z.name,
            "venue": z.venue,
            "display_name_marathi": z.display_name_marathi,
            "color_code": z.color_code,
            "telegram_channel": z.telegram_channel,
            "join_link": _join_link(z.telegram_channel),
            "subscribers": int(sub_counts.get(z.id, 0)),
            "registrants": int(reg_counts.get(z.id, 0)),
            "reachable": int(sub_counts.get(z.id, 0)) + int(reg_counts.get(z.id, 0)),
        }
        for z in zones
    ])


@router.post("/zones/{zone_id}/channel")
async def set_zone_channel(zone_id: uuid.UUID, body: ZoneChannelIn, session: AsyncSession = Depends(get_session)):
    """Attach (or clear) a zone's public Telegram broadcast channel."""
    zone = await session.get(Zone, zone_id)
    if not zone:
        raise ApiError("ZONE_NOT_FOUND", "zone not found", 404)
    zone.telegram_channel = (body.telegram_channel or "").strip() or None
    return ok({"id": str(zone.id), "telegram_channel": zone.telegram_channel,
               "join_link": _join_link(zone.telegram_channel)})


@router.post("/subscribers")
async def add_subscriber(body: SubscriberIn, session: AsyncSession = Depends(get_session)):
    if body.channel not in {"telegram", "email"}:
        raise ApiError("BAD_CHANNEL", "channel must be telegram or email")
    sub = await blast.upsert_subscriber(
        session, channel=body.channel, address=body.address,
        zone_id=body.zone_id, name=body.name, language=body.language,
    )
    return ok({"id": str(sub.id), "channel": sub.channel})


@router.get("/subscribers")
async def list_subscribers(zone_id: Optional[uuid.UUID] = None, session: AsyncSession = Depends(get_session)):
    counts = (await session.execute(
        select(Subscriber.channel, func.count()).group_by(Subscriber.channel)
    )).all()
    by_channel = {c: int(n) for c, n in counts}
    q = select(Subscriber)
    if zone_id:
        q = q.where(Subscriber.zone_id == zone_id)
    rows = (await session.execute(q.limit(200))).scalars().all()
    return ok({
        "by_channel": by_channel,
        "total": sum(by_channel.values()),
        "subscribers": [{"channel": s.channel, "address": s.address,
                         "zone_id": str(s.zone_id) if s.zone_id else None, "name": s.name} for s in rows],
    })


@router.post("/blast/zone")
async def blast_zone(body: ZoneBlastIn, session: AsyncSession = Depends(get_session)):
    result = await blast.blast_zone(
        session, zone_id=body.zone_id, message=body.message,
        subject=body.subject, channels=body.channels,
    )
    return ok(result)


@router.post("/blast/found/{found_id}")
async def blast_found(found_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    """Operator action: alert a found person's zone so families come to identify them."""
    found = (await session.execute(select(FoundReport).where(FoundReport.id == found_id))).scalar_one_or_none()
    if not found:
        raise ApiError("FOUND_NOT_FOUND", "found report not found", 404)
    if not found.current_zone_id:
        raise ApiError("NO_ZONE", "found report has no zone to target", 400)
    zone = (await session.execute(select(Zone.name).where(Zone.id == found.current_zone_id))).scalar_one_or_none()
    who = found.name_if_known or "an unidentified person"
    msg = (f"NANDI: {who} ({found.physical_description}) is safe at {zone or 'a booth'}. "
           f"If someone in your group is missing, please come to identify them.")
    result = await blast.blast_zone(
        session, zone_id=found.current_zone_id, message=msg,
        subject="NANDI - found person in your area", report_id=found.id,
    )
    return ok(result)
