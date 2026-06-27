"""
tests.conftest — shared fixtures for the NANDI test suite (Member 1).

Two hard rules this file enforces so the suite is green with NO infrastructure:

  1. EMBEDDING_FALLBACK=1 is set *before* any app code is imported, so the
     deterministic stub embedder is always used (no torch / sentence-transformers
     / InsightFace download, fully reproducible vectors).

  2. DB-dependent tests SKIP cleanly when Postgres is not reachable. "Reachable"
     here means: we can actually open an asyncpg connection with the configured
     DATABASE_URL *and* the core tables exist. A bare open TCP port (e.g. some
     other Postgres with no `nandi` role/db) must NOT count as reachable, or the
     integration test would fail instead of skipping.

Usage in a test module:

    def test_needs_db(require_db):          # fixture forces a skip if no DB
        ...

    # or, for finer control:
    if not db_available():
        pytest.skip("no database")
"""

from __future__ import annotations

import asyncio
import os

# ── Rule 1: pin the stub embedder BEFORE importing anything that reads settings.
# core.config caches settings via lru_cache at import time, so this env var must
# win the race. We set it unconditionally (the suite is designed around the stub).
os.environ.setdefault("EMBEDDING_FALLBACK", "1")
os.environ["EMBEDDING_FALLBACK"] = "1"

import pytest  # noqa: E402

from core.config import settings  # noqa: E402  (import after env is pinned)

# ── Rule 3: use NullPool for the global async engine DURING TESTS ONLY ────────
# The app creates ONE global async engine at import; its pooled asyncpg
# connections get bound to whichever event loop first used them. Across tests
# (pytest-asyncio's per-test loops + TestClient's own loop) a pooled connection
# from a defunct loop triggers "RuntimeError: Event loop is closed" on cleanup.
# NullPool opens+closes a connection per checkout (always on the current loop),
# so nothing persists across loops. This patches only the test process — the app
# and prod config are untouched. get_session() reads these module globals at call
# time, so rebinding them here is picked up by every route/fixture.
import core.database as _db  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402

_db.engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool, pool_pre_ping=True)
_db.AsyncSessionLocal = async_sessionmaker(
    bind=_db.engine, expire_on_commit=False, autoflush=False
)


# ─────────────────────────────────────────────────────────────────────────────
# Postgres reachability probe (cached for the whole session)
# ─────────────────────────────────────────────────────────────────────────────
_DB_PROBE: tuple[bool, str] | None = None


async def _probe_db_async() -> tuple[bool, str]:
    """
    Try a real connection + a trivial query against the core tables.

    Returns (available, reason). `available` is True only when we can connect
    AND the expected schema is present, so a stray Postgres on the same port
    (wrong role / db / no migrations) reports as *unavailable* and tests skip.
    """
    try:
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import create_async_engine
    except Exception as exc:  # pragma: no cover - deps guaranteed in the venv
        return False, f"sqlalchemy import failed: {exc}"

    engine = create_async_engine(settings.DATABASE_URL)
    try:
        async with engine.connect() as conn:
            # Connectivity check.
            await conn.execute(text("SELECT 1"))
            # Schema check — the integration test needs these tables to exist.
            await conn.execute(text("SELECT 1 FROM found_reports LIMIT 1"))
            await conn.execute(text("SELECT 1 FROM missing_reports LIMIT 1"))
        return True, "ok"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {str(exc)[:200]}"
    finally:
        await engine.dispose()


def db_available() -> tuple[bool, str]:
    """Synchronous, session-cached wrapper over the async probe."""
    global _DB_PROBE
    if _DB_PROBE is None:
        try:
            _DB_PROBE = asyncio.run(_probe_db_async())
        except Exception as exc:  # event-loop edge cases → treat as unavailable
            _DB_PROBE = (False, f"probe error: {exc}")
    return _DB_PROBE


# ─────────────────────────────────────────────────────────────────────────────
# Markers + collection hook
# ─────────────────────────────────────────────────────────────────────────────
def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "requires_db: test needs a reachable, migrated Postgres; skipped otherwise.",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Auto-skip every @requires_db test when no usable database is present."""
    available, reason = db_available()
    if available:
        return
    skip_db = pytest.mark.skip(reason=f"no usable Postgres (DATABASE_URL): {reason}")
    for item in items:
        if "requires_db" in item.keywords:
            item.add_marker(skip_db)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────
@pytest.fixture(scope="session")
def db_status() -> tuple[bool, str]:
    """(available, reason) tuple for tests that want to branch on DB presence."""
    return db_available()


@pytest.fixture
def require_db(db_status: tuple[bool, str]) -> None:
    """Request this fixture to skip a test cleanly when no database is reachable."""
    available, reason = db_status
    if not available:
        pytest.skip(f"no usable Postgres (DATABASE_URL): {reason}")


@pytest.fixture
def client():
    """
    A FastAPI TestClient with the app's lifespan run.

    Importing the app triggers router registration; the lifespan connects the
    Neo4j client which degrades gracefully when Neo4j is down. Safe with no infra.
    """
    from fastapi.testclient import TestClient

    from api.main import app

    with TestClient(app) as c:
        yield c
