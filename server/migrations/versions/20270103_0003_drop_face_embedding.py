"""drop face_embedding columns - photo face-matching removed

The face-matching pipeline was never real: InsightFace/onnxruntime were never
installed, so embed_face returned deterministic hash stubs and the photo re-rank
had no semantic meaning. Photos remain (upload + Claude vision description feeds
the text embedding); only the fake face vectors are dropped.

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-01
"""

from __future__ import annotations

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE missing_reports DROP COLUMN IF EXISTS face_embedding")
    op.execute("ALTER TABLE found_reports  DROP COLUMN IF EXISTS face_embedding")


def downgrade() -> None:
    # 512 = former InsightFace buffalo_l (ArcFace) dimension.
    op.execute("ALTER TABLE missing_reports ADD COLUMN IF NOT EXISTS face_embedding vector(512)")
    op.execute("ALTER TABLE found_reports  ADD COLUMN IF NOT EXISTS face_embedding vector(512)")
