"""Persistence + analytics for the intake layer.

Seeds from the synthetic dataset on first boot so the dashboard is alive
immediately, then accepts live reports from every channel.
"""
from __future__ import annotations

import csv
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, select

from app.config import settings
from app.db import SessionLocal
from app.models.db_models import Report
from app.models.schemas import ReportOut, StatsOut, mask_phone


def _parse_dt(raw: str) -> datetime:
    try:
        return datetime.strptime(raw.strip(), "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
    except (ValueError, AttributeError):
        return datetime.now(timezone.utc)


async def seed_from_csv(path: str | None = None) -> int:
    """Bulk-load the synthetic dataset if the table is empty. Returns rows seeded."""
    csv_path = Path(path or settings.seed_csv_path)
    async with SessionLocal() as session:
        existing = await session.scalar(select(func.count()).select_from(Report))
        if existing:
            return 0
        if not csv_path.exists():
            return 0

        objs: list[Report] = []
        with csv_path.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                res = row.get("resolution_hours") or ""
                objs.append(
                    Report(
                        id=str(uuid.uuid4()),
                        case_id=row["case_id"],
                        report_type="missing",
                        channel="seed",
                        status=(row.get("status") or "active"),
                        reported_at=_parse_dt(row.get("reported_at", "")),
                        person_name=row.get("missing_person_name") or None,
                        gender=row.get("gender") or None,
                        age_band=row.get("age_band") or None,
                        state=row.get("state") or None,
                        district=row.get("district") or None,
                        language=row.get("language") or None,
                        last_seen_location=row.get("last_seen_location") or None,
                        physical_description=row.get("physical_description") or None,
                        reporter_mobile=row.get("reporter_mobile") or None,
                        reporting_center=row.get("reporting_center") or None,
                        is_duplicate_report=(row.get("is_duplicate_report") == "True"),
                        resolution_hours=float(res) if res else None,
                    )
                )
        session.add_all(objs)
        await session.commit()
        return len(objs)


async def add_report(report: Report) -> Report:
    async with SessionLocal() as session:
        session.add(report)
        await session.commit()
        await session.refresh(report)
        return report


def _as_utc(dt: datetime) -> datetime:
    """SQLite stores naive datetimes; we always persist UTC, so re-attach tz on
    the way out — otherwise the browser parses it as local time (IST skew)."""
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def to_out(r: Report) -> ReportOut:
    return ReportOut(
        id=r.id,
        case_id=r.case_id,
        report_type=r.report_type,
        channel=r.channel,
        status=r.status,
        reported_at=_as_utc(r.reported_at),
        person_name=r.person_name,
        gender=r.gender,
        age_band=r.age_band,
        state=r.state,
        district=r.district,
        language=r.language,
        last_seen_location=r.last_seen_location,
        physical_description=r.physical_description,
        reporter_mobile_masked=mask_phone(r.reporter_mobile),
        reporting_center=r.reporting_center,
        is_duplicate_report=r.is_duplicate_report,
        detected_language=r.detected_language,
        extraction_confidence=r.extraction_confidence,
    )


async def list_feed(limit: int = 40, channel: str | None = None) -> list[ReportOut]:
    """Most recent reports first. Live (non-seed) channels float to the top by recency."""
    async with SessionLocal() as session:
        stmt = select(Report).order_by(Report.created_at.desc(), Report.reported_at.desc())
        if channel:
            stmt = stmt.where(Report.channel == channel)
        stmt = stmt.limit(limit)
        rows = (await session.scalars(stmt)).all()
        return [to_out(r) for r in rows]


_LIVE_CHANNELS = {"web", "telegram", "whatsapp", "ivr"}


async def compute_stats() -> StatsOut:
    async with SessionLocal() as session:
        rows = (await session.scalars(select(Report))).all()

    total = len(rows)
    by_status: Counter = Counter()
    by_channel: Counter = Counter()
    by_language: Counter = Counter()
    by_age: Counter = Counter()
    by_gender: Counter = Counter()
    by_loc: Counter = Counter()
    by_date: defaultdict[str, int] = defaultdict(int)

    duplicates = no_name = no_mobile = reunited = 0
    res_hours: list[float] = []
    live_today = 0

    for r in rows:
        by_status[r.status or "unknown"] += 1
        by_channel[r.channel] += 1
        if r.language:
            by_language[r.language] += 1
        if r.age_band:
            by_age[r.age_band] += 1
        if r.gender:
            by_gender[r.gender] += 1
        if r.last_seen_location:
            by_loc[r.last_seen_location] += 1
        by_date[r.reported_at.date().isoformat()] += 1
        if r.is_duplicate_report:
            duplicates += 1
        if not r.person_name:
            no_name += 1
        if not r.reporter_mobile:
            no_mobile += 1
        if (r.status or "").lower() == "reunited":
            reunited += 1
        if r.resolution_hours is not None:
            res_hours.append(r.resolution_hours)
        if r.channel in _LIVE_CHANNELS:
            live_today += 1

    age_order = ["0-12", "13-17", "18-40", "41-60", "61-70", "71-80", "80+"]

    return StatsOut(
        total=total,
        live_today=live_today,
        by_status=dict(by_status.most_common()),
        by_channel=dict(by_channel.most_common()),
        by_language=dict(by_language.most_common(12)),
        by_age_band={k: by_age.get(k, 0) for k in age_order if by_age.get(k)},
        by_gender=dict(by_gender.most_common()),
        top_locations=dict(by_loc.most_common(8)),
        duplicates=duplicates,
        missing_name_pct=round(100 * no_name / total, 1) if total else 0.0,
        missing_mobile_pct=round(100 * no_mobile / total, 1) if total else 0.0,
        reunited=reunited,
        avg_resolution_hours=round(sum(res_hours) / len(res_hours), 1) if res_hours else None,
        timeseries=[{"date": d, "count": c} for d, c in sorted(by_date.items())],
    )
