# NANDI — Member 1 Integration Contract

This is the cross-member integration contract for **Member 1's slice** (matching, DB/graph,
embeddings, scoring). M2 (intake/SMS/blast), M3 (dashboard/UI), and M4 (auth/ws/infra) can wire
to M1 using only this document — no need to read M1's source.

Everything here reflects the code as it exists today. File paths are repo-relative to
`/Users/bhoumiksangle/Desktop/Nandi`.

---

## 0. Shared infra contracts (read this first)

### 0.1 Response envelope (SoW §12.1)

Every M1 route returns the standard envelope from `core/responses.py`. **Never** assume a bare
payload — always unwrap `data`.

**Success:**
```json
{
  "data": { "...": "endpoint-specific payload" },
  "error": null,
  "timestamp": "2026-06-27T10:15:30.123456Z"
}
```

**Error:**
```json
{
  "data": null,
  "error": { "code": "FOUND_NOT_FOUND", "message": "found report not found" },
  "timestamp": "2026-06-27T10:15:30.123456Z"
}
```

- `timestamp` is UTC ISO-8601 with a trailing `Z`.
- To emit the envelope yourself: `from core.responses import ok, err, ApiError`.
  - `ok(data)` → success body.
  - Raise `ApiError(code, message, http_status=400)` for any handled failure; the registered
    exception handlers render it as the error envelope. M4 wires
    `register_exception_handlers(app)` at app construction.
- Validation failures (Pydantic) auto-render as `{"code": "VALIDATION_ERROR", ...}` at HTTP 422.
- Any unhandled exception renders as `{"code": "INTERNAL_ERROR", ...}` at HTTP 500 (no stack
  trace leaked).

### 0.2 Headers

| Header           | Required on                       | Enforced by (`core/security.py`)        | Failure code / status |
|------------------|-----------------------------------|------------------------------------------|------------------------|
| `X-Booth-ID`     | All booth-facing routes (`/match/confirm`, `/match/reject`) | `get_booth_id` | `BOOTH_ID_REQUIRED` (400) if absent; `BOOTH_ID_INVALID` (400) if not a UUID |
| `X-Internal-Key` | All `/internal/*` routes (`/internal/validate`) | `require_internal_key` | `UNAUTHORIZED_INTERNAL` (401) if missing/mismatched |

- `X-Booth-ID` **must be a valid UUID string**; it is parsed to `uuid.UUID` and attributed in the
  audit trail.
- `X-Internal-Key` must exactly equal `settings.INTERNAL_KEY` (env `INTERNAL_KEY`, default
  `dev-internal-key-change-me`).
- `GET /match/{found_id}` currently does **not** require `X-Booth-ID` in code (only `confirm` and
  `reject` do).

### 0.3 Env vars

All config is in `core/config.py` as `settings`, mapping 1:1 to `.env.example`. **Never read
`os.environ` directly** — add a field to `core/config.py` instead. Names other members rely on:

