"""
services.matcher — the matching pipeline (Member 1, the "matching brain").

Given a found-person report id, return the top candidate missing reports for the
booth operator to confirm. Pipeline (SoW §6):

    found report ─▶ pgvector ANN (gender+age pre-filter, cosine rank)
                 ─▶ photo re-rank (InsightFace cosine, when both have faces)
                 ─▶ Neo4j validation per surviving candidate
                 ─▶ composite confidence + reason labels
                 ─▶ drop < MIN_SURFACE, sort by confidence, return top N

This module never notifies anyone and never auto-confirms — it only ranks. The
operator confirmation (the safety contract, SoW §12.8 #1) happens in the route.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.logging_utils import get_logger
from db.models import FoundReport, MissingReport
from schemas.match import GraphSignals, MatchCandidate
from services import dedup, embedding, scoring
from services.neo4j_client import neo4j_client

log = get_logger(__name__)


class FoundNotFoundError(LookupError):
    """Raised when a found_report id has no matching row. The route maps this to a
    404 — distinct from any other error, which must surface as a real 500 rather
    than being mislabeled 'not found'."""


async def get_found_report(session: AsyncSession, found_id: uuid.UUID) -> FoundReport | None:
    """Load a found report by id (None if absent)."""
    return await session.get(FoundReport, found_id)


async def get_missing_report(session: AsyncSession, missing_id: uuid.UUID) -> MissingReport | None:
    """Load a missing report by id (None if absent)."""
    return await session.get(MissingReport, missing_id)


def _language_match(found: FoundReport, missing: MissingReport) -> bool:
    """True when both records name the same spoken language (case-insensitive)."""
    fl = (found.language_spoken or "").strip().lower()
    ml = (missing.language_spoken or "").strip().lower()
    return bool(fl) and fl == ml


async def _possible_duplicate(missing: MissingReport) -> bool:
    """
    True if this missing candidate looks like a duplicate of another active report.

    Feeds the `possible_duplicate` penalty (SoW §6.2). Best-effort: returns False
    if Neo4j is unavailable (the dedup query degrades to (0, [])).
    """
    count, _ = await dedup.find_duplicate_missing(
        current_id=missing.id,
        subject_name=missing.subject_name,
        subject_age=missing.subject_age,
        subject_gender=missing.subject_gender,
    )
    return count > 0


async def _vector_candidates(
    session: AsyncSession, found: FoundReport, query_vec: list[float]
) -> list[tuple[MissingReport, float]]:
    """
    Run the pgvector ANN search with gender/age pre-filtering (SoW §5.2).

    Pre-filters (gender, age window, status=active) shrink the search space
    before the cosine comparison — HNSW supports WHERE pre-filtering from PG16+.
    Returns [(missing_report, cosine_similarity)] ordered best-first.

    Robustness beyond the literal SoW query:
      • gender filter is applied only when the found person's gender is a concrete
        male/female (an "unknown"/blank gender must not exclude valid matches).
      • age filter is applied only when an approximate age is known.
    """
    # Raise HNSW ef_search for this transaction only (recall vs latency knob).
    await session.execute(
        text("SELECT set_config('hnsw.ef_search', :ef, true)"),
        {"ef": str(settings.PGVECTOR_EF_SEARCH)},
    )

    distance = MissingReport.embedding.cosine_distance(query_vec)
    stmt = (
        select(MissingReport, distance.label("distance"))
        .where(MissingReport.status == "active")
        .where(MissingReport.embedding.isnot(None))
        .order_by(distance)
        .limit(settings.MATCH_CANDIDATE_LIMIT)
    )

    # Gender pre-filter (only on a concrete gender).
    if found.gender in ("male", "female"):
        stmt = stmt.where(MissingReport.subject_gender == found.gender)

    # Age window pre-filter (only when age is known).
    if found.approximate_age is not None:
        low = found.approximate_age - settings.MATCH_AGE_WINDOW
        high = found.approximate_age + settings.MATCH_AGE_WINDOW
        stmt = stmt.where(MissingReport.subject_age.between(low, high))

    rows = (await session.execute(stmt)).all()
    out: list[tuple[MissingReport, float]] = []
    for missing, dist in rows:
        # cosine distance → similarity; clamp negatives to 0 for scoring.
        similarity = max(0.0, min(1.0, 1.0 - float(dist)))
        out.append((missing, similarity))
    return out


def _photo_rerank(
    found: FoundReport, candidates: list[tuple[MissingReport, float]]
) -> list[tuple[MissingReport, float]]:
    """
    Re-order candidates by face similarity when both sides have a face vector.

    The displayed/scored `vector_score` stays the TEXT cosine (SoW §6.2 base);
    faces only influence WHICH candidates advance to graph validation. When the
    found person has no face vector, ordering is unchanged.
    """
    # face_embedding is a numpy array or None — never use bare truthiness on it.
    if found.face_embedding is None:
        return candidates

    def rank_key(item: tuple[MissingReport, float]) -> float:
        missing, text_sim = item
        if missing.face_embedding is not None:
            # Strong identity signal — rank by face similarity.
            return embedding.cosine_similarity(found.face_embedding, missing.face_embedding)
        # No face on this candidate: fall back to its text similarity.
        return text_sim

    return sorted(candidates, key=rank_key, reverse=True)


async def find_candidates(session: AsyncSession, found_id: uuid.UUID) -> list[MatchCandidate]:
    """
    Full pipeline entry point. Returns ranked MatchCandidate list (may be empty).

    Raises FoundNotFoundError if the found report does not exist (the route maps
    this to a 404 envelope). Any other exception propagates as a real 500.
    """
    found = await get_found_report(session, found_id)
    if found is None:
        raise FoundNotFoundError(f"found_report {found_id} not found")

    # Search vector: the stored found embedding (a passage vector). If it is
    # missing (embed failed at intake), embed the description on the fly as a
    # query so matching still works rather than returning nothing.
    # NB: embedding columns come back from pgvector as numpy arrays — test for
    # None/length explicitly (bare truthiness on an ndarray raises ValueError).
    query_vec = found.embedding
    if query_vec is None or len(query_vec) == 0:
        if not found.physical_description:
            log.warning("found %s has no embedding and no description; no candidates.", found_id)
            return []
        query_vec = embedding.embed_text(found.physical_description, kind="query")

    # 1) pgvector ANN + pre-filter
    ranked = await _vector_candidates(session, found, query_vec)
    if not ranked:
        return []

    # 2) photo re-rank, then keep only the slots the operator will see
    ranked = _photo_rerank(found, ranked)[: settings.MATCH_RETURN_LIMIT]

    # Seed the found node once so the graph validation queries can traverse it.
    await neo4j_client.sync_found_report(
        report_id=found.id,
        found_at=found.found_at,
        status=found.status,
        name_if_known=found.name_if_known,
        approximate_age=found.approximate_age,
        gender=found.gender,
        apparent_city_origin=found.apparent_city_origin,
        language_spoken=found.language_spoken,
        booth_id=found.registered_at_booth,
        current_zone_id=found.current_zone_id,
    )

    # 3) graph validation + 4) composite score, per candidate
    results: list[MatchCandidate] = []
    for missing, text_sim in ranked:
        # Ensure the missing node exists before validating (idempotent).
        await neo4j_client.sync_missing_report(
            report_id=missing.id,
            filed_at=missing.filed_at,
            status=missing.status,
            subject_name=missing.subject_name,
            subject_age=missing.subject_age,
            subject_gender=missing.subject_gender,
            origin_city=missing.origin_city,
            language_spoken=missing.language_spoken,
            last_seen_time=missing.last_seen_time,
            last_seen_landmark=missing.last_seen_landmark,
            last_seen_zone_id=missing.last_seen_zone_id,
            booth_id=missing.created_by_booth_id,
            filer_phone=missing.filed_by_phone,
        )

        signals = await neo4j_client.graph_signals(
            missing_id=missing.id,
            found_id=found.id,
            filer_phone=missing.filed_by_phone,
        )
        # language_match is computed from SQL (not a graph query), merged in here.
        signals["language_match"] = _language_match(found, missing)
        # possible_duplicate: penalise candidates that themselves look like a
        # duplicate of another active report (graph_signals doesn't compute this).
        signals["possible_duplicate"] = await _possible_duplicate(missing)

        confidence, reasons = scoring.composite_confidence(text_sim, signals)
        band = scoring.confidence_band(confidence)
        if band is None:
            # Below the surface floor (< 0.60) — never shown to the operator.
            continue

        results.append(
            MatchCandidate(
                missing_id=missing.id,
                subject_name=missing.subject_name,
                subject_age=missing.subject_age,
                subject_gender=missing.subject_gender,
                physical_description=missing.physical_description,
                last_seen_landmark=missing.last_seen_landmark,
                last_seen_zone_id=missing.last_seen_zone_id,
                filed_at=missing.filed_at,
                photo_url=missing.photo_url,
                origin_city=missing.origin_city,
                vector_score=round(text_sim, 3),
                confidence=confidence,
                band=band,
                reasons=reasons,
            )
        )

    # Final display order: highest composite confidence first.
    results.sort(key=lambda c: c.confidence, reverse=True)
    return results


async def graph_signals_for(
    session: AsyncSession,
    *,
    missing_id: uuid.UUID,
    found_id: uuid.UUID,
    filer_phone: str | None,
) -> GraphSignals:
    """
    Standalone signal computation for POST /internal/validate.

    Seeds both nodes (idempotent), runs the graph checks, and folds in the
    SQL-derived language_match. Returns a fully-populated GraphSignals model.
    """
    found = await get_found_report(session, found_id)
    missing = await get_missing_report(session, missing_id)

    if found is not None:
        await neo4j_client.sync_found_report(
            report_id=found.id,
            found_at=found.found_at,
            status=found.status,
            name_if_known=found.name_if_known,
            approximate_age=found.approximate_age,
            gender=found.gender,
            apparent_city_origin=found.apparent_city_origin,
            language_spoken=found.language_spoken,
            booth_id=found.registered_at_booth,
            current_zone_id=found.current_zone_id,
        )
    if missing is not None:
        await neo4j_client.sync_missing_report(
            report_id=missing.id,
            filed_at=missing.filed_at,
            status=missing.status,
            subject_name=missing.subject_name,
            subject_age=missing.subject_age,
            subject_gender=missing.subject_gender,
            origin_city=missing.origin_city,
            language_spoken=missing.language_spoken,
            last_seen_time=missing.last_seen_time,
            last_seen_landmark=missing.last_seen_landmark,
            last_seen_zone_id=missing.last_seen_zone_id,
            booth_id=missing.created_by_booth_id,
            filer_phone=missing.filed_by_phone,
        )

    signals = await neo4j_client.graph_signals(
        missing_id=missing_id, found_id=found_id, filer_phone=filer_phone
    )
    if found is not None and missing is not None:
        signals["language_match"] = _language_match(found, missing)
    if missing is not None:
        signals["possible_duplicate"] = await _possible_duplicate(missing)

    return GraphSignals(**signals)
