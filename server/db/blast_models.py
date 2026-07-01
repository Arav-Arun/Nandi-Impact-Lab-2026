"""
db.blast_models - Member 2's multi-channel blast recipient table.

Kept separate from db/models.py (Member 1) so the schema add is additive. A
Subscriber is anyone who can be reached for a location blast on one channel:
  channel ∈ sms | whatsapp | telegram | email
  address  = phone number | telegram chat id | email address
  zone_id  = the zone they're associated with (for location targeting)

Telegram/WhatsApp subscribers are auto-captured when they message the bot; SMS/
email subscribers and the IVR `registrants` list are added via /subscribers.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class Subscriber(Base):
    __tablename__ = "subscribers"
    __table_args__ = (UniqueConstraint("channel", "address", name="uq_subscriber_channel_address"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=func.gen_random_uuid()
    )
    channel: Mapped[str] = mapped_column(String(16), nullable=False, index=True)   # sms|whatsapp|telegram|email
    address: Mapped[str] = mapped_column(Text, nullable=False)
    zone_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("zones.id"), nullable=True, index=True)
    name: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