| Env var | Default | Owner | Used by M1 for |
|---------|---------|-------|----------------|
| `DATABASE_URL` | `postgresql+asyncpg://nandi:password@localhost:5432/nandi` | shared | async DB; `settings.SYNC_DATABASE_URL` derives the psycopg2 URL for Alembic |
| `NEO4J_URI` / `NEO4J_USER` / `NEO4J_PASSWORD` | `bolt://localhost:7687` / `neo4j` / `changeme` | shared | graph client |
| `REDIS_URL` | `redis://localhost:6379/0` | shared | OTP store |
| `INTERNAL_KEY` | `dev-internal-key-change-me` | M1 | guards `/internal/*` |
| `OTP_TTL_SECONDS` | `14400` (4h) | M2 | OTP TTL in the fallback OTP store |
| `EMBEDDING_MODEL` | `intfloat/multilingual-e5-large` | M1 | text model name |
| `EMBEDDING_DIM` | `1024` | M1 | **text vector length** |
| `FACE_MODEL` | `buffalo_l` | M1 | face model name |
| `FACE_EMBEDDING_DIM` | `512` | M1 | **face vector length** |
| `EMBEDDING_FALLBACK` | `True` | M1 | `True` → deterministic stub embedder (no model download) |
| `EMBEDDING_DEVICE` | `cpu` | M1 | model device |
| `MATCH_AGE_WINDOW` | `15` | M1 | ± years around found age |
| `MATCH_CANDIDATE_LIMIT` | `10` | M1 | top-N from pgvector pre re-rank |
| `MATCH_RETURN_LIMIT` | `3` | M1 | candidates shown to operator |
| `MATCH_MIN_CONFIDENCE` | `0.60` | M1 | surface floor (below → not returned) |
| `PGVECTOR_EF_SEARCH` | `64` | M1 | HNSW ef_search |
| `MATVIEW_REFRESH_SECONDS` | `300` | M1 | materialized-view refresh cadence |
| `MSG91_AUTH_KEY` / `MSG91_SENDER_ID` / `GUPSHUP_API_KEY` | `""` / `NANDIK` / `""` | M2 | SMS senders (keys declared here per shared contract) |
| `EXOTEL_*` | `""` | M2 | IVR |
| `AWS_S3_BUCKET` / `AWS_REGION` | `nandi-media` / `ap-south-1` | M4 | media storage |
| `JWT_SECRET` / `JWT_EXPIRY_HOURS` | `""` / `8` | M4 | dashboard auth |

The canonical reference for all env vars is **`.env.example`**.

### 0.4 ID and embedding rules

- **All IDs are UUIDs** (`uuid.UUID` in Python, UUID string on the wire). This includes
  `found_id`, `missing_id`, `booth_id`, `operator_id`-as-attribution (operator_id itself is a free
  string, see below), zone ids, etc.
- **Embedding dimensions are fixed:** text = `1024` (`EMBEDDING_DIM`), face = `512`
  (`FACE_EMBEDDING_DIM`). Vectors are L2-normalised `list[float]`.
- `operator_id` in confirm/reject bodies is an **optional free-form string** (not a UUID) — it is
  only logged in the audit trail.

---

## 1. Endpoints M1 EXPOSES

All mounted under `/api/v1`. Routers: `router` (prefix `/match`) and `internal_router`
(prefix `/internal`), both in `api/routes/match.py`.

### 1.1 `GET /api/v1/match/{found_id}` — ranked candidates

Returns the top candidate missing reports for a registered found person. Candidates below the
surface floor (`MATCH_MIN_CONFIDENCE`, default 0.60) are not returned. Best candidate first.

- **Method:** GET
- **Path param:** `found_id` — UUID of an existing `found_reports` row.
- **Headers:** none enforced in code (no `X-Booth-ID` required here today).
- **Body:** none.

**Success response** (`MatchListResponse`):
```json
{
  "data": {
    "found_id": "8f1c4d2a-0000-4000-8000-000000000001",
    "candidates": [
      {
        "missing_id": "a1b2c3d4-0000-4000-8000-000000000010",
        "subject_name": "Aarav",
        "subject_age": 7,
        "subject_gender": "male",
        "physical_description": "red t-shirt, blue shorts, mole on left cheek",
        "last_seen_landmark": "Ramkund",
        "last_seen_zone_id": "11111111-0000-4000-8000-000000000001",
        "filed_at": "2026-06-27T08:30:00Z",
        "photo_url": "https://nandi-media.s3.ap-south-1.amazonaws.com/missing/abc.jpg",
        "origin_city": "Nashik",
        "vector_score": 0.91,
        "confidence": 0.97,
        "band": "high",
        "reasons": ["Same zone ✓", "Same day ✓", "Language spoken matches ✓"]
      }
    ]
  },
  "error": null,
  "timestamp": "2026-06-27T10:15:30.123456Z"
}
```

