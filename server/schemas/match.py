"""
schemas.match — request/response models for the matching API (Member 1).

These are the exact shapes M2 (intake calls /match/{found_id} after registering a
found person) and M3 (booth PWA renders candidates) integrate against. The
payloads themselves live inside the standard envelope from core.responses, e.g.:

    { "data": <MatchListResponse>, "error": null, "timestamp": "..." }
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from schemas.common import ConfidenceBand


# ─────────────────────────────────────────────────────────────────────────────
# Graph validation (/internal/validate)
# ─────────────────────────────────────────────────────────────────────────────
class GraphSignals(BaseModel):
    """
    Boolean signals produced by the Neo4j validation queries (SoW §6.1).

    Keys map 1:1 to the modifier keys consumed by scoring.composite_confidence().
    Every field defaults to False so a partial / degraded Neo4j response still
    produces a valid signal set (graceful degradation — SoW §2 Golden Rule).
    """

    # Zone plausibility
    same_zone: bool = False
    adjacent_zone: bool = False
    same_venue: bool = False
    different_venue: bool = False
    # Origin
    same_city: bool = False
    same_state: bool = False
    # Temporal
    temporal_very_recent: bool = False
    temporal_same_day: bool = False
    temporal_stale: bool = False
    # Learned landmark flow pattern
    landmark_pattern_match: bool = False
    # Language (computed by the matcher from SQL records, merged in here)
    language_match: bool = False
    # Duplicate suspicion
    possible_duplicate: bool = False


class ValidateRequest(BaseModel):
    """Body for POST /internal/validate (internal key required)."""

    missing_id: uuid.UUID
    found_id: uuid.UUID
    filer_phone: str | None = Field(
        default=None,
        description="Phone of the family member who filed the missing report; "
        "enables the city/group-of-origin check.",
    )


class ValidateResponse(BaseModel):
    """Response for POST /internal/validate."""

    graph_signals: GraphSignals


# ─────────────────────────────────────────────────────────────────────────────
# Candidate listing (GET /match/{found_id})
# ─────────────────────────────────────────────────────────────────────────────
class MatchCandidate(BaseModel):
    """One ranked missing-report candidate shown to the booth operator."""

    missing_id: uuid.UUID
    subject_name: str | None = None
    subject_age: int | None = None
    subject_gender: str | None = None
    physical_description: str
    last_seen_landmark: str | None = None
    last_seen_zone_id: uuid.UUID | None = None
    filed_at: datetime
    photo_url: str | None = None
    origin_city: str | None = None

    # Scores: raw pgvector cosine similarity, the graph-adjusted final score, the
    # operator band, and the plain-language reason labels (SoW §6.2).
    vector_score: float = Field(..., description="raw pgvector cosine similarity 0..1")
    confidence: float = Field(..., description="composite score after graph modifiers 0..1")
    band: ConfidenceBand
    reasons: list[str] = Field(default_factory=list)


class MatchListResponse(BaseModel):
    """Response for GET /match/{found_id} — top candidates, best first."""

    found_id: uuid.UUID
    candidates: list[MatchCandidate]


# ─────────────────────────────────────────────────────────────────────────────
# Confirm / reject
# ─────────────────────────────────────────────────────────────────────────────
class ConfirmRequest(BaseModel):
    """
    Body for POST /match/confirm — the operator picked one candidate.

    Human confirmation is a safety contract (SoW §12.8 #1): the system NEVER
    auto-notifies; this endpoint is the only path that triggers a match SMS.
    """

    found_id: uuid.UUID
    missing_id: uuid.UUID
    operator_id: str | None = Field(default=None, description="logged in the audit trail")


class ConfirmResponse(BaseModel):
    """Response for POST /match/confirm."""

    found_id: uuid.UUID
    missing_id: uuid.UUID
    matched: bool = True
    otp_dispatched: bool = Field(
        ..., description="True if the match SMS+OTP was handed to M2's notifier"
    )
    booth_name: str | None = None
    zone_name: str | None = None
    notify_detail: str | None = Field(
        default=None, description="non-fatal note if notification could not be dispatched"
    )


class RejectRequest(BaseModel):
    """Body for POST /match/reject — operator rejected all surfaced candidates."""

    found_id: uuid.UUID
    operator_id: str | None = None
    rejected_missing_ids: list[uuid.UUID] = Field(
        default_factory=list,
        description="optional: the specific candidate ids shown, for the audit log",
    )


class RejectResponse(BaseModel):
    """Response for POST /match/reject."""

    found_id: uuid.UUID
    status: str = "unmatched"
