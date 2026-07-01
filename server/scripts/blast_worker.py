"""
scripts.blast_worker - time-based escalation for still-open reports (M2).

SoW escalation ladder: a missing report that is still `active` past T+24h triggers
a zone re-blast across every live channel; past T+72h it is escalated to police.
Each tier is idempotent (guarded by the audit event it writes), so the loop can
run as often as you like without double-sending.

  one-shot (cron):   python -m scripts.blast_worker
  daemon loop:       python -m scripts.blast_worker --loop [--interval 600]

Requires DATABASE_URL + (optionally) Neo4j for adjacency and the notify channel
keys in .env. With no channel keys it still advances the audit trail (logged
no-op sends), so the escalation state machine is testable offline.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import settings  # noqa: E402
from core.database import AsyncSessionLocal  # noqa: E402
from core.logging_utils import get_logger  # noqa: E402
from schemas.common import EventType  # noqa: E402
from services import blast  # noqa: E402
from services.case_events import log_event  # noqa: E402
from services.neo4j_client import neo4j_client  # noqa: E402

log = get_logger("blast_worker")


async def run_once() -> dict:
    """One escalation sweep. Returns counts of actions taken."""
    reblasted = escalated = 0
    async with AsyncSessionLocal() as session:
        # T+24h - re-blast the zone for still-open reports
        for report in await blast.open_reports_past(
            session, hours=settings.BLAST_ESCALATE_HOURS_1, without_event=EventType.blast_zone_sent
        ):
            who = report.subject_name or "a missing person"
            msg = (f"🪷 NANDI: still searching for {who} "
                   f"(last seen {report.last_seen_landmark or 'this area'}). "
                   f"If you have seen them, please alert the nearest NANDI booth.")
            await blast.blast_zone(
                session, zone_id=report.last_seen_zone_id, message=msg,
                subject="NANDI - still searching", report_id=report.id,
            )
            reblasted += 1

        # T+72h - escalate to police
        for report in await blast.open_reports_past(
            session, hours=settings.BLAST_ESCALATE_HOURS_2, without_event=EventType.escalated_to_police
        ):
            await log_event(session, report_id=report.id, event_type=EventType.escalated_to_police,
                            metadata={"reason": f"open > {settings.BLAST_ESCALATE_HOURS_2}h",
                                      "zone_id": str(report.last_seen_zone_id)})
            escalated += 1

        await session.commit()
    log.info("escalation sweep: reblasted=%d escalated_to_police=%d", reblasted, escalated)
    return {"reblasted": reblasted, "escalated": escalated}


async def _loop(interval: int) -> None:
    await neo4j_client.connect()
    log.info("blast worker loop started (every %ds)", interval)
    try:
        while True:
            try:
                await run_once()
            except Exception as exc:
                log.warning("escalation sweep failed (%s); retrying next tick.", exc)
            await asyncio.sleep(interval)
    finally:
        await neo4j_client.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="NANDI escalation / blast worker.")
    parser.add_argument("--loop", action="store_true", help="run forever on a timer")
    parser.add_argument("--interval", type=int, default=600, help="seconds between sweeps in --loop mode")
    args = parser.parse_args()

    if args.loop:
        asyncio.run(_loop(args.interval))
    else:
        async def _once():
            await neo4j_client.connect()
            try:
                await run_once()
            finally:
                await neo4j_client.close()
        asyncio.run(_once())


if __name__ == "__main__":
    main()
