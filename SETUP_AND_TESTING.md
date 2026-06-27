# NANDI — Run Locally · API Keys · How to Test

This is the operator's guide to running the whole NANDI stack on your laptop, adding the
(free) API keys that light up each notification channel, and testing every part of the
system end to end.

> **The golden design rule:** every channel and AI feature **degrades to a safe no-op
> when its key is blank** — so the app runs fully *without any keys*. You only add keys
> to make messages actually leave your machine. Nothing breaks if you add none.

---

## 0. What's running right now

| Piece | URL | What it is |
|---|---|---|
| **Backend API** (FastAPI) | http://127.0.0.1:8000 · docs at `/docs` | match + intake + blast + dashboard |
| **Frontend** (React/Vite) | http://127.0.0.1:5173 | Overview · Report · Operator · **Blast** |
| **Postgres + pgvector** | localhost:**5433** (Docker) | source of truth + vector search |
| **Neo4j** | bolt://localhost:7687 · browser :7474 (Docker) | graph validation + zone adjacency |
| **Redis** | localhost:6379 (Docker) | OTP store |

The DB is already migrated + seeded (5 zones, 5 booths) and the embedding model
(`multilingual-e5-large`, real semantic matching) is cached. **68/68 tests pass.**

---

## 1. Running it on localhost (from a cold machine)

```bash
# ── A. Datastores (Docker) ────────────────────────────────────────────────
cd server
make db-up                 # Postgres(5433) + Neo4j(7687) + Redis(6379)
docker compose ps          # wait until all 3 are "healthy"

# ── B. Backend (FastAPI) ──────────────────────────────────────────────────
make venv install          # one-time: build .venv + install deps
cp .env.example .env        # if you don't already have server/.env
make migrate seed          # create schema + HNSW indexes, load Nashik topology
make run                    # → http://127.0.0.1:8000/docs   (uvicorn --reload)

# ── C. Frontend (React) ───────────────────────────────────────────────────
cd ../frontend
npm install                 # one-time
npm run dev                 # → http://127.0.0.1:5173   (proxies /api → :8000)
```

Open **http://127.0.0.1:5173**. The frontend's Vite proxy forwards `/api/*` and
`/health` to the backend on :8000, so you only ever browse to 5173.