Per-candidate field notes (`MatchCandidate` in `schemas/match.py`):
- `subject_name`, `subject_age`, `subject_gender`, `last_seen_landmark`, `last_seen_zone_id`,
  `photo_url`, `origin_city` are all **nullable**.
- `physical_description` is a required string; `filed_at` is a required datetime.
- `vector_score`: raw pgvector cosine similarity, 0..1.
- `confidence`: composite score after graph modifiers, 0..1.
- `band`: a `ConfidenceBand` enum value serialized as one of exactly **`"high"`** (≥0.90, 🟢),
  **`"probable"`** (0.75–0.89, 🟡), or **`"possible"`** (0.60–0.74, ⚪). Candidates below 0.60 are
  never returned, so `band` is always one of those three. Defined in `schemas/common.py`.
- `reasons`: list of plain-language label strings exactly as shown to the operator, e.g.
  `"Same zone ✓"`, `"Same city of origin ✓"`, `"⚠ Different venue"` (may be empty). Full set in
  `services/scoring.py:MODIFIERS`.

**Errors:**

| Condition | code | HTTP |
|-----------|------|------|
| `found_id` does not exist | `FOUND_NOT_FOUND` | 404 |
| Malformed UUID in path | `VALIDATION_ERROR` | 422 |

### 1.2 `POST /api/v1/match/confirm` — human confirmation gate

