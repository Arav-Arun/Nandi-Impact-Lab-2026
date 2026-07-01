# 🐂 NANDI - Missing-Persons Reunification

**Simhastha Kumbh Mela 2027 · Nashik–Trimbakeshwar**

NANDI reunites missing people with their families at one of the world's largest
human gatherings (8–10 crore pilgrims). A family reports a missing person in any
language - by voice, Telegram, or at a booth. When someone is found and
registered, NANDI ranks likely matches for a booth operator using **multilingual
semantic search** (pgvector) and **graph validation** of the venue's geography
(Neo4j). The operator confirms; the family is notified with a booth location and
a one-time verification code they present to collect their relative.

> Built as an **operational control tool**, not a demo: the booth console, the
> family intake, and the command dashboard are designed for real use on cheap
> Android phones in bright daylight.

<table>
<tr>
<td width="50%" align="center"><b>Command dashboard</b><br/><img src="assets/img1.png" alt="Command dashboard"/></td>
<td width="50%" align="center"><b>Operator console</b><br/><img src="assets/img4.png" alt="Operator console"/></td>
</tr>
<tr>
<td align="center"><b>Family intake &middot; Marathi</b><br/><img src="assets/img3.png" alt="Family intake in Marathi"/></td>
<td align="center"><b>Zone broadcast</b><br/><img src="assets/img5.png" alt="Zone broadcast"/></td>
</tr>
<tr>
<td align="center"><b>Whole-UI translation &middot; Tamil</b><br/><img src="assets/img2.png" alt="Dashboard translated to Tamil"/></td>
<td></td>
</tr>
</table>

---

## What it does

| Surface | For | What happens |
|---|---|---|
| **Intake** | Families | Report a missing person by **voice in any of 11 Indian languages** (Sarvam STT) or free text. An LLM extracts name/age/gender/clothing/last-seen into the form. An optional photo is auto-described and folded into the search text. |
| **Operator** | Booth staff | A live queue of cases. Register a found person → **AI-ranked candidates** with confidence + plain-language reasons. Confirm → verification code → mark reunited when the family arrives. |
| **Dashboard** | Command centre | Live operational metrics - open workload, escalations, high-risk cases, per-day load, language/channel/age/hotspot breakdowns. |
| **Broadcast** | Escalation | Reach a whole zone at Kumbh scale by posting once to its **Telegram channel** (see below). |

### Highlights

- **Whole UI translates** into every Sarvam-supported language (English, Hindi,
  Marathi, Bengali, Telugu, Tamil, Kannada, Gujarati, Malayalam, Punjabi, Odia) -
  real translations generated via Sarvam, one click in the header.
- **Kumbh-scale broadcast.** Individual opt-in lists can't reach crores. Each zone
  has a public **Telegram channel** pilgrims join by scanning a QR at the booths;
  a broadcast posts once per zone channel and reaches every member instantly.
  Email is kept for registered families/officials.
- **Vulnerable-person priority.** Open cases for children (≤12) and elders (≥70)
  are auto-flagged, pinned to the top of the operator queue, and can be broadcast
  immediately instead of waiting for the normal escalation window - learnt from
  past-Kumbh lapses in responding to the most at-risk.
- **Graceful degradation.** Every AI/notification dependency falls back safely if
  its key is missing, so a report is never dropped.

---

## Architecture

```mermaid
flowchart TD
    Family([Family]) -->|voice / text / photo| Intake[Intake UI]
    Operator([Booth operator]) --> Console[Operator console]
    Intake --> API[FastAPI backend]
    Console --> API
    API -->|STT / extraction / vision| AI[[Sarvam + OpenAI]]
    API --> PG[(Postgres + pgvector<br/>source of truth)]
    API -->|geo validation| Neo[(Neo4j<br/>venue graph)]
    API -->|OTP| Redis[(Redis)]
    Console -->|confirm match| Notify[[Telegram + Email]]
    API -->|zone broadcast| TG[Zone Telegram channels]
```

- **Postgres + pgvector + PostGIS** - source of truth; multilingual text
  embeddings for ANN search.
