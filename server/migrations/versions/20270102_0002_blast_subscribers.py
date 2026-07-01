"""blast subscribers - multi-channel location-blast recipients (M2)

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-27
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "subscribers",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("channel", sa.String(length=16), nullable=False),
        sa.Column("address", sa.Text(), nullable=False),
        sa.Column("zone_id", UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("language", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["zone_id"], ["zones.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("channel", "address", name="uq_subscriber_channel_address"),
    )
    op.create_index("ix_subscribers_channel", "subscribers", ["channel"])
    op.create_index("ix_subscribers_zone_id", "subscribers", ["zone_id"])


def downgrade() -> None:
    op.drop_index("ix_subscribers_zone_id", table_name="subscribers")
    op.drop_index("ix_subscribers_channel", table_name="subscribers")
    op.drop_table("subscribers")
