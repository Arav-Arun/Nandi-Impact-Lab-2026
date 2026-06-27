"""
db.models — SQLAlchemy 2.0 models for the NANDI PostgreSQL schema (SoW §5.1).

These tables are the source of truth for the whole system. Member 1 owns this
file; the other members read from / write to these tables but should not change
the schema without a heads-up (every change ripples into the Alembic migration,
the embedding dim, and the HNSW index — SoW §12.5).

Conventions (SoW §12.4 / §12.5):
  • Every primary key is a UUID (no integer auto-increment) so offline
    booth-generated ids never collide with server ids on sync.
  • Text embedding columns are vector(1024) — multilingual-e5-large output dim.
  • Face embedding columns are vector(512) — InsightFace buffalo_l (ArcFace).
    NOTE: face_embedding is a Member-1 extension beyond the SoW §5.1 listing; it
    is required by the photo re-ranking step (SoW §6) which has nowhere else to
    store a face vector. It is nullable — photos are optional everywhere.

The HNSW indexes, the partial `status='active'` index, and the
`zone_case_summary` materialized view are created in the Alembic migration
(raw SQL), because SQLAlchemy cannot express HNSW opclasses cleanly.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from geoalchemy2 import Geometry
from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.config import settings
from db.base import Base

# Embedding dimensions are read from settings so they stay in lock-step with the
# model config and the migration. Changing these requires re-indexing (SoW §12.5).
TEXT_DIM = settings.EMBEDDING_DIM        # 1024 — multilingual-e5-large
FACE_DIM = settings.FACE_EMBEDDING_DIM   # 512  — InsightFace buffalo_l


def _uuid_pk() -> Mapped[uuid.UUID]:
    """A UUID primary key column with a client-side default (works offline too)."""
    return mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Zone geography
# ─────────────────────────────────────────────────────────────────────────────
class Zone(Base):
    __tablename__ = "zones"

    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(Text, nullable=False)            # "Ramkund Zone"
    venue: Mapped[str] = mapped_column(Text, nullable=False)           # "Nashik" | "Trimbakeshwar"
    # PostGIS polygon (SRID 4326 / WGS84). Nullable so seed data can omit geometry.
    boundary: Mapped[object | None] = mapped_column(
        Geometry(geometry_type="POLYGON", srid=4326), nullable=True
    )
    color_code: Mapped[str] = mapped_column(Text, nullable=False)      # wristband colour hex
    display_name_marathi: Mapped[str] = mapped_column(Text, nullable=False)

    booths: Mapped[list["Booth"]] = relationship(back_populates="zone")


# ─────────────────────────────────────────────────────────────────────────────
# Booth locations
# ─────────────────────────────────────────────────────────────────────────────
class Booth(Base):
    __tablename__ = "booths"

    id: Mapped[uuid.UUID] = _uuid_pk()
    zone_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("zones.id"), nullable=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)            # "Milap Sthal – Neela Kamal"
    latitude: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    zone: Mapped[Zone | None] = relationship(back_populates="booths")


# ─────────────────────────────────────────────────────────────────────────────
# Travel groups (bus / temple / village groups) — group identity is crucial
# ─────────────────────────────────────────────────────────────────────────────
class Group(Base):
    __tablename__ = "groups"

    id: Mapped[uuid.UUID] = _uuid_pk()
    origin_city: Mapped[str | None] = mapped_column(Text, nullable=True)
    origin_state: Mapped[str | None] = mapped_column(Text, nullable=True)
    entry_point: Mapped[str | None] = mapped_column(Text, nullable=True)
    leader_phone: Mapped[str | None] = mapped_column(Text, nullable=True)


# ─────────────────────────────────────────────────────────────────────────────
# Phone registrations via missed-call IVR (target list for SMS blasts)
# ─────────────────────────────────────────────────────────────────────────────
class Registrant(Base):
    __tablename__ = "registrants"

    phone: Mapped[str] = mapped_column(Text, primary_key=True)
    zone_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("zones.id"), nullable=True)
    entry_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    name: Mapped[str | None] = mapped_column(Text, nullable=True)
    group_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("groups.id"), nullable=True)


# ─────────────────────────────────────────────────────────────────────────────
# Missing person reports (filed by family)
# ─────────────────────────────────────────────────────────────────────────────
class MissingReport(Base):
    __tablename__ = "missing_reports"

    id: Mapped[uuid.UUID] = _uuid_pk()
    filed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    filed_by_phone: Mapped[str] = mapped_column(Text, nullable=False)
    subject_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    subject_age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    subject_gender: Mapped[str | None] = mapped_column(String(16), nullable=True)  # male|female|unknown
    physical_description: Mapped[str] = mapped_column(Text, nullable=False)        # freeform, any language
    last_seen_zone_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("zones.id"), nullable=True
    )
    last_seen_landmark: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_seen_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    photo_url: Mapped[str | None] = mapped_column(Text, nullable=True)             # S3 key, optional
    language_spoken: Mapped[str | None] = mapped_column(Text, nullable=True)
    origin_city: Mapped[str | None] = mapped_column(Text, nullable=True)
    # active | matched | closed | duplicate
    status: Mapped[str] = mapped_column(String(16), default="active", server_default="active")
    matched_found_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_by_booth_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("booths.id"), nullable=True
    )
    # Text embedding of `physical_description` (passage). 1024-dim. HNSW indexed.
    embedding: Mapped[list[float] | None] = mapped_column(Vector(TEXT_DIM), nullable=True)
    # Face embedding from photo (512-dim, InsightFace). Optional, used for re-rank.
    face_embedding: Mapped[list[float] | None] = mapped_column(Vector(FACE_DIM), nullable=True)


# ─────────────────────────────────────────────────────────────────────────────
# Found person reports (registered at booths)
# ─────────────────────────────────────────────────────────────────────────────
class FoundReport(Base):
    __tablename__ = "found_reports"

    id: Mapped[uuid.UUID] = _uuid_pk()
    found_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    registered_at_booth: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("booths.id"), nullable=True
    )
    name_if_known: Mapped[str | None] = mapped_column(Text, nullable=True)
    approximate_age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(16), nullable=True)
    physical_description: Mapped[str] = mapped_column(Text, nullable=False)
    current_zone_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("zones.id"), nullable=True)
    photo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    language_spoken: Mapped[str | None] = mapped_column(Text, nullable=True)
    apparent_city_origin: Mapped[str | None] = mapped_column(Text, nullable=True)
    # unmatched | matched | closed
    status: Mapped[str] = mapped_column(String(16), default="unmatched", server_default="unmatched")
    matched_report_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("missing_reports.id"), nullable=True
    )
    operator_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(TEXT_DIM), nullable=True)
    face_embedding: Mapped[list[float] | None] = mapped_column(Vector(FACE_DIM), nullable=True)


# ─────────────────────────────────────────────────────────────────────────────
# Audit trail — every state change is logged here (SoW §5.1 case_events)
# ─────────────────────────────────────────────────────────────────────────────
class CaseEvent(Base):
    __tablename__ = "case_events"

    id: Mapped[uuid.UUID] = _uuid_pk()
    # report_id may reference either a missing_report or a found_report id, so it
    # is intentionally NOT a FK (polymorphic). event_type disambiguates.
    report_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    # filed | matched | blast_zone_sent | blast_event_sent | closed |
    # duplicate_flagged | operator_rejected | escalated_to_police
    event_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    event_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    booth_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("booths.id"), nullable=True)
    operator_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    event_metadata: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
