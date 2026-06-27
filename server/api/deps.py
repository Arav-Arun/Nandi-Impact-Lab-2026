"""
api.deps — re-exports of the common FastAPI dependencies.

Importing from one place keeps route files tidy and gives the other members a
single, stable import path:

    from api.deps import get_session, get_neo4j, require_internal_key, get_booth_id
"""

from __future__ import annotations

from core.database import get_session
from core.redis_client import get_redis
from core.security import get_booth_id, require_internal_key
from services.neo4j_client import get_neo4j

__all__ = [
    "get_session",
    "get_redis",
    "get_neo4j",
    "get_booth_id",
    "require_internal_key",
]
