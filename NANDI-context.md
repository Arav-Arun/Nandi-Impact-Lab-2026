# 🐂 NANDI — Project Context for Claude

> **Purpose of this file:** A single, dense, well-structured brief so that any Claude session (chat or Claude Code) can be dropped into this project and immediately understand the problem, architecture, conventions, and current decisions — without re-reading a 1300-line spec.

---

## 0. One-Paragraph Summary

**NANDI** is a missing-persons reunification system being built for the **Simhastha Kumbh Mela 2027** in Nashik–Trimbakeshwar (estimated 8–10 crore pilgrims). It's a **hackathon build (48–72 hrs, team of 4)**. Families report missing people at booths/WhatsApp/IVR → descriptions get embedded into vectors → when a found person is registered, the system finds semantically similar missing reports via **pgvector**, validates plausibility via **Neo4j graph queries**, shows a booth operator the top 3 candidates with a confidence score, and **only on human confirmation** sends an SMS with location + OTP. Unresolved cases escalate to zone-wide, then event-wide SMS blasts. A read-only dashboard gives police/officials live visibility.

**Confirmed stack (per your note):** Backend API = **FastAPI** (Python). Frontend (dashboard + booth PWA) = **React**.

---

## 1. Problem & Constraints (Why This System Exists)

- **Scale:** 8–10 crore pilgrims vs. 30 lakh resident city. Peak single-day crowd: up to 1 crore (Shahi Snan days: Aug 2, Aug 31, Sep 11–12, 2027).
- **Baseline crisis rate:** At 2025 Maha Kumbh (Prayagraj), 200–300 people reported missing *per day*.
- **Current (broken) solutions:** PA announcements, paper registers, ad hoc social media, word-of-mouth — none scale, none talk to each other, none learn.
- **Demographic reality (drives every design decision):**
  | Constraint | Detail |
  |---|---|
  | Language | Marathi 80%, Hindi 15%, Telugu/Kannada/Bhojpuri remainder |
  | Literacy | Urban ~89%, rural/tribal pilgrims ~68–71% |
  | Tech literacy | Assume **feature phones** as baseline, not smartphones |
  | Network | Will **collapse** on Shahi Snan peak days |
  | Venues | Two sites, ~30km apart: Ramkund (Nashik) & Kushavarta Kund (Trimbakeshwar) |
  | Travel pattern | Pilgrims move in bus/temple/village groups — group identity matters |
  | High-risk groups | Children <12, elderly 65+, solo travelers |

- **Golden Rule:** System must **degrade gracefully**. If all tech fails, physical wristbands + booth volunteers still work. Tech *amplifies*, never replaces, the manual layer.

---

## 2. Solution Shape

Three databases, clean separation of concerns:

| Layer | Tool | Job |
|---|---|---|
| **Intake** | Booth Tablet (PWA), WhatsApp Bot (Gupshup), Missed-call IVR (Exotel) | Capture missing/found reports in any language |
| **Match** | PostgreSQL + pgvector | Semantic similarity search on multilingual text/photo embeddings |
| **Validate** | Neo4j | Graph-based plausibility checks (zone, time, origin, learned patterns) |
| **Notify** | SMS (MSG91/Gupshup) | Direct alert to filer on confirmed match; escalating blasts if unresolved |
| **Command** | React Dashboard | Read-only live view for police/officials |

**Critical rule: human-in-the-loop.** The system *never* auto-notifies. A booth operator always sees top-3 candidates with confidence scores + plain-language reasons and must explicitly CONFIRM or REJECT. This is a stated **safety contract**, not a UX nicety.

### High-level flow
1. Family reports missing person (booth/WhatsApp) → text (+ optional photo) embedded → stored in `missing_reports` with `vector(1024)` column.
2. Found/disoriented person registered at any booth → same embedding pipeline → pgvector query for top-10 semantically similar missing reports.
3. Neo4j validates top candidates: zone proximity, temporal plausibility, group/city of origin, learned landmark patterns, duplicate detection.
4. Composite confidence score (`vector_score + graph_modifiers`) computed; operator sees top 3 with reasoning labels.
5. Operator **confirms** → family gets SMS with booth location + 4-digit OTP. Operator verifies OTP at handoff.
6. If unresolved: T+24h → zone-wide SMS blast. T+72h → event-wide SMS blast. T+120h → flagged for police escalation.
7. Dashboard shows live case volumes, match rates, unresolved cases, landmark heatmap.

