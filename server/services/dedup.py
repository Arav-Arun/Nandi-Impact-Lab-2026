"""
services.dedup — duplicate missing-report detection (Member 1).

Two families file the same lost child from two booths → two near-identical
missing reports. We FLAG these (never block — SoW: flag on create, not block) so
operators and the dashboard can collapse them, and so a candidate that is itself
a likely duplicate gets a small confidence penalty.

`flag_duplicates_on_intake` is meant to be called by M2's intake AFTER the SQL
row + graph node exist (see INTEGRATION.md). It is non-blocking: any failure is
logged and swallowed so a flaky graph never stops a report being filed.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from core.logging_utils import get_logger
from db.models import MissingReport
from schemas.common import EventType
from services.case_events import log_event
from services.neo4j_client import neo4j_client

log = get_logger(__name__)


async def find_duplicate_missing(
    *,
    current_id: uuid.UUID,
    subject_name: str | None,
    subject_age: int | None,
    subject_gender: str | None,
) -> tuple[int, list[str]]:
    """
    Return (count, ids) of other active missing reports that look like duplicates.

    Matching heuristic (SoW §6.1 duplicate check): same gender, age within ±5,
    and a fuzzy name overlap. Delegates to the Neo4j duplicate query; returns
    (0, []) when Neo4j is unavailable.
    """
    # Use the first token of the name as the fuzzy fragment (handles
    # "Ram Kumar" vs "Ram" entries). Empty fragment → name not constrained.
    fragment = (subject_name or "").strip().split(" ")[0] if subject_name else ""
    return await neo4j_client.duplicate_check(
        current_id=current_id,
        name_fragment=fragment,
        age=subject_age,
        gender=subject_gender,
    )


async def flag_duplicates_on_intake(session: AsyncSession, report: MissingReport) -> int:
    """
    Check a freshly-filed missing report for duplicates and log an audit event.

    Non-blocking and best-effort. Returns the duplicate count found (0 if none or
    on any error). Does NOT change the report's status — humans decide whether to
    actually merge; we only surface the suspicion.
    """
    try:
        count, ids = await find_duplicate_missing(
            current_id=report.id,
            subject_name=report.subject_name,
            subject_age=report.subject_age,
            subject_gender=report.subject_gender,
        )
        if count > 0:
            await log_event(
                session,
                report_id=report.id,
                event_type=EventType.duplicate_flagged,
                metadata={"duplicate_count": count, "duplicate_ids": ids},
            )
            log.info("flagged %d possible duplicate(s) for missing report %s", count, report.id)
        return count
    except Exception as exc:  # never block intake on a dedup hiccup
        log.warning("duplicate check failed for %s (%s) — skipping.", report.id, exc)
        return 0
