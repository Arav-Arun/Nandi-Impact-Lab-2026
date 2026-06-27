"""
api.routes.match — Member 1's matching endpoints.

Routes (SoW §12.2):
    GET  /api/v1/match/{found_id}      → top candidates for the operator
    POST /api/v1/match/confirm         → operator confirms ONE candidate (safety gate)
    POST /api/v1/match/reject          → operator rejects all surfaced candidates
    POST /api/v1/internal/validate     → graph signals for a (missing, found) pair

The confirm endpoint is the ONLY path that triggers a notification, and only on
explicit human action (SoW §12.8 #1 — no auto-notification, ever).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_booth_id, get_session, require_internal_key
from core.logging_utils import get_logger, mask_phone
from core.responses import ApiError, ok
from db.models import Booth, FoundReport, MissingReport, Zone
from schemas.common import EventType
from schemas.match import (
    ConfirmRequest,
    ConfirmResponse,
    MatchListResponse,
    RejectRequest,
    RejectResponse,
    ValidateRequest,
    ValidateResponse,
)
from services import matcher, notify_bridge
from services.case_events import log_event
from services.neo4j_client import neo4j_client

log = get_logger(__name__)

# Two routers: a public booth-facing one and an internal-only one. api.main
# mounts both under /api/v1.
router = APIRouter(prefix="/match", tags=["match"])
internal_router = APIRouter(prefix="/internal", tags=["internal"])


# ─────────────────────────────────────────────────────────────────────────────
# GET /match/{found_id} — ranked candidates
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/{found_id}")
async def get_matches(found_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    """
    Return the top candidate missing reports for a registered found person.

    Each candidate carries its raw vector_score, the graph-adjusted confidence,
    the operator band (🟢/🟡/⚪), and plain-language reason labels. Candidates
    below the surface floor (< 0.60) are not returned (SoW §6.3).
    """
    try:
        candidates = await matcher.find_candidates(session, found_id)
    except matcher.FoundNotFoundError as exc:
        # Only a genuinely-missing found_report is a 404. Any other exception
        # propagates to the 500 handler instead of being mislabeled "not found".
        raise ApiError("FOUND_NOT_FOUND", str(exc), 404) from exc

    return ok(MatchListResponse(found_id=found_id, candidates=candidates))


# ─────────────────────────────────────────────────────────────────────────────
# POST /match/confirm — the human confirmation gate
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/confirm")
async def confirm_match(
    body: ConfirmRequest,
    session: AsyncSession = Depends(get_session),
    booth_id: uuid.UUID = Depends(get_booth_id),
):
    """
    Confirm that a found person is the subject of a missing report.

    Effects (all in one transaction):
      1. missing → matched (+ matched_found_id); found → matched (+ matched_report_id)
      2. write the MATCHED_TO edge in Neo4j (learns landmark patterns over time)
      3. audit `matched` event
      4. generate OTP + dispatch the Marathi match SMS to the filer (via M2)
    """
    missing = await session.get(MissingReport, body.missing_id)
    found = await session.get(FoundReport, body.found_id)

    if missing is None:
        raise ApiError("MISSING_NOT_FOUND", "missing report not found", 404)
    if found is None:
        raise ApiError("FOUND_NOT_FOUND", "found report not found", 404)

    # Idempotency / sanity: don't re-match an already-resolved pair to a new one.
    if missing.status == "matched" and missing.matched_found_id not in (None, found.id):
        raise ApiError("ALREADY_MATCHED", "missing report is already matched elsewhere", 409)
    if found.status == "matched" and found.matched_report_id not in (None, missing.id):
        raise ApiError("ALREADY_MATCHED", "found report is already matched elsewhere", 409)

    # 1) update both sides
    missing.status = "matched"
    missing.matched_found_id = found.id
    found.status = "matched"
    found.matched_report_id = missing.id

    # 2) graph edge (best-effort; degrades if Neo4j down)
    await neo4j_client.write_match_edge(missing.id, found.id)

    # 3) audit
    await log_event(
        session,
        report_id=missing.id,
        event_type=EventType.matched,
        booth_id=booth_id,
        operator_id=body.operator_id,
        metadata={"found_id": str(found.id)},
    )

    # 4) resolve the destination booth/zone for the SMS, then notify via M2.
    booth_name, zone_name = await _resolve_destination(session, found)
    case_id = str(missing.id)  # the family's case id; OTP is keyed on this
    otp = await notify_bridge.generate_otp(case_id)
    dispatched = await notify_bridge.send_match_sms(
        phone=missing.filed_by_phone,
        booth_name=booth_name or "NANDI Booth",
        zone_name=zone_name or "",
        otp=otp,
    )

    log.info(
        "match confirmed missing=%s found=%s filer=%s otp_dispatched=%s",
        missing.id,
        found.id,
        mask_phone(missing.filed_by_phone),
        dispatched,
    )

    return ok(
        ConfirmResponse(
            found_id=found.id,
            missing_id=missing.id,
            matched=True,
            otp_dispatched=dispatched,
            booth_name=booth_name,
            zone_name=zone_name,
            notify_detail=None if dispatched else "SMS not dispatched (notifier unavailable)",
        )
    )


# ─────────────────────────────────────────────────────────────────────────────
# POST /match/reject — operator rejected every surfaced candidate
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/reject")
async def reject_matches(
    body: RejectRequest,
    session: AsyncSession = Depends(get_session),
    booth_id: uuid.UUID = Depends(get_booth_id),
):
    """
    Record that none of the surfaced candidates matched this found person.

    The found report stays `unmatched` so M2's blast scheduler will escalate it on
    the normal T+24h / T+72h timeline. We only log the operator's decision.
    """
    found = await session.get(FoundReport, body.found_id)
    if found is None:
        raise ApiError("FOUND_NOT_FOUND", "found report not found", 404)

    # Keep it explicitly unmatched (it should already be, but be defensive).
    if found.status != "matched":
        found.status = "unmatched"

    await log_event(
        session,
        report_id=found.id,
        event_type=EventType.operator_rejected,
        booth_id=booth_id,
        operator_id=body.operator_id,
        metadata={"rejected_missing_ids": [str(i) for i in body.rejected_missing_ids]},
    )

    return ok(RejectResponse(found_id=found.id, status=found.status))


# ─────────────────────────────────────────────────────────────────────────────
# POST /internal/validate — graph signals (server-to-server only)
# ─────────────────────────────────────────────────────────────────────────────
@internal_router.post("/validate", dependencies=[Depends(require_internal_key)])
async def validate_pair(body: ValidateRequest, session: AsyncSession = Depends(get_session)):
    """
    Run the Neo4j validation checks for one (missing, found) pair.

    Returns the `graph_signals` dict consumed by the composite score. Guarded by
    X-Internal-Key — this is an internal step of the match pipeline, not a
    user-facing route.
    """
    signals = await matcher.graph_signals_for(
        session,
        missing_id=body.missing_id,
        found_id=body.found_id,
        filer_phone=body.filer_phone,
    )
    return ok(ValidateResponse(graph_signals=signals))


# ─────────────────────────────────────────────────────────────────────────────
# helpers
# ─────────────────────────────────────────────────────────────────────────────
async def _resolve_destination(
    session: AsyncSession, found: FoundReport
) -> tuple[str | None, str | None]:
    """
    Resolve the booth + zone name the family should travel to.

    The family goes to where the found person currently is: the booth they were
    registered at (falling back to the current zone if no booth is recorded).
    """
    booth_name: str | None = None
    zone_name: str | None = None

    if found.registered_at_booth:
        booth = await session.get(Booth, found.registered_at_booth)
        if booth is not None:
            booth_name = booth.name
            if booth.zone_id:
                zone = await session.get(Zone, booth.zone_id)
                zone_name = zone.name if zone else None

    if zone_name is None and found.current_zone_id:
        zone = await session.get(Zone, found.current_zone_id)
        zone_name = zone.name if zone else None

    return booth_name, zone_name