---

## 3. System Architecture

```
INTAKE LAYER (Booth PWA / WhatsApp Bot / Missed-call IVR)
        │
        ▼
   API GATEWAY — FastAPI, rate-limited per booth
        │
   ┌────┼────────────┬─────────────┐
   ▼    ▼            ▼             ▼
Embedding   Media    Core API   Blast Scheduler
Service     Service  (case      (Celery + Redis)
(text+face) (photo)   mgmt)
   │           │         │            │
   └─────┬─────┘         │            │
         ▼                ▼            ▼
  PostgreSQL+pgvector   Neo4j      SMS Gateway
  (missing/found_reports,(graph    (MSG91 / Gupshup)
   zones, booths,        validation,
   registrants,          landmark
   case_events,          patterns,
   groups)               duplicates)
         │
         ▼ (direct PG queries for analytics)
   React Dashboard (MapLibre GL)
```

**Database choices and why:**
| DB | Role | Why not something else |
|---|---|---|
| PostgreSQL + pgvector | Source of truth + vector search | One DB for OLTP + embeddings; HNSW index fast enough at hackathon scale; avoids separate vector DB |
| Neo4j | Graph validation + relationship intelligence | Multi-hop traversal (zone→landmark→pattern) is native; SQL recursive CTEs are painful/slow |
| Redis | Celery broker + rate limiting + short cache | Lightweight, battle-tested |
| SQLite | Offline booth cache **only** | No server needed, works in PWA service worker |

**Explicitly NOT used:** ClickHouse / separate analytics DB. Dashboard queries run directly against Postgres using materialized views (e.g. `zone_case_summary`, refreshed every 5 min).

### Offline resilience (booths will lose network on peak days)
Every booth tablet is a **PWA, offline-first**:
- Local SQLite queues new missing/found reports
- Cached static zone map (no tile server dependency)
- Last-synced match cache (read-only, limited matching)
- Background sync worker pushes queue on reconnect
- Offline-created records get **client-generated UUIDs** to avoid collision on sync; matches attempted offline are flagged `pending_sync` and re-run server-side later.

---

## 4. Data Models (summary — full DDL/Cypher in source spec)

### PostgreSQL (with pgvector + PostGIS)
Key tables: `zones`, `booths`, `groups`, `registrants`, `missing_reports`, `found_reports`, `case_events`, plus materialized view `zone_case_summary`.

- `missing_reports` / `found_reports` both carry `embedding vector(1024)` (multilingual-e5-large output dim), with an **HNSW index** (`vector_cosine_ops`, `m=16, ef_construction=64`).
- `missing_reports` also has a **partial index on `status = 'active'`** — vector search must always pre-filter to active rows, never full-table scan.
- `case_events` is the audit trail: `filed | matched | blast_zone_sent | blast_event_sent | closed | duplicate_flagged | operator_rejected | escalated_to_police`.

**pgvector query pattern** (run when a found person is registered):
```sql
SELECT mr.*, 1 - (mr.embedding <=> $1::vector) AS cosine_similarity
FROM missing_reports mr
WHERE mr.status = 'active'
  AND mr.subject_gender = $2
  AND mr.subject_age BETWEEN $3 AND $4   -- age ± 15 years
ORDER BY mr.embedding <=> $1::vector
LIMIT 10;
```
Pre-filter (gender, age, status) **before** the vector comparison — Postgres 16+ supports this with HNSW, and it matters for performance under load.

### Neo4j graph schema
Nodes: `MissingReport, FoundReport, Person, Zone, Landmark, Booth, Phone, Group, City`.
Key relationships: `DESCRIBES, FILED_AT, REGISTERED_AT, IN_ZONE, ADJACENT_TO, LAST_SEEN_AT, FOUND_NEAR, BELONGS_TO, FROM_CITY, MATCHED_TO` (the last one written only on confirmation).

---

## 5. Matching Pipeline (the core of the system)

