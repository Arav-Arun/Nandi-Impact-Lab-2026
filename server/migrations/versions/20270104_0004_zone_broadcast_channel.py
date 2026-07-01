"""zone Telegram broadcast channels - reach a whole zone with one post

Kumbh-scale broadcast: instead of fanning a message to individually opted-in
subscribers (which cannot scale to crores of pilgrims), each zone gets a public
Telegram channel that pilgrims join via a QR code at the booths. Broadcasting to
a zone posts ONE message to its channel, reaching every member instantly. Email
subscribers remain for registered families/officials.

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-01
"""

from __future__ import annotations

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE zones ADD COLUMN IF NOT EXISTS telegram_channel TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE zones DROP COLUMN IF EXISTS telegram_channel")
