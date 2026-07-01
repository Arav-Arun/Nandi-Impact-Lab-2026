"""
core.database - async SQLAlchemy engine + session factory (shared infra).

Every route/service that touches PostgreSQL depends on `get_session`:

    from fastapi import Depends
    from core.database import get_session

    @router.get("/x")
    async def handler(session: AsyncSession = Depends(get_session)):
        ...

The engine is created once at import time from settings.DATABASE_URL (asyncpg).
`db.base.Base` is the declarative base all models inherit from.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from core.config import settings

# echo=False keeps logs clean; flip to True locally to see emitted SQL.
# pool_pre_ping avoids handing out dead connections after a DB restart - handy
# on Shahi Snan days when the network flaps.
engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

# expire_on_commit=False so objects stay usable after commit (we often return
# fields from a just-committed row in the response envelope).
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency yielding a transactional session.

    Commits on success, rolls back on any exception, always closes. Handlers
    should NOT call session.commit() for the happy path unless they need an id
    mid-request - but committing explicitly is also safe (this just commits a
    no-op afterwards).
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