> **Embeddings:** `server/.env` ships with `EMBEDDING_FALLBACK=0` = the **real**
> multilingual model (semantic matching). The model is already downloaded. If you ever
> move to a machine without it and want zero downloads, set `EMBEDDING_FALLBACK=1` for a
> deterministic stub (matching still wires up; it just isn't semantic).

---

## 2. API keys — what to create and where to paste it

**Every key below is FREE.** All go into **`server/.env`**. After editing, **restart the
backend** (`make run`) and check `GET /api/v1/channels` — each channel flips to `true`
once its key(s) are present.

| Channel / feature | env var(s) in `server/.env` | Free? | Where to get it |
|---|---|---|---|
| **Telegram** (inbound + outbound + blast) | `TELEGRAM_BOT_TOKEN` | ✅ totally free | @BotFather → `/newbot` |
| **WhatsApp** (Twilio sandbox) | `TWILIO_ACCOUNT_SID` + `TWILIO_AUTH_TOKEN` (+ default `TWILIO_WHATSAPP_FROM`) | ✅ free sandbox | console.twilio.com |
| **SMS** (Twilio trial) | `TWILIO_SMS_FROM` (+ the two Twilio creds above) | ✅ trial credit | console.twilio.com |
| **SMS** (MSG91, India) | `MSG91_AUTH_KEY` (+ `MSG91_SENDER_ID`) | ✅ trial | msg91.com — *alt to Twilio SMS* |
| **Email** | `RESEND_API_KEY` | ✅ 3k/mo | resend.com (works with `onboarding@resend.dev`, no domain) |
| Email (alt) | `SENDGRID_API_KEY` *or* `SMTP_HOST`/`SMTP_USER`/`SMTP_PASSWORD` | ✅ | sendgrid.com / Gmail app password |
| **Voice → text** on bots (optional) | `SARVAM_API_KEY` | ✅ trial credits | dashboard.sarvam.ai |
| **Claude extraction** (optional, paid) | `ANTHROPIC_API_KEY` | 💳 paid | console.anthropic.com |

> **Minimum to light up all four blast channels for free:** Telegram token + Twilio
> sandbox (covers WhatsApp **and** SMS) + Resend. That's three sign-ups.

### 2.1 Telegram (easiest — 60 seconds, no billing)
1. In Telegram, message **@BotFather** → send `/newbot`.
2. Give it a name + a username ending in `bot`.
3. BotFather replies with a token like `8123456789:AAH...`. Paste it:
   ```ini
   TELEGRAM_BOT_TOKEN=8123456789:AAH...
   ```
4. Restart backend. To receive inbound messages you need a public URL (see §4.2);
   **outbound + blasts work immediately from localhost.**

### 2.2 Twilio — WhatsApp sandbox + SMS (one account, two channels)
1. Sign up at **console.twilio.com** (free trial).
2. On the dashboard copy **Account SID** and **Auth Token**:
   ```ini
   TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxx
   TWILIO_AUTH_TOKEN=your_auth_token
   ```
3. **WhatsApp:** Messaging → *Try it out* → **Send a WhatsApp message** → join the
   sandbox by texting the `join <code>` phrase to the sandbox number from your phone.
   Leave `TWILIO_WHATSAPP_FROM=whatsapp:+14155238886` (the sandbox default).
4. **SMS (optional):** grab a trial number (Phone Numbers → buy a free trial number) and
   set `TWILIO_SMS_FROM=+1xxxxxxxxxx`. Trial SMS only sends to **verified** numbers.

### 2.3 Resend — email (simplest email option)
1. Sign up at **resend.com** → API Keys → **Create API Key**.
2. ```ini
   RESEND_API_KEY=re_xxxxxxxx
   EMAIL_FROM=NANDI <onboarding@resend.dev>
   ```
   `onboarding@resend.dev` works with **no domain verification** — perfect for a demo.

### 2.4 Sarvam (optional — Indian-language voice intake)
`dashboard.sarvam.ai` → API key → `SARVAM_API_KEY=...`. Without it, the voice
"Report" tab still works using a mock transcription.

### 2.5 Anthropic / Claude (optional — better field extraction)
`console.anthropic.com` → API Keys → `ANTHROPIC_API_KEY=sk-ant-...`. This is the only
**paid** key. Without it, intake extracts fields with a heuristic parser (still works).

### 2.6 After adding keys
```bash
# restart so .env reloads
cd server && make run
# confirm which channels went live
curl -s http://127.0.0.1:8000/api/v1/channels
# → {"sms":true,"whatsapp":true,"telegram":true,"email":true}   (the ones you keyed)
```
In the UI, the **Blast** tab's channel chips turn saffron for each live channel.

---

## 3. How to test — the UI walkthrough (no keys needed)

Open **http://127.0.0.1:5173**. The UI is English by default; the language switcher in
the top-right toggles the whole interface to **Marathi** or **Hindi**.

1. **Overview** — live dashboard. Headline counts, then an **Operational metrics** panel
   built around the actual problem statement: cross-center matches, duplicate reports
   detected, cases without a name, cases without a phone, needs-escalation, and high-risk
   unresolved. Then the per-day curve, age/language/outcome breakdowns, channels, and
   hotspots. Auto-refreshes every 8s; every number comes from the live API.

2. **Report** — file a missing report the way a family would:
   - Type a free-text description in any language (or record voice, which transcribes).
   - Watch it auto-extract name/age/gender/landmark, then submit. It appears live in the
     Operator feed.

3. **Operator** — the booth console (the core loop):
   - Click **"Register a found person"**, enter e.g. *"old woman in a green saree with
     silver anklets, found near the river steps"*, age 70, then **Register and find matches**.
   - You'll get **AI-ranked candidates** with a confidence band (High / Probable /
     Possible), the vector score, and plain-language reasons. Matching is semantic, so
     *"green saree, silver anklets"* matches a report worded differently.
   - Click **Confirm match** so the family's OTP/SMS is dispatched (a no-op log line
     until you add an SMS key) and the case is marked reunited. Or **reject all**.
   - On any **found** report you'll also see **"Blast this person's zone"**, which alerts
     everyone opted-in to that zone (plus adjacent zones) to come identify them.

4. **Blast** — the escalation engine, surfaced as a manual control:
   - Channel chips show which channels are live (saffron) vs. no-key (grey).
   - Pick a **zone**, write a message, **Blast**. It fans out to every subscriber and
     IVR registrant in that zone **and its graph-adjacent zones**, across all channels.
     The result shows `targeted` recipients, zones reached, and `sent/targeted` per
     channel. Blasting **Ramkund** reaches **3 zones** (Ramkund, Tapovan, Panchavati) via
     Neo4j adjacency.
   - **Subscribers** panel: add an SMS/WhatsApp/Telegram/email recipient to a zone, or
     watch the list (Telegram/WhatsApp users auto-enroll when they message the bot).

---

## 4. How to test — APIs and channels

