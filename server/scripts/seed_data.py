"""
scripts.seed_data — canonical Nashik / Trimbakeshwar topology (single source).

CRITICAL: zone and booth UUIDs must be IDENTICAL in PostgreSQL and Neo4j, because
the graph zone-plausibility check compares a zone id coming from the seeded graph
(found booth's zone) against a zone id coming from Postgres (missing report's
last_seen_zone_id). We guarantee this by deriving every id deterministically with
uuid5 from a fixed namespace + a stable slug — so seed_postgres.py and
seed_neo4j.py independently compute the same ids, no hardcoded UUIDs to drift.

Edit the data here and BOTH seeders (and the generated graph/seed_nashik.cypher)
stay in sync.
"""

from __future__ import annotations

import uuid

# Fixed namespace for all NANDI seed ids. Never change this — it would re-key
# every seeded zone/booth and break id alignment with already-seeded data.
NAMESPACE = uuid.UUID("4e616e64-6900-5345-4544-000000000001")  # "Nandi SEED" mnemonic


def seed_id(kind: str, slug: str) -> uuid.UUID:
    """Deterministic UUID for a seed entity, e.g. seed_id('zone', 'ramkund')."""
    return uuid.uuid5(NAMESPACE, f"{kind}:{slug}")


# ── Zones ────────────────────────────────────────────────────────────────────
# slug, name, venue, color_code (wristband hex), display_name_marathi
ZONES: list[dict] = [
    {"slug": "ramkund",    "name": "Ramkund Zone",     "venue": "Nashik",
     "color_code": "#E53935", "display_name_marathi": "रामकुंड क्षेत्र"},
    {"slug": "panchavati", "name": "Panchavati Zone",  "venue": "Nashik",
     "color_code": "#1E88E5", "display_name_marathi": "पंचवटी क्षेत्र"},
    {"slug": "tapovan",    "name": "Tapovan Zone",     "venue": "Nashik",
     "color_code": "#43A047", "display_name_marathi": "तपोवन क्षेत्र"},
    {"slug": "kushavarta", "name": "Kushavarta Zone",  "venue": "Trimbakeshwar",
     "color_code": "#FB8C00", "display_name_marathi": "कुशावर्त क्षेत्र"},
    {"slug": "trimbak",    "name": "Trimbak Town Zone", "venue": "Trimbakeshwar",
     "color_code": "#8E24AA", "display_name_marathi": "त्र्यंबक नगर क्षेत्र"},
]

# ── Landmarks ────────────────────────────────────────────────────────────────
# slug, name, zone_slug
LANDMARKS: list[dict] = [
    {"slug": "ramkund_ghat",    "name": "Ramkund Ghat",    "zone_slug": "ramkund"},
    {"slug": "panchavati_steps", "name": "Panchavati Steps", "zone_slug": "panchavati"},
    {"slug": "kalaram_temple",  "name": "Kalaram Temple",  "zone_slug": "panchavati"},
    {"slug": "tapovan_sangam",  "name": "Tapovan Sangam",  "zone_slug": "tapovan"},
    {"slug": "kushavarta_kund", "name": "Kushavarta Kund", "zone_slug": "kushavarta"},
    {"slug": "trimbak_gate",    "name": "Trimbakeshwar Temple Gate", "zone_slug": "trimbak"},
]

# ── Booths ───────────────────────────────────────────────────────────────────
# slug, name, zone_slug, lat, lng
BOOTHS: list[dict] = [
    {"slug": "ramkund_neela",   "name": "Milap Sthal – Neela Kamal", "zone_slug": "ramkund",
     "latitude": 19.9975, "longitude": 73.7898},
    {"slug": "panchavati_3",    "name": "Panchavati Booth 3",        "zone_slug": "panchavati",
     "latitude": 20.0079, "longitude": 73.7949},
    {"slug": "tapovan_1",       "name": "Tapovan Booth 1",           "zone_slug": "tapovan",
     "latitude": 20.0152, "longitude": 73.8101},
    {"slug": "kushavarta_main", "name": "Kushavarta Milap Sthal",    "zone_slug": "kushavarta",
     "latitude": 19.9320, "longitude": 73.5290},
    {"slug": "trimbak_gate_1",  "name": "Trimbak Gate Booth 1",      "zone_slug": "trimbak",
     "latitude": 19.9330, "longitude": 73.5305},
]

# ── Zone adjacency (bidirectional) ───────────────────────────────────────────
# Within-venue neighbours only — Nashik and Trimbakeshwar are ~30km apart.
ADJACENCY: list[tuple[str, str]] = [
    ("ramkund", "panchavati"),
    ("panchavati", "tapovan"),
    ("ramkund", "tapovan"),
    ("kushavarta", "trimbak"),
]


# ── Resolved-id helpers (used by both seeders) ───────────────────────────────
def zone_id(slug: str) -> uuid.UUID:
    return seed_id("zone", slug)


def booth_id(slug: str) -> uuid.UUID:
    return seed_id("booth", slug)
