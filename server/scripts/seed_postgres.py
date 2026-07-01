"""
scripts.seed_postgres - seed zones + booths into PostgreSQL.

Uses the SAME deterministic UUIDs as scripts.seed_neo4j (both read seed_data), so
a zone id in Postgres equals the matching zone id in Neo4j - which is exactly
what the zone-plausibility check relies on.

Usage:
    python -m scripts.seed_postgres        # idempotent: inserts only what's missing
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database import AsyncSessionLocal  # noqa: E402
from core.logging_utils import get_logger  # noqa: E402
from db.models import Booth, Zone  # noqa: E402
from scripts.seed_data import BOOTHS, ZONES, booth_id, zone_id  # noqa: E402

log = get_logger("seed_postgres")


async def seed() -> None:
    inserted_zones = inserted_booths = 0
    async with AsyncSessionLocal() as session:
        # Zones first (booths FK them).
        for z in ZONES:
            zid = zone_id(z["slug"])
            if await session.get(Zone, zid) is None:
                session.add(
                    Zone(
                        id=zid,
                        name=z["name"],
                        venue=z["venue"],
                        color_code=z["color_code"],
                        display_name_marathi=z["display_name_marathi"],
                    )
                )
                inserted_zones += 1

        for b in BOOTHS:
            bid = booth_id(b["slug"])
            if await session.get(Booth, bid) is None:
                session.add(
                    Booth(
                        id=bid,
                        zone_id=zone_id(b["zone_slug"]),
                        name=b["name"],
                        latitude=b["latitude"],
                        longitude=b["longitude"],
                        active=True,
                    )
                )
                inserted_booths += 1

        await session.commit()

    log.info("Postgres seed complete: +%d zones, +%d booths", inserted_zones, inserted_booths)
    print(f"Postgres seed complete: +{inserted_zones} zones, +{inserted_booths} booths")


if __name__ == "__main__":
    asyncio.run(seed())
