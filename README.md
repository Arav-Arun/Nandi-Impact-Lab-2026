# 🐂 NANDI — Missing Persons Reunification System

**Kumbh Mela 2027 · Nashik–Trimbakeshwar**

NANDI reunites missing persons with their families at one of the world's largest gatherings (8–10 crore pilgrims). Families report missing people through booths, WhatsApp, Telegram, or voice. When a found person is registered at any booth, the system uses **multilingual semantic search** (pgvector) and **graph-based validation** (Neo4j) to surface ranked candidates to a booth operator — who makes the final call. On confirmation, the family is notified via SMS/WhatsApp with the booth location and a verification OTP.

---

## Prerequisites

| Tool | Version | Check |
|---|---|---|
| **Docker Desktop** | Any recent version | `docker --version` |
| **Python** | 3.11+ | `python3 --version` |
| **Node.js** | 18+ | `node --version` |
| **npm** | 9+ | `npm --version` |
| **Git** | Any | `git --version` |

> **Docker Desktop must be running** before you start. All three databases (Postgres, Neo4j, Redis) run as containers.

---

## Quick Start (from scratch)

```bash
# 1. Clone the repository
git clone https://github.com/Arav-Arun/Nandi-Impact-Lab-2026.git
cd Nandi-Impact-Lab-2026

# 2. Start the databases (Docker)
cd server
docker compose up -d
docker compose ps              # wait until all 3 show "healthy"

# 3. Set up the backend
make venv install              # create .venv + install all Python deps
cp .env.example .env           # create your env file (edit secrets if needed)
make migrate seed              # create DB schema + seed Nashik topology

# 4. Start the backend API
make run                       # → http://127.0.0.1:8000/docs
# (leave this terminal running)

# 5. In a NEW terminal — start the frontend
cd frontend
npm install                    # one-time: install JS deps
npm run dev                    # → http://localhost:5173
```

**Open http://localhost:5173** — the full application is running.

---

## If you received a `.env` file

If someone shared their `.env` with API keys already filled in:

```bash
git clone https://github.com/Arav-Arun/Nandi-Impact-Lab-2026.git
cd Nandi-Impact-Lab-2026/server

# Copy the shared .env into server/
cp /path/to/shared/.env .env

# Start databases + backend
docker compose up -d
make venv install
make migrate seed
make run

# In a new terminal — frontend
cd frontend
npm install
npm run dev
```

---

## What's running

| Service | URL | Purpose |
|---|---|---|
| **Frontend** (React/Vite) | http://localhost:5173 | Dashboard, Report, Operator, Blast |
| **Backend API** (FastAPI) | http://127.0.0.1:8000/docs | REST API + Swagger docs |
| **PostgreSQL + pgvector** | localhost:5433 | Source of truth + vector search |
| **Neo4j** | bolt://localhost:7687 (browser: :7474) | Graph validation + zone adjacency |
| **Redis** | localhost:6379 | OTP store |

---

## API Keys (all optional, all free)

Every channel **degrades to a safe no-op when its key is blank** — the app runs fully without any keys. You only add keys to make messages actually leave your machine.

All keys go into `server/.env`. After editing, **restart the backend** (`make run`).

| Channel | Env vars | Free? | Get it at |
|---|---|---|---|
| **Telegram** | `TELEGRAM_BOT_TOKEN` | ✅ | @BotFather → `/newbot` |
| **WhatsApp** (Twilio sandbox) | `TWILIO_ACCOUNT_SID` + `TWILIO_AUTH_TOKEN` | ✅ | console.twilio.com |
| **SMS** (Twilio trial) | `TWILIO_SMS_FROM` + above creds | ✅ | console.twilio.com |
| **Email** (Resend) | `RESEND_API_KEY` | ✅ 3k/mo | resend.com |
| **Voice → text** (Sarvam) | `SARVAM_API_KEY` | ✅ trial | dashboard.sarvam.ai |
| **Claude extraction** | `ANTHROPIC_API_KEY` | 💳 paid | console.anthropic.com |

Check which channels are live:
```bash
curl -s http://127.0.0.1:8000/api/v1/channels
# → {"data":{"sms":false,"whatsapp":true,"telegram":true,"email":true}}
```