```
Found person registered
   → Generate embedding (multilingual-e5-large text + face embed if photo)
   → [parallel] pgvector query (top 10, pre-filtered gender/age/status)
              + Neo4j seeding (async, non-blocking)
   → Photo re-ranking (InsightFace cosine, only if both have photos)
   → Neo4j validation on top 3:
        zone plausibility, temporal window, city/state match,
        landmark pattern match, duplicate detection, language match
   → Composite score = clamp(vector_score + Σ graph modifiers, 0, 1)
   → Booth operator screen: top 3, confidence %, reason labels
   → CONFIRM or REJECT ALL (human decision, always)
```

**Composite confidence modifiers** (`services/scoring.py`):
| Signal | Delta | Label |
|---|---|---|
| same_zone | +0.08 | Same zone ✓ |
| adjacent_zone | +0.04 | Adjacent zone ✓ |
| same_venue | +0.03 | Same venue ✓ |
| different_venue | −0.12 | ⚠ Different venue |
| same_city | +0.06 | Same city of origin ✓ |
| same_state | +0.03 | Same state ✓ |
| temporal_very_recent (<2h) | +0.07 | Time gap under 2 hours ✓ |
| temporal_same_day | +0.04 | Same day ✓ |
| temporal_stale (>72h) | −0.08 | ⚠ Report over 3 days old |
| landmark_pattern_match | +0.07 | Landmark pattern match ✓ |
| language_match | +0.04 | Language spoken matches ✓ |
| possible_duplicate | −0.05 | ⚠ Possible duplicate report |

**Confidence display thresholds:**
| Score | Label | Indicator |
|---|---|---|
| ≥ 0.90 | High Confidence | 🟢 |
| 0.75–0.89 | Probable Match | 🟡 |
| 0.60–0.74 | Possible Match | ⚪ |
| < 0.60 | Not surfaced | — |

Human confirmation required at **every** threshold. No auto-confirm, ever.

---

## 6. Notification & Escalation Logic

- **On confirm:** generate 4-digit OTP → store in Redis (`otp:{case_id}`, TTL 4h) → SMS via MSG91 (Marathi template) with booth name, zone, OTP. Operator verifies OTP at physical handoff.
- **Escalation schedule:**
  | Time | Action |
  |---|---|
  | T+0h | Filed, status = active |
  | T+24h | No match → zone-wide SMS blast (registrants in same zone, last 48h) |
  | T+72h | Still unmatched → event-wide SMS blast (all zones, both venues) |
  | T+120h | Flagged for police escalation in dashboard (status stays active) |
- **Blast architecture:** Celery Beat every 15 min checks Postgres for cases crossing T+24h/T+72h thresholds without corresponding blast events → enqueues blast jobs → dedupes by phone+case_id, idempotency key `{case_id}:{blast_type}` → sends in batches of 500 via MSG91 → logs delivery receipt to `case_events`.

---

## 7. Dashboard (Read-Only for Officials/Police)

No case management happens on the dashboard — that's booth-level only. Queries hit Postgres directly (`zone_case_summary` materialized view + indexed tables).

| Panel | Content |
|---|---|
| 1. Live Map | MapLibre GL, self-hosted Nashik tiles, case dots, zone fill by density, booth markers |
| 2. Case Funnel | Filed → Matched → Confirmed → Notified → Closed, 15-min resolution time series |
| 3. Unresolved Table | Sortable/filterable, red >72h, purple flagged-for-police |
| 4. Landmark Patterns | Sankey diagram from Neo4j learned patterns, refreshed daily (not real-time) |
| 5. Blast Log | Zone/event blast counts, delivery rates, unresolved-after-blast cases |

**Role-based access (JWT, 8h expiry, role in payload):**
| Role | Access |
|---|---|
| `booth_operator` | Booth PWA only |
| `zone_supervisor` | Panels 1–3, own zone only |
| `command_center` | All panels, all zones/venues |
| `police` | All panels + Panel 5 escalation flags + case detail |
| `admin` | Everything + user management |

---

## 8. Tech Stack (Confirmed)

### Backend
| Component | Tech |
|---|---|
| **API framework** | **FastAPI (Python 3.11)** — async, native WebSocket support |
| Task queue | Celery + Redis |
| ORM | SQLAlchemy 2.0 + Alembic (async sessions) |
| Text embedding | `intfloat/multilingual-e5-large` (1024-dim) |
| Face embedding | InsightFace `buffalo_l` |
| Speech-to-text | OpenAI Whisper, self-hosted `small` model |

