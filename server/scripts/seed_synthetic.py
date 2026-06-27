"""
scripts.seed_synthetic — load dataset/Synthetic_Missing_Persons_2500.csv into
`missing_reports` so the dashboard / feed / matcher have realistic data.

Maps the CSV columns onto the MissingReport model, assigns each row to one of the
seeded zones/booths (by reporting-center keyword, round-robin fallback), generates
a text embedding, and bulk-inserts. Refreshes the zone_case_summary matview at the
end. Idempotent-ish: pass --truncate to clear missing_reports first.

Usage:
    python -m scripts.seed_synthetic              # append all rows
    python -m scripts.seed_synthetic --limit 500  # only first 500
    python -m scripts.seed_synthetic --truncate   # wipe missing_reports first
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402

from core.database import AsyncSessionLocal, engine  # noqa: E402
from core.logging_utils import get_logger  # noqa: E402
from db.models import MissingReport  # noqa: E402
from services import embedding  # noqa: E402
from scripts.seed_data import booth_id, zone_id  # noqa: E402

log = get_logger("seed_synthetic")

# dataset/ lives at the repo root (one level above server/).
CSV_PATH = Path(__file__).resolve().parent.parent.parent / "dataset" / "Synthetic_Missing_Persons_2500.csv"

# ── value maps ───────────────────────────────────────────────────────────────
AGE_BAND_MIDPOINT = {
    "0-12": 6, "13-17": 15, "18-40": 29, "41-60": 50,
    "61-70": 65, "71-80": 75, "80+": 85,
}
GENDER = {"male": "male", "female": "female", "unknown": "unknown"}
STATUS = {  # CSV status -> MissingReport.status lifecycle
    "Reunited": "matched",
    "Pending": "active",
    "Unresolved": "active",
    "Transferred to hospital": "closed",
}
# reporting_center keyword -> seeded zone slug
ZONE_KEYWORDS = [
    ("ramkund", "ramkund"), ("panchavati", "panchavati"), ("trimbak", "trimbak"),
    ("adgaon", "tapovan"), ("sadhugram", "tapovan"), ("tapovan", "tapovan"),
    ("rajur", "kushavarta"), ("nashik road", "panchavati"),
]
ALL_ZONES = ["ramkund", "panchavati", "tapovan", "kushavarta", "trimbak"]
ZONE_BOOTH = {
    "ramkund": "ramkund_neela", "panchavati": "panchavati_3", "tapovan": "tapovan_1",
    "kushavarta": "kushavarta_main", "trimbak": "trimbak_gate_1",
}


def zone_for(center: str, idx: int) -> str:
    """Map a reporting center to a seeded zone slug; round-robin as fallback."""
    low = (center or "").lower()
    for kw, slug in ZONE_KEYWORDS:
        if kw in low:
            return slug
    return ALL_ZONES[idx % len(ALL_ZONES)]


def parse_dt(value: str) -> datetime | None:
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
    except (ValueError, AttributeError):
        return None


def build_report(row: dict, idx: int) -> MissingReport:
    desc = row.get("physical_description") or "(no description)"
    zslug = zone_for(row.get("reporting_center", ""), idx)
    return MissingReport(
        filed_at=parse_dt(row.get("reported_at", "")),
        filed_by_phone=(row.get("reporter_mobile") or "").strip() or "+910000000000",
        subject_name=(row.get("missing_person_name") or "").strip() or None,
        subject_age=AGE_BAND_MIDPOINT.get((row.get("age_band") or "").strip()),
        subject_gender=GENDER.get((row.get("gender") or "").strip().lower(), "unknown"),
        physical_description=desc,
        last_seen_zone_id=zone_id(zslug),
        last_seen_landmark=(row.get("last_seen_location") or "").strip() or None,
        last_seen_time=parse_dt(row.get("reported_at", "")),
        language_spoken=(row.get("language") or "").strip() or None,
        origin_city=(row.get("district") or "").strip() or None,
        status=STATUS.get((row.get("status") or "").strip(), "active"),
        created_by_booth_id=booth_id(ZONE_BOOTH[zslug]),
        embedding=embedding.embed_text(desc, kind="passage"),
    )


async def seed(limit: int | None, truncate: bool) -> None:
    if not CSV_PATH.exists():
        raise SystemExit(f"dataset not found: {CSV_PATH}")
    rows = list(csv.DictReader(CSV_PATH.open(encoding="utf-8")))
    if limit:
        rows = rows[:limit]
    log.info("seeding %d synthetic missing reports from %s", len(rows), CSV_PATH.name)

    async with AsyncSessionLocal() as s:
        if truncate:
            await s.execute(text("TRUNCATE missing_reports CASCADE"))
            await s.commit()
            log.info("truncated missing_reports")

        batch: list[MissingReport] = []
        inserted = 0
        for idx, row in enumerate(rows):
            batch.append(build_report(row, idx))
            if len(batch) >= 500:
                s.add_all(batch)
                await s.commit()
                inserted += len(batch)
                log.info("  inserted %d/%d", inserted, len(rows))
                batch = []
        if batch:
            s.add_all(batch)
            await s.commit()
            inserted += len(batch)

    # Refresh the dashboard rollup (first refresh after data load is non-concurrent).
    async with engine.connect() as conn:
        conn = await conn.execution_options(isolation_level="AUTOCOMMIT")
        await conn.execute(text("REFRESH MATERIALIZED VIEW zone_case_summary"))

    log.info("done: %d missing reports inserted, matview refreshed", inserted)
    print(f"✅ seeded {inserted} synthetic missing reports (matview refreshed)")


def main() -> None:
    ap = argparse.ArgumentParser(description="Seed synthetic missing-persons data.")
    ap.add_argument("--limit", type=int, default=None, help="only seed the first N rows")
    ap.add_argument("--truncate", action="store_true", help="clear missing_reports first")
    args = ap.parse_args()
    asyncio.run(seed(args.limit, args.truncate))


if __name__ == "__main__":
    main()
