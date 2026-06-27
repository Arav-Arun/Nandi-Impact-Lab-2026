"""
scripts.refresh_views — refresh the dashboard materialized view(s).

`zone_case_summary` powers the dashboard zone aggregates (M3). It must be
refreshed on a cadence (SoW §5.1: "every 5 minutes"). Member 1 owns this; we keep
it deployment-agnostic so it can be driven three ways without code changes:

  • one-shot (cron / pg_cron / CI):   python -m scripts.refresh_views
  • daemon loop:                       python -m scripts.refresh_views --loop
  • Celery beat (M2):                  await refresh_zone_case_summary()  as a task

CONCURRENTLY avoids locking the view against dashboard reads, but it requires a
unique index on the view and cannot run in a transaction block — we fall back to
a plain refresh if CONCURRENTLY is not yet supported by the view definition.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402

from core.config import settings  # noqa: E402
from core.database import engine  # noqa: E402
from core.logging_utils import get_logger  # noqa: E402

log = get_logger("refresh_views")

MATERIALIZED_VIEWS = ["zone_case_summary"]


async def refresh_zone_case_summary() -> None:
    """Refresh all dashboard materialized views once. Safe to call repeatedly."""
    # autocommit so REFRESH ... CONCURRENTLY (which forbids an open txn) works.
    async with engine.connect() as conn:
        conn = await conn.execution_options(isolation_level="AUTOCOMMIT")
        for view in MATERIALIZED_VIEWS:
            try:
                await conn.execute(text(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view}"))
            except Exception:
                # No unique index yet, or first refresh after creation — plain refresh.
                await conn.execute(text(f"REFRESH MATERIALIZED VIEW {view}"))
            log.info("refreshed materialized view %s", view)


async def _loop(interval: int) -> None:
    log.info("refresh loop started (every %ds)", interval)
    while True:
        try:
            await refresh_zone_case_summary()
        except Exception as exc:  # keep the loop alive across transient DB hiccups
            log.warning("refresh failed (%s); will retry next tick.", exc)
        await asyncio.sleep(interval)


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh NANDI materialized views.")
    parser.add_argument("--loop", action="store_true", help="run forever on a timer")
    parser.add_argument(
        "--interval",
        type=int,
        default=settings.MATVIEW_REFRESH_SECONDS,
        help="seconds between refreshes in --loop mode",
    )
    args = parser.parse_args()

    if args.loop:
        asyncio.run(_loop(args.interval))
    else:
        asyncio.run(refresh_zone_case_summary())


if __name__ == "__main__":
    main()
