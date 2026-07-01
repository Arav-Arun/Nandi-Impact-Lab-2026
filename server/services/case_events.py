"""
services.case_events - the single writer for the audit trail (Member 1).

Every state change in a case must leave a row in `case_events` (SoW §5.1). Route
this through `log_event` so the audit vocabulary and phone-masking stay
consistent. Other members (e.g. M2's blast worker logging `blast_zone_sent`)
should call this helper too rather than inserting rows by hand.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.logging_utils import get_logger, mask_phone
from db.models import CaseEvent
from schemas.common import EventType

log = get_logger(__name__)


async def log_event(
    session: AsyncSession,
    *,
    report_id: uuid.UUID,
    event_type: EventType | str,
    booth_id: uuid.UUID | None = None,
    operator_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    flush: bool = True,
) -> CaseEvent:
    """
    Append one audit event.

    Args:
        report_id: the missing OR found report id this event concerns.
        event_type: an EventType (or its string value).
        booth_id / operator_id: who/where, for attribution.
        metadata: arbitrary JSON context. Any key that looks like a phone number
            is masked here as a safety net (SoW §12.8 #2 - no plaintext phones).
        flush: flush to assign the id without committing (the request-level
            session commits at the end). Set False inside a larger unit of work.

    Returns the persisted (flushed) CaseEvent.
    """
    safe_metadata = _mask_phone_fields(metadata) if metadata else None

    event = CaseEvent(
        report_id=report_id,
        event_type=event_type.value if isinstance(event_type, EventType) else str(event_type),
        booth_id=booth_id,
        operator_id=operator_id,
        event_metadata=safe_metadata,
    )
    session.add(event)
    if flush:
        await session.flush()
    log.info(
        "case_event report=%s type=%s booth=%s",
        report_id,
        event.event_type,
        booth_id,
    )
    return event


# Keys whose values are masked before being written into the JSONB metadata.
_PHONE_KEYS = {"phone", "filer_phone", "filed_by_phone", "leader_phone", "to", "msisdn"}


def _mask_phone_fields(metadata: dict[str, Any]) -> dict[str, Any]:
    """Return a shallow copy of metadata with known phone-bearing keys masked."""
    out: dict[str, Any] = {}
    for key, value in metadata.items():
        if key in _PHONE_KEYS and isinstance(value, str):
            out[key] = mask_phone(value)
        else:
            out[key] = value
    return out