### Databases
- PostgreSQL 16 + pgvector 0.7+ (AWS RDS `db.r6g.xlarge`)
- Neo4j 5.x Community (EC2 `r6i.xlarge`)
- Redis 7.x (AWS ElastiCache)
- SQLite (in-browser PWA offline queue only)

### Frontend
| Component | Tech |
|---|---|
| **Dashboard** | **React 18 + Vite** |
| **Booth app** | **React PWA**, offline-first via service workers |
| Charts | Recharts |
| Map | MapLibre GL JS (self-hosted tiles) |
| State | Zustand |
| Real-time | WebSockets (native FastAPI) |
| Styling | Tailwind CSS |

### Intake & Notifications
- WhatsApp Bot: Gupshup BSP + FastAPI webhook
- Missed-call IVR: Exotel
- SMS: MSG91 primary, Gupshup fallback
- Voice transcription: Whisper via bot webhook

### Infrastructure
- AWS Mumbai (`ap-south-1` — data residency in India)
- S3 + presigned URLs for photos
- CloudFront CDN (dashboard static assets)
- Prometheus + Grafana monitoring
- GitHub Actions CI/CD
- AWS Secrets Manager

---

## 9. API Conventions (must follow exactly)

```
Base URL:   /api/v1/
Request:    Content-Type: application/json
Response:   { "data": {...}, "error": null, "timestamp": "ISO8601" }
Error:      { "data": null, "error": { "code": "ERR_CODE", "message": "..." } }

Auth header:        Authorization: Bearer <jwt>
Booth-facing routes: X-Booth-ID: <uuid>   (required)
Internal routes:     X-Internal-Key: <key> (not user-facing, /internal/*)
```

### Route ownership map
| Method | Route | Owner | Description |
|---|---|---|---|
| POST | `/intake/missing` | M2 | File missing report |
| POST | `/intake/found` | M2 | Register found person |
| GET | `/match/{found_id}` | M1 | Top 3 matches |
| POST | `/match/confirm` | M1 | Operator confirms |
| POST | `/match/reject` | M1 | Operator rejects all |
| POST | `/internal/validate` | M1 | Neo4j validation (internal) |
| POST | `/registrant` | M2 | Register phone→zone (IVR) |
| GET | `/dashboard/summary` | M3 | Zone case counts |
| GET | `/dashboard/map` | M3 | GeoJSON for map |
| GET | `/dashboard/unresolved` | M3 | Unresolved cases table |
| GET | `/dashboard/patterns` | M3 | Neo4j landmark patterns |
| WS | `/ws/dashboard` | M4 | Real-time push |
| POST | `/auth/login` | M4 | JWT issue |

### Environment variables (exact names, shared across team)
```
DATABASE_URL=postgresql+asyncpg://nandi:password@rds-host:5432/nandi
NEO4J_URI=bolt://neo4j-host:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=changeme
REDIS_URL=redis://elasticache-host:6379/0
MSG91_AUTH_KEY=
MSG91_SENDER_ID=NANDIK
GUPSHUP_API_KEY=
EXOTEL_SID=
EXOTEL_TOKEN=
EXOTEL_VIRTUAL_NUMBER=
AWS_S3_BUCKET=nandi-media
AWS_REGION=ap-south-1
EMBEDDING_MODEL=intfloat/multilingual-e5-large
EMBEDDING_DIM=1024
FACE_MODEL=buffalo_l
JWT_SECRET=
JWT_EXPIRY_HOURS=8
INTERNAL_KEY=
OTP_TTL_SECONDS=14400
```

---

## 10. Non-Negotiables (cannot be broken by anyone)

1. **No auto-notification.** SMS is sent only after explicit operator confirmation. Safety contract.
2. **No plaintext phone numbers in logs.** Always mask: `+91XXXXXX7890`.
3. **Offline booths queue, never drop.** No server reach → write to SQLite, never show an error and discard.
4. **Marathi first.** Every user-facing string needs a Marathi version. English is internal/admin only.
5. **Photos are optional everywhere.** Never block submission on missing photo.
6. **pgvector index is always partial on `status = 'active'`.** Never run a full-table vector scan.

