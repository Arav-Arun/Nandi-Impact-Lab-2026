"""
db.base — the declarative base for all SQLAlchemy models.

Alembic's `target_metadata` is `Base.metadata`. For autogenerate / metadata to
see every table, all model modules must be imported before metadata is read;
`migrations/env.py` imports `db.models` for exactly this reason.
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Common declarative base. All NANDI tables inherit from this."""

    pass