---

## UI Walkthrough

1. **Overview** — Live dashboard with headline counts, operational metrics, per-day trends, age/language/channel breakdowns, and hotspot locations. Auto-refreshes every 8 seconds.

2. **Report** — File a missing-person report via voice (any Indian language) or text. Auto-extracts name, age, gender, landmarks using Claude AI. Supports Marathi, Hindi, Telugu, and more.

3. **Operator** — The booth console:
   - Register a found person → get AI-ranked match candidates with confidence scores (High / Probable / Possible) and plain-language reasons.
   - **Confirm match** → family gets SMS with booth location + OTP.
   - **Reject all** → case stays open for escalation.
   - **Blast this person's zone** → alerts all subscribers in that zone + adjacent zones.

4. **Blast** — Manual escalation engine. Pick a zone, write a message, blast across all live channels (Telegram, WhatsApp, SMS, Email). Shows targeted vs. sent counts per channel.

---

## Project Structure

```
Nandi-Impact-Lab-2026/
├── frontend/              # React + Vite + Tailwind
│   ├── src/
│   │   ├── pages/         # Overview, Intake, Operator, Blast
│   │   ├── lib/           # API client, i18n, hooks
│   │   └── design/        # Icons, brand assets
│   └── package.json
├── server/                # FastAPI backend
│   ├── api/               # FastAPI app + route modules
│   │   └── routes/        # blast, dashboard, intake, match, media, webhooks, ws
│   ├── core/              # config, database, redis, security, logging
│   ├── db/                # SQLAlchemy models
│   ├── services/          # Business logic (matching, embedding, notify, blast, etc.)
│   ├── graph/             # Neo4j Cypher schemas + queries
│   ├── migrations/        # Alembic migrations
│   ├── scripts/           # Seed data, blast worker
│   ├── tests/             # Pytest suite
│   ├── docker-compose.yml # Postgres + Neo4j + Redis
│   ├── Makefile           # Dev shortcuts
│   ├── requirements.txt   # Python deps
│   └── .env.example       # Template for env vars
├── dataset/               # Source CSV data (zones, CCTV, police stations)
└── backend_legacy/        # Previous prototype (reference only)
```

---

## Makefile Commands (inside `server/`)

| Command | What it does |
|---|---|
| `make venv` | Create `.venv` virtualenv |
| `make install` | Install Python dependencies into `.venv` |
| `make db-up` | `docker compose up -d` (Postgres + Neo4j + Redis) |
| `make db-down` | `docker compose down` (keeps data volumes) |
| `make migrate` | `alembic upgrade head` (create/update DB schema) |
| `make seed` | Seed Postgres + Neo4j with Nashik topology |
| `make run` | Start the API server (uvicorn --reload) |
| `make test` | Run the test suite |

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `connection refused` to Postgres | Docker not running, or containers not started. Run `docker compose up -d` inside `server/`. |
| Frontend loads but shows no data | Backend not running on :8000. Run `make run` inside `server/`. |
| `GET /channels` all `false` | Restart the backend after editing `.env` — env vars are read once at boot. |
| Matches come back empty | Description too generic, or no active missing reports. File a missing report first. |
| `ModuleNotFoundError` | Run `make install` inside `server/` to reinstall dependencies. |
| Port 5433 conflict | Another Postgres is running. Stop it or change the port in `docker-compose.yml` + `.env`. |

---

## Running Tests

```bash
cd server
make test      # runs pytest against live datastores
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | React 18 + Vite + Tailwind CSS + Recharts |
| **Backend** | FastAPI (Python 3.11) + SQLAlchemy 2.0 |
| **Vector Search** | PostgreSQL 16 + pgvector (HNSW, 1024-dim embeddings) |
| **Graph DB** | Neo4j 5.x (zone adjacency, landmark patterns, validation) |
| **Cache/OTP** | Redis 7.x |
| **Text Embeddings** | `intfloat/multilingual-e5-large` (1024-dim, 100+ languages) |
| **AI Extraction** | Claude (Anthropic) for structured field extraction |
| **Voice** | Sarvam AI (Indian-language speech-to-text) |
| **Notifications** | Twilio (WhatsApp/SMS), Telegram Bot API, Resend (email) |
