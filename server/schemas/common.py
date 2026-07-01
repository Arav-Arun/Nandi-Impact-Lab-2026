"""
schemas.common - enums and small shared types used across the API contract.

Keeping these here (rather than scattering string literals) means M2's intake,
M3's dashboard, and M1's matcher all agree on the exact allowed values.
"""

from __future__ import annotations

from enum import Enum


class Gender(str, Enum):
    """SoW §5.1 - subject_gender / gender values."""

    male = "male"
    female = "female"
    unknown = "unknown"


class MissingStatus(str, Enum):
    """missing_reports.status lifecycle."""

    active = "active"
    matched = "matched"      # operator confirmed a candidate; family being notified
    reunited = "reunited"    # family verified the OTP at the booth (loop closed)
    closed = "closed"
    duplicate = "duplicate"


class FoundStatus(str, Enum):
    """found_reports.status lifecycle."""

    unmatched = "unmatched"
    matched = "matched"
    reunited = "reunited"
    closed = "closed"


class EventType(str, Enum):
    """case_events.event_type - the full audit vocabulary (SoW §5.1)."""

    filed = "filed"
    matched = "matched"
    reunited = "reunited"
    blast_zone_sent = "blast_zone_sent"
    blast_event_sent = "blast_event_sent"
    closed = "closed"
    duplicate_flagged = "duplicate_flagged"
    operator_rejected = "operator_rejected"
    escalated_to_police = "escalated_to_police"


class ConfidenceBand(str, Enum):
    """Operator-facing confidence buckets (SoW §6.3)."""

    high = "high"          # ≥ 0.90  🟢
    probable = "probable"  # 0.75–0.89  🟡
    possible = "possible"  # 0.60–0.74  ⚪
    # < 0.60 is never surfaced, so there is no band for it.
