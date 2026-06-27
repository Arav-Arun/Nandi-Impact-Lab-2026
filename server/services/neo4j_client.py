"""
services.neo4j_client — async Neo4j driver wrapper + all graph operations (M1).

Responsibilities:
  • Own the single async driver (connect lazily, close on shutdown).
  • Idempotently sync MissingReport / FoundReport nodes into the graph so the
    validation queries have something to traverse (MERGE everywhere → safe to
    call repeatedly, including on offline-sync replays).
  • Run the five validation queries from SoW §6.1 and return a `graph_signals`
    dict (used by /internal/validate and the matcher).
  • Write the MATCHED_TO edge on operator confirmation.
  • Serve the landmark-pattern aggregation consumed by the dashboard (Panel 4).

GRACEFUL DEGRADATION (SoW §2 Golden Rule): if Neo4j is unreachable, every read
returns empty/false signals and every write is a logged no-op. Matching then
falls back to pure vector similarity instead of crashing — tech amplifies, it is
never the only layer.

The .cypher query files live in graph/queries/ and are loaded by name. Their
bind-parameter names are the contract documented on each method below.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from neo4j import AsyncDriver, AsyncGraphDatabase

from core.config import settings
from core.logging_utils import get_logger

log = get_logger(__name__)

# graph/ lives at the repo root next to this services/ package.
_GRAPH_DIR = Path(__file__).resolve().parent.parent / "graph"
_QUERY_DIR = _GRAPH_DIR / "queries"


@lru_cache(maxsize=None)
def _load_cypher(name: str) -> str:
    """Read and cache a .cypher file from graph/queries/ by stem name."""
    path = _QUERY_DIR / f"{name}.cypher"
    return path.read_text(encoding="utf-8")


def _coerce_bool(value: Any) -> bool:
    """Neo4j may return None for comparisons involving NULLs — treat None as False."""
    return bool(value) if value is not None else False


class Neo4jClient:
    """Thin async wrapper around the Neo4j driver with NANDI-specific helpers."""

    def __init__(self) -> None:
        self._driver: AsyncDriver | None = None
        # Latches to True after a connection failure so we stop trying every call
        # and degrade gracefully for the rest of the process lifetime.
        self._unavailable = False

    # ── lifecycle ───────────────────────────────────────────────────────────
    async def connect(self) -> None:
        """Open the driver and verify connectivity. Safe to call once at startup."""
        if self._driver is not None:
            return
        try:
            self._driver = AsyncGraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
                # Silence "unknown relationship type / property key" notifications:
                # several rels (MATCHED_TO, BELONGS_TO) and props (City.state) only
                # exist once data accumulates, so these warnings are expected noise,
                # not bugs — our queries handle the absent cases as NULL/false.
                notifications_disabled_categories=["UNRECOGNIZED"],
            )
            await self._driver.verify_connectivity()
            self._unavailable = False
            log.info("Neo4j connected at %s", settings.NEO4J_URI)
        except Exception as exc:  # connection refused / auth / offline
            log.warning("Neo4j unavailable (%s) — graph validation will be skipped.", exc)
            self._driver = None
            self._unavailable = True

    async def close(self) -> None:
        if self._driver is not None:
            await self._driver.close()
            self._driver = None

    async def _run(self, cypher: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """
        Execute a Cypher statement and return rows as dicts.

        On any failure (including Neo4j being down) logs a warning and returns an
        empty list so callers degrade gracefully rather than raising.
        """
        if self._driver is None:
            if not self._unavailable:
                await self.connect()
            if self._driver is None:
                return []
        try:
            async with self._driver.session() as session:
                result = await session.run(cypher, params or {})
                return [record.data() async for record in result]
        except Exception as exc:
            log.warning("Neo4j query failed (%s) — returning empty result.", exc)
            return []

    # ── runtime node sync (idempotent) ──────────────────────────────────────
    async def sync_missing_report(
        self,
        *,
        report_id: uuid.UUID,
        filed_at: datetime | None,
        status: str,
        subject_name: str | None,
        subject_age: int | None,
        subject_gender: str | None,
        origin_city: str | None,
        language_spoken: str | None,
        last_seen_time: datetime | None,
        last_seen_landmark: str | None,
        last_seen_zone_id: uuid.UUID | None,
        booth_id: uuid.UUID | None,
        filer_phone: str | None,
    ) -> None:
        """
        MERGE a MissingReport (+ Person/City/Landmark/Booth/Phone) into the graph.

        Called by M2's intake after writing the SQL row (see INTEGRATION.md), and
        defensively re-run by the matcher. All MERGE → safe to call repeatedly.
        """
        await self._run(
            _load_cypher("sync_missing_report"),
            {
                "id": str(report_id),
                "filed_at": filed_at,
                "status": status,
                "name": subject_name,
                "age": subject_age,
                "gender": subject_gender,
                "origin_city": origin_city,
                "language": language_spoken,
                "last_seen_time": last_seen_time,
                "landmark": last_seen_landmark,
                "zone_id": str(last_seen_zone_id) if last_seen_zone_id else None,
                "booth_id": str(booth_id) if booth_id else None,
                "filer_phone": filer_phone,
            },
        )

    async def sync_found_report(
        self,
        *,
        report_id: uuid.UUID,
        found_at: datetime | None,
        status: str,
        name_if_known: str | None,
        approximate_age: int | None,
        gender: str | None,
        apparent_city_origin: str | None,
        language_spoken: str | None,
        booth_id: uuid.UUID | None,
        current_zone_id: uuid.UUID | None,
    ) -> None:
        """MERGE a FoundReport (+ Person/City/Booth) into the graph. Idempotent."""
        await self._run(
            _load_cypher("sync_found_report"),
            {
                "id": str(report_id),
                "found_at": found_at,
                "status": status,
                "name": name_if_known,
                "age": approximate_age,
                "gender": gender,
                "origin_city": apparent_city_origin,
                "language": language_spoken,
                "booth_id": str(booth_id) if booth_id else None,
                "zone_id": str(current_zone_id) if current_zone_id else None,
            },
        )

    async def write_match_edge(self, missing_id: uuid.UUID, found_id: uuid.UUID) -> None:
        """Write the (:MissingReport)-[:MATCHED_TO]->(:FoundReport) edge on confirm."""
        await self._run(
            """
            MATCH (m:MissingReport {id: $missing_id})
            MATCH (f:FoundReport   {id: $found_id})
            MERGE (m)-[:MATCHED_TO]->(f)
            SET m.status = 'matched', f.status = 'matched'
            """,
            {"missing_id": str(missing_id), "found_id": str(found_id)},
        )

    # ── validation queries (SoW §6.1) ───────────────────────────────────────
    async def graph_signals(
        self,
        *,
        missing_id: uuid.UUID,
        found_id: uuid.UUID,
        filer_phone: str | None,
    ) -> dict[str, bool]:
        """
        Run all graph checks for one (missing, found) pair and return signal bools.

        This is the body behind POST /internal/validate. Keys returned match the
        modifier keys in services.scoring.MODIFIERS (minus language_match, which
        the matcher computes from SQL records). Always returns a full dict; when
        Neo4j is down every value is False.
        """
        signals: dict[str, bool] = {
            "same_zone": False,
            "adjacent_zone": False,
            "same_venue": False,
            "different_venue": False,
            "same_city": False,
            "same_state": False,
            "temporal_very_recent": False,
            "temporal_same_day": False,
            "temporal_stale": False,
            "landmark_pattern_match": False,
            "possible_duplicate": False,
        }

        params = {"missing_id": str(missing_id), "found_id": str(found_id)}

        # Zone plausibility
        rows = await self._run(_load_cypher("zone_plausibility"), params)
        if rows:
            r = rows[0]
            signals["same_zone"] = _coerce_bool(r.get("same_zone"))
            signals["adjacent_zone"] = _coerce_bool(r.get("adjacent_zone"))
            signals["same_venue"] = _coerce_bool(r.get("same_venue"))
            # different_venue only fires when both venues are known AND differ.
            same_venue_known = r.get("same_venue") is not None
            signals["different_venue"] = same_venue_known and not signals["same_venue"]

        # Temporal plausibility
        rows = await self._run(_load_cypher("temporal"), params)
        if rows:
            r = rows[0]
            signals["temporal_very_recent"] = _coerce_bool(r.get("very_recent"))
            signals["temporal_same_day"] = _coerce_bool(r.get("same_day"))
            signals["temporal_stale"] = _coerce_bool(r.get("stale"))

        # City / state of origin
        rows = await self._run(
            _load_cypher("origin_city"), {**params, "filer_phone": filer_phone}
        )
        if rows:
            r = rows[0]
            signals["same_city"] = _coerce_bool(r.get("same_city"))
            signals["same_state"] = _coerce_bool(r.get("same_state"))

        # Learned landmark→booth flow pattern (per-candidate membership check)
        rows = await self._run(
            _load_cypher("landmark_pattern_match"), {**params, "min_times": 1}
        )
        if rows:
            signals["landmark_pattern_match"] = _coerce_bool(rows[0].get("pattern_match"))

        return signals

    async def duplicate_check(
        self,
        *,
        current_id: uuid.UUID,
        name_fragment: str,
        age: int | None,
        gender: str | None,
    ) -> tuple[int, list[str]]:
        """
        Detect likely-duplicate active missing reports (SoW §6.1 duplicate check).

        Returns (count, ids). Used both to set the `possible_duplicate` signal for
        a candidate and by services.dedup to flag duplicates on intake.
        """
        rows = await self._run(
            _load_cypher("duplicate_check"),
            {
                "current_id": str(current_id),
                "name_fragment": (name_fragment or "").strip(),
                "age": age if age is not None else -999,
                "gender": gender or "",
            },
        )
        if not rows:
            return 0, []
        r = rows[0]
        return int(r.get("duplicate_count") or 0), [str(i) for i in (r.get("ids") or [])]

    # ── dashboard support (consumed by M3's GET /dashboard/patterns) ─────────
    async def landmark_patterns(
        self, *, min_times: int = 1, limit: int = 50
    ) -> list[dict[str, Any]]:
        """
        Aggregate learned landmark→booth flows across confirmed matches.

        Returns rows shaped `{from_landmark, to_landmark, count}` where
        `to_landmark` is the booth where people last seen at `from_landmark`
        typically turned up (Panel 4 annotation). M3 owns the HTTP route; this is
        the data source it calls.
        """
        rows = await self._run(
            _load_cypher("landmark_pattern"), {"min_times": min_times, "limit": limit}
        )
        return [
            {
                "from_landmark": r.get("from_landmark"),
                "to_landmark": r.get("to_landmark"),
                "count": int(r.get("times") or 0),
            }
            for r in rows
        ]


# Module-level singleton shared by routes/services. Connected at app startup
# (api.main lifespan) and closed at shutdown.
neo4j_client = Neo4jClient()


async def get_neo4j() -> Neo4jClient:
    """FastAPI dependency returning the shared Neo4j client."""
    return neo4j_client
