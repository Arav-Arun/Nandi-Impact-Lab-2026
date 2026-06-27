# NANDI — Missing Persons Reunification System

NANDI is a missing-persons reunification backend built for the **Kumbh Mela 2027** at
Nashik / Trimbakeshwar — a gathering where tens of millions of pilgrims move through a small
number of zones and family members get separated in the crowd. Families file a *missing report*
(any language, optional photo); volunteers register *found persons* at booths. NANDI matches the
two using multilingual text embeddings (pgvector ANN search) re-ranked by face similarity and
validated against a graph of the venue topology (Neo4j: zones, landmarks, adjacency, origin
cities). A booth operator always makes the final call — the system surfaces ranked candidates with
plain-language reasons and confidence bands, and **only a human confirmation triggers an SMS** to
the family (no auto-notification, ever).

This repo is the **backend**. It is split across four members; this README documents the whole
backend but the slice owned by **Member 1** is: PostgreSQL schema + migrations, pgvector matching,
Neo4j validation, embeddings, scoring, and the `/match` + `/internal/validate` routes.

---

## Package layout

Flat top-level packages so all four members merge files into the same packages without collisions.

| Package | What it is |
|---|---|
| `core/` | Cross-cutting infrastructure: `config.py` (typed settings from `.env`), `database.py` (async SQLAlchemy engine/session), `redis_client.py`, `responses.py` (the `{data, error, timestamp}` envelope + exception handlers), `security.py` (booth/internal header guards), `logging_utils.py` (logger + phone masking). |
| `db/` | `base.py` (declarative `Base`) and `models.py` — the SQLAlchemy 2.0 models that are the source of truth for the whole system (zones, booths, groups, registrants, missing/found reports, case events). |
| `schemas/` | Pydantic request/response models. `common.py` (shared enums like `EventType`), `match.py` (match list / confirm / reject / validate payloads). |
| `services/` | Business logic. `embedding.py` (text + face vectors), `scoring.py` (composite confidence + bands), `neo4j_client.py` (graph client + validation queries), `matcher.py` (candidate retrieval + re-rank), `dedup.py`, `case_events.py` (audit log), `notify_bridge.py` (OTP + hand-off to M2's SMS sender). |
| `api/` | FastAPI app. `main.py` (app factory; auto-mounts each member's router under `/api/v1`), `deps.py` (DI: session, booth id, internal-key guard), `routes/match.py` (Member 1's endpoints). |
| `graph/` | Neo4j assets: `schema.cypher` (constraints), `seed_nashik.cypher` (generated static topology), and `queries/*.cypher` (the validation queries). |
| `scripts/` | Operational scripts: `seed_data.py` (canonical zone/booth/landmark data + deterministic UUIDs), `seed_postgres.py`, `seed_neo4j.py`, `refresh_views.py` (materialized-view refresh). |
| `migrations/` | Alembic environment + versioned migrations (`versions/`). |
| `workers/` | Reserved for Celery workers/tasks (M2). |
| `tests/` | Pytest suite (`asyncio_mode=auto`); `tests/e2e/` for end-to-end flows. |
| `docker/` | `postgres.Dockerfile` — a dev-only Postgres image bundling **PostGIS + pgvector** (no official image ships both). |

> **Ownership.** M1 = match/db/graph, M2 = intake/sms/blast, M3 = dashboard/UI, M4 = auth/ws/infra.
> `api/main.py` imports each router defensively, so the app boots with only the routers that have
> been merged so far — a missing route file is skipped, a *broken* one is logged loudly.

---

## Prerequisites

- **Python 3.11** (a working virtualenv already exists at `.venv`).
- **PostgreSQL 16** with the **pgvector** and **PostGIS** extensions (plus `pgcrypto`, used by the
  migration). Use the bundled `docker/postgres.Dockerfile` for local dev.
- **Neo4j 5.x** (Bolt on `:7687`).
- **Redis 7.x** (broker / OTP store / rate limiting; used by other members).
- **Docker** (optional but recommended) for the three datastores.

> **Embeddings need no GPU or model download by default** — see [the EMBEDDING_FALLBACK story](#the-embedding_fallback-story).

---

## Quickstart

```bash
# 1. From the repo root, activate the pre-built virtualenv
source .venv/bin/activate

# 2. Create your local env file and edit the secrets
cp .env.example .env
#    Defaults point at localhost Postgres/Neo4j/Redis and EMBEDDING_FALLBACK=1.

# 3. Bring up the datastores (see next section), then:
alembic upgrade head            # create the schema + extensions + HNSW indexes
python -m scripts.seed_postgres # zones + booths
python -m scripts.seed_neo4j    # graph schema + static Nashik topology

# 4. Run the API
uvicorn api.main:app --reload
#    → http://127.0.0.1:8000/docs   (interactive Swagger UI)
```

The dependency list lives in `requirements.txt`. If you ever need to rebuild the venv:

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

---

## Bringing up Postgres / Neo4j / Redis

NANDI needs three datastores. Two ways to run them:

**1. Root `docker-compose.yml` (dev convenience).**
A root-level `docker-compose.yml` is being added by the dev-compose author. It wires up:

- **Postgres** built from `docker/postgres.Dockerfile` (PostGIS **and** pgvector in one image),
- **Neo4j 5.x** (Bolt `:7687`, browser `:7474`),
- **Redis 7.x** (`:6379`).

Once it lands:

```bash
docker compose up -d        # postgres + neo4j + redis
docker compose ps           # confirm all three are healthy
docker compose down         # stop them (add -v to wipe volumes)
```

If the compose file isn't present yet, you can still build/run the dev Postgres image directly:

```bash
docker build -f docker/postgres.Dockerfile -t nandi-postgres docker/
docker run -d --name nandi-pg -p 5432:5432 \
  -e POSTGRES_USER=nandi -e POSTGRES_PASSWORD=password -e POSTGRES_DB=nandi \
  nandi-postgres
```

The default `.env` URLs already match this (`localhost:5432`, `nandi/password/nandi`,
`bolt://localhost:7687`, `redis://localhost:6379/0`).

**2. Canonical infra (`infra/`) — owned by Member 4.**
The dev `docker-compose.yml` above is for getting a backend dev unblocked locally. The
**canonical infrastructure stack lives in `infra/` and is owned by M4** (staging/prod
networking, secrets, healthchecks, persistence). Use that for anything beyond local development;
do not duplicate or override it from the backend packages.

---

## Database migrations (Alembic)

The database URL is **not** stored in `alembic.ini` — `migrations/env.py` injects it at runtime
from `settings.SYNC_DATABASE_URL`, which derives a sync (psycopg2) URL from your single
`DATABASE_URL`. So you only configure the database in one place (`.env`).

```bash
alembic upgrade head            # apply all migrations
alembic current                # show the current revision
alembic downgrade -1           # roll back one revision
alembic revision -m "msg"      # author a new migration (filename is date_rev_slug)
```

The initial migration (`migrations/versions/20270101_0001_initial_schema.py`) runs
`CREATE EXTENSION IF NOT EXISTS` for `vector`, `postgis`, and `pgcrypto`, then builds all tables
plus the HNSW vector indexes, the partial `status` index, and the `zone_case_summary`
materialized view (these are raw SQL because SQLAlchemy can't express HNSW opclasses).

---

## Seeding

The seed data (zones, booths, landmarks, adjacency) lives in `scripts/seed_data.py` and uses
**deterministic UUIDs**, so a zone's id in Postgres equals the same zone's id in Neo4j — which is
exactly what the zone-plausibility graph check relies on. All seeds are **idempotent** (insert /
`MERGE` only what's missing).

```bash
# PostgreSQL: insert zones + booths (run AFTER `alembic upgrade head`)
python -m scripts.seed_postgres

# Neo4j: apply graph constraints + seed the static Nashik/Trimbakeshwar topology
python -m scripts.seed_neo4j
```

`seed_neo4j` can also **regenerate the committed reference Cypher** without touching any database
or needing the Neo4j driver — it rebuilds `graph/seed_nashik.cypher` straight from `seed_data.py`
so the checked-in file can never drift:

```bash
python -m scripts.seed_neo4j --emit-cypher graph/seed_nashik.cypher
```

Runtime nodes (missing/found reports, persons, phones) are **not** seeded — they are `MERGE`d on
the fly by `services/neo4j_client.py`.

### Refreshing the dashboard view

The `zone_case_summary` materialized view (powers M3's zone aggregates) needs periodic refresh:

```bash
python -m scripts.refresh_views            # one-shot (cron / pg_cron / CI)
python -m scripts.refresh_views --loop     # daemon loop (every MATVIEW_REFRESH_SECONDS, default 300s)
```

---

## Running the API

```bash
uvicorn api.main:app --reload
```

- Interactive docs (Swagger UI): **http://127.0.0.1:8000/docs**
- OpenAPI JSON: `http://127.0.0.1:8000/openapi.json`
- Liveness probe: `GET /health`

All routers mount under `/api/v1`. Member 1's endpoints:

| Method & path | Auth | Purpose |
|---|---|---|
| `GET /api/v1/match/{found_id}` | — | Ranked candidate missing reports for a found person (scores, bands, reasons; candidates below `MATCH_MIN_CONFIDENCE` are not surfaced). |
| `POST /api/v1/match/confirm` | `X-Booth-ID` | Operator confirms one candidate — updates both reports, writes the Neo4j `MATCHED_TO` edge, audits, and dispatches the OTP/SMS. The **only** path that notifies. |
| `POST /api/v1/match/reject` | `X-Booth-ID` | Operator rejected all surfaced candidates (logged; the found report stays unmatched). |
| `POST /api/v1/internal/validate` | `X-Internal-Key` | Server-to-server graph signals for one (missing, found) pair. |

Every response uses the shared envelope: `{ "data": ..., "error": null, "timestamp": <ISO8601> }`.
Booth routes require the `X-Booth-ID` header; `/internal/*` routes require `X-Internal-Key`.

---

## Running tests

```bash
pytest                  # full suite
pytest -v               # verbose
pytest tests/e2e        # end-to-end flows
```

`pyproject.toml` sets `asyncio_mode=auto` (async tests need no explicit marker) and points
`testpaths` at `tests/`. Tests run end-to-end in fallback embedding mode, so they need no GPU or
model download (a live Postgres/Neo4j may still be required for integration-level tests).

---

## The EMBEDDING_FALLBACK story

Embeddings are produced by `services/embedding.py`:

- `embed_text(text, kind="passage"|"query")` → a 1024-dim vector (multilingual-e5-large), and
- `embed_face(image_bytes)` → a 512-dim vector (InsightFace `buffalo_l` / ArcFace).

The real models are multi-gigabyte and GPU-friendly. To keep the entire stack buildable on a
laptop — and so no teammate is ever blocked on a model download — `EMBEDDING_FALLBACK` **defaults
to on (`1`/`True`)**. In fallback mode the embedder is a **deterministic stub**: it hashes the input
to seed a fixed unit vector, so identical text yields an identical vector (cosine 1.0) and the
matching pipeline and tests run reproducibly end-to-end. The stub is *not* semantic — similar text
is not "close" — but every code path works without `torch` / `sentence-transformers` /
`insightface` installed. The module also lazy-loads the real model only on first use and
auto-falls-back if it can't be loaded.

**For the demo box** (real multilingual semantics + real face recognition):

1. Install the heavy deps — `sentence-transformers` is already pinned in `requirements.txt`;
   uncomment `insightface` / `onnxruntime` there for real faces.
2. In `.env`, set:

   ```ini
   EMBEDDING_FALLBACK=0
   EMBEDDING_DEVICE=cpu      # or "cuda" / "mps" if you have a GPU
   ```

3. Restart the API. The first embedding call downloads/loads the model; subsequent calls reuse it.

> The current `.venv` does **not** include `torch` / `sentence-transformers` / `insightface`, so it
> runs in fallback mode out of the box.

---

## Configuration reference

All settings are read once from `.env` via `core/config.py` (`from core.config import settings`).
Never read `os.environ` directly elsewhere. Copy `.env.example` → `.env`; the field names are the
canonical contract shared by all members. Member-1-specific knobs (with safe defaults) include
`MATCH_AGE_WINDOW`, `MATCH_CANDIDATE_LIMIT`, `MATCH_RETURN_LIMIT`, `MATCH_MIN_CONFIDENCE` (0.60
surface floor), `PGVECTOR_EF_SEARCH` (HNSW recall/latency), and `MATVIEW_REFRESH_SECONDS`.
# Nandi-Impact-Lab-2026