- **Neo4j** - venue geography (zones, booths, landmarks, adjacency) for match
  validation and broadcast fan-out.
- **Redis** - verification-code (OTP) store.

---

## Quick start (local dev)

Prerequisites: **Docker Desktop**, **Python 3.11+**, **Node 18+**.

```bash
# 1. Datastores (Postgres + Neo4j + Redis)
cd server
docker compose up -d          # wait until all three are healthy

# 2. Backend
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env          # add keys (all optional - see below)
.venv/bin/python -m alembic upgrade head
.venv/bin/python -m uvicorn api.main:app --reload    # → http://127.0.0.1:8000/docs

# 3. Frontend (new terminal)
cd frontend
npm install
npm run dev                   # → http://localhost:5173
```

> **Note:** if the project path contains spaces, the venv console scripts
> (`alembic`, `uvicorn`) can't be executed directly - run them as
> `python -m alembic …` / `python -m uvicorn …` as shown above.

The database starts **empty** (no fake data). To load the Nashik zone/booth
topology the app needs:

```bash
cd server && .venv/bin/python -m scripts.seed_postgres && .venv/bin/python -m scripts.seed_neo4j
```

---

## Production deploy

One command brings up the full stack (nginx SPA + backend + datastores):

```bash
cp server/.env.example server/.env       # real secrets
docker compose -f docker-compose.prod.yml up -d --build
```

Migrations run automatically on backend start and the database starts clean.
Put a TLS-terminating reverse proxy (Caddy / Traefik / cloud LB) in front for HTTPS.

---

## API keys

All optional - each dependency degrades to a safe fallback when its key is blank.
Keys live in `server/.env`.

| Capability | Env var | Fallback when unset |
|---|---|---|
| Voice → text + UI translation | `SARVAM_API_KEY` | mock transcript; UI stays English |
| Intake extraction + photo description | `OPENAI_API_KEY` (primary), `ANTHROPIC_API_KEY` (fallback) | regex heuristic |
| Zone broadcast + match notifications | `TELEGRAM_BOT_TOKEN` | on-screen code only |
| Email to registered families | `RESEND_API_KEY` / SMTP | logged no-op |
| Real embeddings (vs deterministic stub) | `EMBEDDING_FALLBACK=0` | hash-seeded stub |

Check what's live: `curl -s http://127.0.0.1:8000/api/v1/channels`

---

## UI translations

The interface ships translated into every Sarvam language
(`frontend/src/lib/locales/*.json`). English is the source of truth in
`frontend/src/lib/i18n.tsx`. After editing English copy, regenerate:

```bash
cd server && python -m scripts.gen_i18n          # fills only missing keys
python -m scripts.gen_i18n --force               # retranslate everything
```

---

## Project structure

```
Nandi/
├── frontend/                     # React + Vite + Tailwind (operational UI)
│   └── src/
│       ├── pages/                # Overview · Intake · Operator · Blast
│       ├── lib/                  # api client, i18n + locales/, hooks
│       └── components/           # shared UI primitives + icons
├── server/                       # FastAPI backend
│   ├── api/routes/               # blast, dashboard, intake, match, media, webhooks, ws
│   ├── core/                     # config, database, redis, security, logging
│   ├── db/                       # SQLAlchemy models
│   ├── services/                 # matcher, embedding, extraction, vision, blast, notify …
│   ├── migrations/               # Alembic
│   ├── scripts/                  # seed_* , gen_i18n (Sarvam translations), blast_worker
│   ├── Dockerfile                # production backend image
│   └── docker-compose.yml        # dev datastores
└── docker-compose.prod.yml       # full production stack
```

---

## Tech stack

**Frontend** React 18 · Vite · TypeScript · Tailwind · Recharts -
**Backend** FastAPI · SQLAlchemy (async) · Alembic -
**Data** Postgres + pgvector + PostGIS · Neo4j · Redis -
**AI** Sarvam (STT + translation) · OpenAI (extraction + vision) ·
sentence-transformers (multilingual-e5-large embeddings).