### Other binding conventions
- **UUIDs everywhere** — no integer auto-increment IDs (avoids offline/online sync collisions).
- **Embedding dimension is locked at 1024** (`multilingual-e5-large`). Don't change without updating schema + HNSW index + all embedding calls together. Text inputs are prefixed `"passage: ..."` (storage) or `"query: ..."` (search) per model convention.
- **No language validation anywhere** — the embedding model handles multilingual input natively. The only language-specific logic allowed is SMS templates (Marathi first, Hindi fallback).
- **Git branches:** `main` (protected, 2 approvals) → `dev` (1 approval) → `feat/m1-*` … `feat/m4-*`. Merge order: M1 → M2 → M1+M2 integration test → M3 → M4.

---

## 11. Out of Scope (hackathon — roadmap only)

- Live CCTV facial recognition scanning
- Aadhaar / government ID verification
- Police FIR system integration
- Drone PA system integration
- Full multilingual NLP (bot handles Marathi + Hindi only for hackathon)
- Native iOS/Android app (PWA deemed sufficient)
- Child trafficking detection model
- ClickHouse / separate analytics DB
- Payment or commercial features

---

## 12. Team & Ownership (4 members)

| Member | Owns | Does NOT own |
|---|---|---|
| **M1 — Backend, DB & Search** | Postgres schema/migrations, pgvector tuning, embedding service, matching pipeline, Neo4j schema/queries, `/internal/validate`, composite scoring, match confirm/reject, audit logging, dedup logic | SMS, intake routes, dashboard routes, frontend, WebSocket server, infra |
| **M2 — Notifications Engine** | Intake routes (`/intake/missing`, `/intake/found`), WhatsApp bot webhook, IVR webhook, `/registrant`, SMS on confirm, Celery blast scheduler, OTP gen/storage, offline sync endpoint | Matching logic, Neo4j, dashboard queries, frontend, infra |
| **M3 — UI** | Booth PWA (all forms + match screen + offline UI), Dashboard (all 5 panels + auth screens), all Marathi copy, dashboard API routes (`GET /dashboard/*`) | Matching logic, Neo4j, SMS/blast, WebSocket server, AWS infra, router/auth wiring |
| **M4 — Frontend Integration & Infra** | AWS infra, Docker Compose, CI/CD, React Router + route protection, auth flow (JWT in-memory), Axios client, WebSocket client + Zustand wiring, `/auth/login`, MapLibre tile server, S3 presigned URLs, Prometheus/Grafana, env var management, e2e integration tests | Business logic, UI components, dashboard routes, matching pipeline, SMS/blast |

Each member's deliverables are broken into 4 hackathon phases (0–16h, 16–28h, 28–40h, 40–48h) — see source spec Section 13 for the exhaustive per-phase checklist if needed.

---

## 13. Build Phases (Whole-Team View)

| Phase | Hours | Goal |
|---|---|---|
| 1 — Core Loop | 0–16 | One missing report filed, one found person matched, one SMS sent, end to end |
| 2 — Graph Validation | 16–28 | Match scores have reasoning; operator sees confidence labels |
| 3 — Dashboard + Blast | 28–40 | Police can see live state; blast scheduler fires on schedule |
| 4 — Polish + Demo | 40–48 | Demo-ready: offline mode tested, OTP flow works, full scenario rehearsed |

---

## 14. Naming & Identity Note

**NANDI** — named after the sacred bull who guards the threshold at Shiva's temple gate: patient, watchful, always waiting for the lost to return. *"नंदी. The patient one. The one who waits at the gate until everyone has come home."*

---

## 15. Open Items / Things to Confirm Going Forward

- Source doc references GitHub repos for hackathon data (`SumeetGDoshi/claude-impact-labs-data`) and two contributor handles (`shrutiiiiin`, `ParthJ39`) — worth clarifying team roles/repo access if not already set up.
- Document version in source: v2.0, last updated June 2026, team size 4.
- This file should be treated as the **canonical condensed brief**. The original spec (`Kumbhathon-Cluade-Project.md`) remains the full source of truth for exact Cypher/SQL/Python snippets, key file trees, and the complete phase-by-phase checklists per member.