Operator confirms exactly one candidate. **This is the only path that triggers a match SMS**
(no auto-notification, ever — SoW §12.8 #1). In one transaction it:
1. Sets `missing.status='matched'` + `missing.matched_found_id`, and `found.status='matched'` +
   `found.matched_report_id`.
2. Writes the `MATCHED_TO` edge in Neo4j (best-effort).
3. Logs a `matched` audit event.
4. Generates an OTP and dispatches the Marathi match SMS to the filer via the M2 bridge.

- **Method:** POST
- **Headers:** `X-Booth-ID: <uuid>` **(required)**.
- **Body** (`ConfirmRequest`):
```json
{
  "found_id": "8f1c4d2a-0000-4000-8000-000000000001",
  "missing_id": "a1b2c3d4-0000-4000-8000-000000000010",
  "operator_id": "officer-meena"
}
```
- `operator_id` is optional (free-form string, logged for attribution).

**Success response** (`ConfirmResponse`):
```json
{
  "data": {
    "found_id": "8f1c4d2a-0000-4000-8000-000000000001",
    "missing_id": "a1b2c3d4-0000-4000-8000-000000000010",
    "matched": true,
    "otp_dispatched": true,
    "booth_name": "Ramkund Booth 3",
    "zone_name": "Ramkund Ghat",
    "notify_detail": null
  },
  "error": null,
  "timestamp": "2026-06-27T10:15:30.123456Z"
}
```
- `otp_dispatched`: `true` only if the SMS was handed to a real M2 sender. If M2's SMS service is
  not yet present (or failed), it is `false` and `notify_detail` is
  `"SMS not dispatched (notifier unavailable)"`. The match is still recorded regardless — SMS is
  best-effort and never blocks confirmation.
- `booth_name` / `zone_name`: the destination the family should travel to (where the found person
  is). Resolved from the found report's `registered_at_booth` (falling back to `current_zone_id`);
  either may be `null`.

**Errors:**

| Condition | code | HTTP |
|-----------|------|------|
| `missing_id` not found | `MISSING_NOT_FOUND` | 404 |
| `found_id` not found | `FOUND_NOT_FOUND` | 404 |
| Missing report already matched to a *different* found | `ALREADY_MATCHED` | 409 |
| Found report already matched to a *different* missing | `ALREADY_MATCHED` | 409 |
| Missing `X-Booth-ID` | `BOOTH_ID_REQUIRED` | 400 |
| Invalid `X-Booth-ID` UUID | `BOOTH_ID_INVALID` | 400 |
| Body validation | `VALIDATION_ERROR` | 422 |

Note: confirming the **same** pair again is idempotent (does not raise `ALREADY_MATCHED`).

### 1.3 `POST /api/v1/match/reject` — operator rejected all candidates

Records that none of the surfaced candidates matched. The found report stays/returns to
`unmatched` (so M2's blast scheduler escalates it on the normal T+24h / T+72h timeline). Only an
audit event is written.

- **Method:** POST
- **Headers:** `X-Booth-ID: <uuid>` **(required)**.
- **Body** (`RejectRequest`):
```json
{
  "found_id": "8f1c4d2a-0000-4000-8000-000000000001",
  "operator_id": "officer-meena",
  "rejected_missing_ids": [
    "a1b2c3d4-0000-4000-8000-000000000010",
    "a1b2c3d4-0000-4000-8000-000000000011"
  ]
}
```
- `operator_id` optional. `rejected_missing_ids` optional (list of the candidate UUIDs shown, for
  the audit log; defaults to `[]`).

**Success response** (`RejectResponse`):
```json
{
  "data": {
    "found_id": "8f1c4d2a-0000-4000-8000-000000000001",
    "status": "unmatched"
  },
  "error": null,
  "timestamp": "2026-06-27T10:15:30.123456Z"
}
```
- `status` is left as `matched` only if the found report was already matched; otherwise it is
  forced to `unmatched`.

**Errors:**

| Condition | code | HTTP |
|-----------|------|------|
| `found_id` not found | `FOUND_NOT_FOUND` | 404 |
| Missing/invalid `X-Booth-ID` | `BOOTH_ID_REQUIRED` / `BOOTH_ID_INVALID` | 400 |
| Body validation | `VALIDATION_ERROR` | 422 |

### 1.4 `POST /api/v1/internal/validate` — graph signals (server-to-server)

Runs the Neo4j validation checks for one `(missing, found)` pair and returns the `graph_signals`
dict consumed by the composite score. Internal step of the match pipeline — not user-facing.

- **Method:** POST
- **Headers:** `X-Internal-Key: <settings.INTERNAL_KEY>` **(required)**.
- **Body** (`ValidateRequest`):
```json
{
  "missing_id": "a1b2c3d4-0000-4000-8000-000000000010",
  "found_id": "8f1c4d2a-0000-4000-8000-000000000001",
  "filer_phone": "+919812345678"
}
```
- `filer_phone` optional (enables the city/group-of-origin check).

**Success response** (`ValidateResponse` → `GraphSignals`):
```json
{
  "data": {
    "graph_signals": {
      "same_zone": true,
      "adjacent_zone": false,
      "same_venue": true,
      "different_venue": false,
      "same_city": true,
      "same_state": true,
      "temporal_very_recent": false,
      "temporal_same_day": true,
      "temporal_stale": false,
      "landmark_pattern_match": false,
      "language_match": false,
      "possible_duplicate": false
    }
  },
  "error": null,
  "timestamp": "2026-06-27T10:15:30.123456Z"
}
```
- Every signal is a boolean and **defaults to `false`**. If Neo4j is down, all values are `false`
  (graceful degradation) and the call still succeeds.
- `language_match` is present on the schema but is computed by the matcher from SQL records; the
  `/internal/validate` path returns it as its default (`false`) — do not rely on it here.

**Errors:**

| Condition | code | HTTP |
|-----------|------|------|
| Missing/invalid `X-Internal-Key` | `UNAUTHORIZED_INTERNAL` | 401 |
| Body validation | `VALIDATION_ERROR` | 422 |

---

## 2. Functions M1 EXPECTS Member 2 to implement (notify_bridge contract)

`services/notify_bridge.py` is the M1↔M2 hand-off. On confirm, M1 calls **its own bridge
functions** (`notify_bridge.generate_otp` and `notify_bridge.send_match_sms`), which in turn call
M2's modules **when they exist** and degrade to a safe local fallback when they don't. M2 must
implement these **exact signatures** so the bridge picks them up automatically with no route
change.

### 2.1 `services/otp.py` — M2 implements:
```python
async def generate_and_store(case_id: str) -> str:
    """
    4-digit OTP, stored in Redis at key f"otp:{case_id}",
    TTL = settings.OTP_TTL_SECONDS. Returns the OTP string.
    """
```
- May be sync or async — the bridge awaits coroutines and calls plain functions transparently.
- The bridge calls this via `generate_otp(case_id)` where **`case_id` is `str(missing.id)`** (the
  family's missing-report UUID as a string). M2's verify-OTP endpoint must read the same
  `otp:{case_id}` key.

**Redis key convention:** `otp:{case_id}` — value is the 4-digit code, TTL = `OTP_TTL_SECONDS`
(default 14400s = 4h). If M2's `services.otp` is absent, M1's fallback writes exactly this key
(`code = f"{secrets.randbelow(10000):04d}"`), so M2's verify path works against either
implementation.

### 2.2 `services/sms.py` — M2 implements:
```python
async def send_match_notification(
    phone: str, booth_name: str, zone_name: str, otp: str
) -> bool:
    """
    Send the Marathi match SMS via MSG91 (Gupshup fallback).
    Returns True on accepted-for-delivery.
    """
```
- May be sync or async.
- The bridge calls it **positionally** as
  `send_match_notification(phone, booth_name, zone_name, otp)`. Keep the parameter order.
- Return `True` if handed to a real sender; the route surfaces this as `otp_dispatched`.
- `phone` is `missing.filed_by_phone` (the family member who filed the report).
- If `services.sms` is absent, M1 logs a masked no-op and returns `False` — confirmation still
  succeeds.

**When M1 calls these:** only inside `POST /match/confirm`, step 4, after both report rows are
flipped to `matched`, the graph edge is written, and the `matched` audit event is logged.

---

## 3. Functions M1 PROVIDES for others

Import these directly; they are the supported integration surface.

### 3.1 Embeddings — `services/embedding.py` (M2 intake calls these)

```python
def embed_text(text: str, kind: str = "passage") -> list[float]
def embed_face(image_bytes: bytes) -> list[float] | None
def cosine_similarity(a: list[float], b: list[float]) -> float
```

- `embed_text` → list of length **1024** (`EMBEDDING_DIM`), L2-normalised.
  - `kind="passage"` for stored documents, `kind="query"` for search inputs (e5 asymmetric
    prefix, SoW §12.5). Anything other than `"query"` is treated as `"passage"`.
  - **M2 intake must embed stored descriptions with `kind="passage"`** so they match M1's query
    embedding convention.
- `embed_face` → list of length **512** (`FACE_EMBEDDING_DIM`), or `None` when no face is detected
  (photos are optional everywhere). In stub/fallback mode a deterministic vector is always
  returned (hash of the bytes).
- `cosine_similarity` → float in `[-1, 1]`; `0.0` if either vector is empty/zero.
- With `EMBEDDING_FALLBACK=True` (default), these run a deterministic hash-based stub: identical
  text → identical vector (cosine 1.0), but **not semantically similar** across different text.
  Fine for wiring and tests; flip to `0` on the demo box with the real model installed.

### 3.2 Graph node sync — `services/neo4j_client.py` (M2 intake)

Use the module singleton: `from services.neo4j_client import neo4j_client`. **M2 intake should
call these after writing the SQL row** so validation queries have something to traverse. All MERGE
→ idempotent / safe to re-run (including offline-sync replays). All keyword-only args.

```python
await neo4j_client.sync_missing_report(
    report_id=...,            # uuid.UUID
    filed_at=...,             # datetime | None
    status=...,               # str
    subject_name=...,         # str | None
    subject_age=...,          # int | None
    subject_gender=...,       # str | None
    origin_city=...,          # str | None
    language_spoken=...,      # str | None
    last_seen_time=...,       # datetime | None
    last_seen_landmark=...,   # str | None
    last_seen_zone_id=...,    # uuid.UUID | None
    booth_id=...,             # uuid.UUID | None
    filer_phone=...,          # str | None
) -> None

await neo4j_client.sync_found_report(
    report_id=...,            # uuid.UUID
    found_at=...,             # datetime | None
    status=...,               # str
    name_if_known=...,        # str | None
    approximate_age=...,      # int | None
    gender=...,               # str | None
    apparent_city_origin=..., # str | None
    language_spoken=...,      # str | None
    booth_id=...,             # uuid.UUID | None
    current_zone_id=...,      # uuid.UUID | None
) -> None
```

These never raise on a Neo4j outage — they log a warning and no-op.

### 3.3 Duplicate flagging — `services/dedup.py` (M2 intake)

```python
async def flag_duplicates_on_intake(session: AsyncSession, report: MissingReport) -> int
```
- **M2 intake should call this AFTER the SQL row + graph node exist.** It checks the new missing
  report for likely duplicates (same gender, age within ±5, fuzzy name overlap via Neo4j), and if
  any are found logs a `duplicate_flagged` audit event.
- **Non-blocking:** returns the duplicate count (0 on none or any error). Does **not** change the
  report's status — humans decide whether to merge.
- Takes the live request `AsyncSession` and a `db.models.MissingReport` instance.

Lower-level helper (also available): `find_duplicate_missing(*, current_id, subject_name,
subject_age, subject_gender) -> tuple[int, list[str]]`.

### 3.4 Dashboard landmark patterns — `services/neo4j_client.py` (M3 data source)

M3 owns the HTTP route `GET /dashboard/patterns`; this is the data source it calls.

```python
await neo4j_client.landmark_patterns(min_times: int = 1, limit: int = 50) -> list[dict]
```

**Exact return shape** — a list of dicts:
```python
[
    {"from_landmark": "Ramkund",    "to_landmark": "Booth 3 - Panchavati", "count": 12},
    {"from_landmark": "Kalaram",    "to_landmark": "Booth 1 - Tapovan",    "count": 5},
]
```
- `from_landmark`: str | None — landmark where people were last seen.
- `to_landmark`: str | None — the booth where they typically turned up (Panel 4 annotation).
- `count`: int — number of confirmed matches following that flow (aggregated across confirmed
  `MATCHED_TO` edges).
- Returns `[]` if Neo4j is unavailable.

### 3.5 Audit writer — `services/case_events.py` (shared)

```python
async def log_event(
    session: AsyncSession,
    *,
    report_id: uuid.UUID,                 # missing OR found report id
    event_type: EventType | str,          # schemas.common.EventType (or its string value)
    booth_id: uuid.UUID | None = None,
    operator_id: str | None = None,
    metadata: dict | None = None,
    flush: bool = True,
) -> CaseEvent
```
- **All members must route audit rows through this** (e.g. M2's blast worker logging
  `blast_zone_sent`) rather than inserting `case_events` rows by hand, so the vocabulary and
  phone-masking stay consistent.
- Phone safety net: metadata keys in `{"phone", "filer_phone", "filed_by_phone", "leader_phone",
  "to", "msisdn"}` are auto-masked before being persisted (SoW §12.8 #2 — no plaintext phones).
- `flush=True` assigns the id without committing (the request session commits at the end). Set
  `flush=False` inside a larger unit of work.
- `event_type` values come from `schemas/common.py:EventType` (e.g. `matched`,
  `operator_rejected`, `duplicate_flagged`). Read that enum for the full vocabulary.

### 3.6 Materialized-view refresh — `scripts/refresh_views.py` (M2 may register as a Celery task)

```python
async def refresh_zone_case_summary() -> None
```
- Refreshes the `zone_case_summary` materialized view that powers M3's dashboard zone aggregates.
  Must run on a cadence (SoW §5.1: every 5 min; `MATVIEW_REFRESH_SECONDS`, default 300).
- **M2 can register this as a Celery beat task:** `await refresh_zone_case_summary()`.
- Also runnable standalone:
  - one-shot: `python -m scripts.refresh_views`
  - daemon loop: `python -m scripts.refresh_views --loop [--interval N]`
- Uses `REFRESH MATERIALIZED VIEW CONCURRENTLY` (autocommit), falling back to a plain refresh if a
  unique index isn't present yet. Safe to call repeatedly.

---

## 4. Merge order / who-owns-what-file

`api/routes/` and `services/` are **shared directories** — M1 owns only specific files in them.
Do **not** modify M1's files in the Author phase; add your own files alongside.

| Path | Owner | Notes |
|------|-------|-------|
| `core/config.py` | M1 (shared) | Single config source. Add fields here, don't read `os.environ`. |
| `core/responses.py`, `core/security.py`, `core/database.py`, `core/redis_client.py`, `core/logging_utils.py` | M1 (shared) | Envelope, auth deps, DB/Redis clients, logging. |
| `db/base.py`, `db/models.py` | M1 | SQLAlchemy models. |
| `schemas/common.py`, `schemas/match.py` | M1 | `EventType`, `ConfidenceBand`, match request/response models. |
| `services/embedding.py` | M1 (in shared dir) | `embed_text` / `embed_face` / `cosine_similarity`. |
| `services/scoring.py`, `services/matcher.py` | M1 (in shared dir) | Composite scoring + candidate selection. |
| `services/neo4j_client.py` | M1 (in shared dir) | Graph sync, validation, landmark patterns. |
| `services/dedup.py` | M1 (in shared dir) | `flag_duplicates_on_intake`. |
| `services/case_events.py` | M1 (in shared dir) | Shared audit writer. |
| `services/notify_bridge.py` | M1 (in shared dir) | Calls M2's `otp`/`sms` when present. |
| **`services/otp.py`** | **M2** (new file in shared dir) | `generate_and_store(case_id)` — §2.1. |
| **`services/sms.py`** | **M2** (new file in shared dir) | `send_match_notification(...)` — §2.2. |
| `api/main.py`, `api/deps.py`, `api/routes/match.py` | M1 (routes/ is shared) | M1 owns only `match.py` under `routes/`. |
| **`api/routes/intake.py`, `registrant.py`, `webhooks.py`, `sync.py`** | **M2** (new files in shared dir) | Just expose a module-level `router` (APIRouter) — `api/main.py` auto-mounts ANY file under `routes/`. No edit to `main.py`. |
| **`api/routes/dashboard.py`** | **M3** (new file in shared dir) | Expose `router`; auto-mounts. Calls `neo4j_client.landmark_patterns` (§3.4) and `zone_case_summary`. |
| **`api/routes/auth.py`, `media.py`, `ws.py`** | **M4** (new files in shared dir) | Expose `router`; auto-mounts. |
| `scripts/refresh_views.py` | M1 | Registerable as a Celery task by M2 (§3.6). |
| `graph/`, `migrations/`, `alembic.ini` | M1 | Cypher, Alembic migrations. |

**Suggested merge order:**
1. **M1 first** — schema/migrations, config, envelope, embeddings, graph client, match routes
   (everything here exists today and runs with stub embedder + graceful Neo4j/Redis degradation).
2. **M2** — add `services/otp.py` + `services/sms.py` (notify_bridge auto-detects them), intake
   routes calling `embed_text`/`sync_*_report`/`flag_duplicates_on_intake`, blast worker calling
   `log_event`, and register `refresh_zone_case_summary` in Celery beat.
3. **M3** — dashboard routes consuming `neo4j_client.landmark_patterns` and `zone_case_summary`,
   plus the booth PWA rendering `GET /match/{found_id}` → confirm/reject.
4. **M4** — auth (JWT), websockets, infra/storage. Note: router mounting is already
   directory-driven in `api/main.py` (any `routes/*.py` exposing a `router` auto-mounts under
   `/api/v1`), so M4 does **not** need to register routers — just drop the file in.