### 4.1 Full match pipeline end-to-end (curl, no keys)
This is the core flow — file → register → match → confirm:
```bash
B=http://127.0.0.1:8000/api/v1
BOOTH=$(curl -s $B/booths | python3 -c "import sys,json;print(json.load(sys.stdin)['data'][0]['id'])")

# 1) file a missing report
curl -s -X POST $B/intake/missing -H 'Content-Type: application/json' -d '{
  "physical_description":"elderly woman, green nine-yard saree, silver anklets, wooden cane, near Ramkund",
  "subject_name":"Lakshmibai","subject_age":68,"subject_gender":"female",
  "language_spoken":"Marathi","last_seen_landmark":"Ramkund","filed_by_phone":"+919812300011"}'

# 2) register a found person (worded differently, same person)
FOUND=$(curl -s -X POST $B/intake/found -H 'Content-Type: application/json' -d "{
  \"physical_description\":\"old woman in a green traditional saree with silver anklets and a walking stick, found confused by the river steps\",
  \"approximate_age\":70,\"gender\":\"female\",\"language_spoken\":\"Marathi\",\"registered_at_booth\":\"$BOOTH\"}")
FOUND_ID=$(echo "$FOUND" | python3 -c "import sys,json;print(json.load(sys.stdin)['data']['found_id'])")

# 3) ranked candidates (expect a high-confidence match ~0.94)
curl -s $B/match/$FOUND_ID | python3 -m json.tool

# 4) confirm the top candidate (requires X-Booth-ID; fires the OTP/SMS bridge)
TOP=$(curl -s $B/match/$FOUND_ID | python3 -c "import sys,json;c=json.load(sys.stdin)['data']['candidates'];print(c[0]['missing_id'])")
curl -s -X POST $B/match/confirm -H 'Content-Type: application/json' -H "X-Booth-ID: $BOOTH" \
  -d "{\"found_id\":\"$FOUND_ID\",\"missing_id\":\"$TOP\",\"operator_id\":\"tester\"}" | python3 -m json.tool
```

### 4.2 Blast + subscribers (curl)
```bash
B=http://127.0.0.1:8000/api/v1
# which channels are live
curl -s $B/channels
# list zones with reachable-recipient counts
curl -s $B/zones | python3 -m json.tool
# add a subscriber to a zone
ZONE=$(curl -s $B/zones | python3 -c "import sys,json;print(json.load(sys.stdin)['data'][0]['id'])")
curl -s -X POST $B/subscribers -H 'Content-Type: application/json' \
  -d "{\"channel\":\"telegram\",\"address\":\"123456\",\"zone_id\":\"$ZONE\",\"name\":\"Test\"}"
# blast that zone (+ adjacent)
curl -s -X POST $B/blast/zone -H 'Content-Type: application/json' \
  -d "{\"zone_id\":\"$ZONE\",\"message\":\"Test alert\",\"subject\":\"NANDI\"}" | python3 -m json.tool
```
With no keys, `sent` is 0 but `targeted` and the zone-expansion are real, and a
`blast_zone_sent` audit event is written.

### 4.3 Inbound Telegram / WhatsApp (needs a public URL)
Outbound and blasts work from localhost, but **inbound webhooks need the internet to
reach you.** Expose port 8000 with a tunnel:
```bash
# e.g. cloudflared (free) or ngrok
cloudflared tunnel --url http://localhost:8000      # gives https://<random>.trycloudflare.com
```
- **Telegram:** `curl -X POST "http://127.0.0.1:8000/api/v1/telegram/set-webhook?url=https://<your-tunnel>"`
  then message your bot — it auto-files a report and enrolls you as a zone subscriber.
- **WhatsApp:** in the Twilio WhatsApp sandbox settings, set *"When a message comes in"*
  to `https://<your-tunnel>/api/v1/whatsapp/webhook`, then text the sandbox number.

### 4.4 Escalation worker (T+24h re-blast, T+72h police)
```bash
cd server && source .venv/bin/activate
python -m scripts.blast_worker            # one pass
python -m scripts.blast_worker --loop     # daemon (re-checks on a cadence)
```
It scans open reports past `BLAST_ESCALATE_HOURS_1` (24h) → re-blasts the zone, and past
`BLAST_ESCALATE_HOURS_2` (72h) → escalates to police, idempotently (won't double-send).

### 4.5 Automated test suite
```bash
cd server && make test     # 68 tests, runs against the live datastores
```

---

## 5. Troubleshooting

| Symptom | Fix |
|---|---|
| `GET /channels` all `false` after adding keys | You didn't restart the backend — `.env` is read once at boot. `make run` again. |
| Frontend loads but data is empty / errors | Backend not up on :8000, or datastores down. `docker compose ps`, then `make run`. |
| `connection refused` to Postgres | Host port is **5433** (not 5432). Check `DATABASE_URL` in `server/.env`. |
| Matches come back empty | Found description too generic, or `MATCH_MIN_CONFIDENCE` (0.60) floor. Use a distinctive description. |
| Telegram/WhatsApp inbound silent | Needs a public tunnel + webhook set (§4.3). Outbound still works without it. |
| Blast `sent: 0` | Expected with no channel keys — it's a logged no-op. Add a key (§2). |
