"""
tests.test_matcher_db — end-to-end matcher integration test (needs Postgres).

Marked @requires_db: conftest auto-skips the whole module's DB tests when no
usable, migrated Postgres is reachable, so the suite stays green with no infra.

What it exercises (against a real pgvector DB):
  1. insert a found report + a missing report whose stub passage embeddings are
     identical (same physical_description → deterministic stub → cosine 1.0),
  2. run services.matcher.find_candidates,
  3. assert the missing report is returned as a candidate in the 'high' band
     (Neo4j may be down → no graph modifiers → confidence == vector_score ≈ 1.0).

Everything is written inside a transaction that is rolled back in teardown, so
the test leaves the database untouched.
"""

from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.requires_db


@pytest.fixture
async def session(require_db):
    """A throwaway AsyncSession whose work is rolled back after the test."""
    from core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as s:
        try:
            yield s
        finally:
            await s.rollback()
            await s.close()


async def test_matcher_returns_high_band_candidate(session) -> None:
    from schemas.common import ConfidenceBand
    from services import embedding, matcher
    from db.models import FoundReport, MissingReport

    description = "elderly man, white dhoti, saffron shawl, walking stick, near Ramkund"
    # Stub embeddings: same description → identical passage vectors → cosine 1.0.
    vec = embedding.embed_text(description, kind="passage")

    missing = MissingReport(
        id=uuid.uuid4(),
        filed_by_phone="+919800000001",
        subject_name="Ramesh Patil",
        subject_age=68,
        subject_gender="male",
        physical_description=description,
        language_spoken="marathi",
        origin_city="Pune",
        status="active",
        embedding=vec,
    )
    found = FoundReport(
        id=uuid.uuid4(),
        name_if_known=None,
        approximate_age=68,
        gender="male",
        physical_description=description,
        language_spoken="marathi",
        apparent_city_origin="Pune",
        status="unmatched",
        embedding=vec,
    )

    session.add_all([missing, found])
    await session.flush()  # assign rows in-txn without committing

    candidates = await matcher.find_candidates(session, found.id)

    # The seeded missing report must surface as a candidate.
    ids = {c.missing_id for c in candidates}
    assert missing.id in ids, f"seeded missing report not returned; got {ids}"

    cand = next(c for c in candidates if c.missing_id == missing.id)

    # Identical stub vectors → cosine similarity ~1.0 → high band.
    assert cand.vector_score == pytest.approx(1.0, abs=1e-3)
    assert cand.confidence >= 0.90
    assert cand.band is ConfidenceBand.high
    # language_match is computed from SQL (both 'marathi') regardless of Neo4j.
    assert "Language spoken matches ✓" in cand.reasons


async def test_matcher_raises_for_unknown_found_id(session) -> None:
    from services import matcher

    # An unknown found id raises the specific FoundNotFoundError (which the route
    # maps to 404). Any OTHER error must NOT be swallowed as "not found".
    with pytest.raises(matcher.FoundNotFoundError):
        await matcher.find_candidates(session, uuid.uuid4())
