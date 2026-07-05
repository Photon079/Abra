# Abra — Complete Setup Guide

End-to-end setup for Abra v2 (Coral live data + Cognee graph memory + Notion + LLM).
Run everything **from the repo root** (`/home/anish/Abra`).

---

## 0. Prerequisites

| Requirement | Notes |
|---|---|
| Python 3.10+ | You're on 3.12. |
| Node.js 18+ | Only needed if you want to rebuild the React frontend; a prebuilt dashboard is already served. |
| [Coral CLI](https://withcoral.com/docs) | `coral` must be on your PATH. Check: `coral --version` |
| Notion integration | https://www.notion.so/my-integrations |
| At least one LLM key | Gemini recommended (Groq / Cerebras / OpenRouter auto-fallback). |
| Cognee Cloud account | https://platform.cognee.ai — for v2 graph memory (optional; app runs without it). |

---

## 1. Install dependencies

```bash
cd /home/anish/Abra

# Use the existing venv (or create one: python3 -m venv venv)
source venv/bin/activate

# Backend deps — includes cognee (heavy: lancedb, litellm; first install is slow)
pip install -r requirements.txt

# Frontend deps — OPTIONAL. The dashboard is served as static files already.
# Only needed if you want to modify/rebuild the React app.
# cd frontend && npm install && cd ..
```

---

## 2. Configure environment

```bash
cp .env.example .env
```

Then fill in `.env`. Sections below explain each block.

### 2a. Notion (storage + tasks + "brain")

```bash
NOTION_TOKEN="secret_xxx"                 # integration secret
NOTION_DIARY_DB_ID="..."                  # diary database (or a plain page id)
NOTION_TASKS_DB_ID="..."                  # tasks database (or a plain page id)
NOTION_BRAIN_PAGE_ID="..."                # parent page whose sub-pages are your profile/goals/patterns
```

- Create the integration, copy its secret into `NOTION_TOKEN`.
- **Share each database/page with the integration** (Notion → page → ••• → Connections → your integration). Without this, the API returns 404s.
- IDs are the 32-char hex in the page/DB URL. Abra auto-detects whether an ID is a database or a plain page and adapts.

### 2b. LLM provider

```bash
LLM_PROVIDER="gemini"                      # "gemini" | "groq" | "cerebras"
GEMINI_API_KEY="..."                       # https://aistudio.google.com/apikey
GROQ_API_KEY="..."                         # https://console.groq.com/keys  (also powers Whisper voice transcription)
CEREBRAS_API_KEY=""                        # optional
# OPENROUTER_API_KEY=""                    # optional extra fallback
```

The cascade tries your configured provider first, then any other provider whose key is present. Set at least one. Groq additionally enables voice-diary transcription (Whisper).

### 2c. Chess.com (no auth)

```bash
CHESSCOM_USERNAME="your_chess_username"
```

### 2d. Strava (OAuth)

```bash
STRAVA_CLIENT_ID="..."                     # https://www.strava.com/settings/api
STRAVA_CLIENT_SECRET="..."
STRAVA_ATHLETE_ID="..."                    # numeric id from your profile URL (needed for athlete_stats table)
# The three below are filled automatically by the OAuth step in §4 — leave blank for now:
STRAVA_ACCESS_TOKEN=""
STRAVA_REFRESH_TOKEN=""
STRAVA_TOKEN_EXPIRES_AT=""

STRAVA_WEEKLY_KM_TARGET=30                  # optional dashboard targets
STRAVA_WEEKLY_MINS_TARGET=180
```

In your Strava API app settings, set **Authorization Callback Domain** to `localhost`.

### 2e. Cognee Cloud (v2 graph memory)

```bash
USE_GRAPH_MEMORY=false                      # keep false until §5 validates the connection
COGNEE_API_KEY=""                           # from https://platform.cognee.ai
COGNEE_CLOUD_URL="https://your-tenant.aws.cognee.ai"
COGNEE_DATASET="abra"                       # optional
COGNEE_TOP_K=10                             # optional
```

> With `USE_GRAPH_MEMORY=false` (or no key), Abra falls back to the v1 Notion memory loader and runs completely fine. Graph memory is additive.

---

## 3. Coral sources

`chesscom` and `strava` are **native Coral sources contributed to Coral by the author** —
on most setups they're already installed. Check first:

```bash
coral source list          # look for chesscom + strava (Origin doesn't matter)
```

If they're already listed, **you don't need to register anything** — skip to the sanity
check. Abra's startup only registers the local `sources/*.yml` as a fallback when Coral
doesn't already have the source.

If a source is missing, add it (env vars supply the input values):

```bash
coral source add --file sources/chesscom.yml
coral source add --file sources/strava.yml
```

Sanity check:

```bash
coral sql "SELECT chess_blitz__last__rating FROM chesscom.stats" --format json
```

`coral_smoke_test.py` runs a couple of real cross-source queries:

```bash
python scripts/coral_smoke_test.py
```

---

## 4. Strava OAuth (one-time)

Opens a browser, authorizes, and writes the tokens back into `.env` automatically:

```bash
python3 -m app.coral.startup --strava-auth
```

After this, tokens auto-refresh on every startup — no manual step again. Verify:

```bash
coral sql "SELECT name, distance, start_date_local FROM strava.activities LIMIT 3" --format json
```

---

## 5. Validate Cognee Cloud (one-time spike — do this before trusting graph memory)

This is PRD Task 1: a hello-world `add → cognify → search` against your tenant. It confirms
the exact Cloud SDK surface for your account before the app depends on it.

```bash
export COGNEE_API_KEY=...                    # (or rely on .env — the spike calls load_dotenv)
export COGNEE_CLOUD_URL=https://your-tenant.aws.cognee.ai
python scripts/cognee_spike.py
```

It ingests two diary facts and asks:
*"What happens to my chess accuracy in weeks where my diary mentions low sleep or exam stress?"*

- **If the answer links low sleep → lower chess accuracy** → graph memory works. Set `USE_GRAPH_MEMORY=true` in `.env`.
- If it errors on connection/signature, note the exact error — only the connect/search kwargs would need a tweak in `app/memory/graph_memory.py`.

---

## 6. Run

```bash
python run.py
```

Open **http://127.0.0.1:8000** — the dashboard loads with live data.

On startup Abra automatically:
1. Refreshes the Strava token,
2. Registers/confirms Coral sources,
3. Verifies Cognee Cloud connectivity (non-blocking) if `USE_GRAPH_MEMORY=true`.

Check wiring:

```bash
curl -s http://127.0.0.1:8000/api/status | python -m json.tool
# look for "graph_memory": {"enabled": true, "connected": true, ...}
```

---

## 7. Backfill the graph (before a demo)

Populate the graph with real history (existing Notion diary + a 30-day telemetry snapshot):

```bash
curl -X POST http://127.0.0.1:8000/memory/backfill
```

Returns `{"diary_entries_found": N, "items_ingested": M, ...}`. Run this once after a fresh
Cognee dataset, before recording the demo.

---

## 8. Demo flow (the judging moment)

1. **v1-style (Coral live fact):** in chat, ask *"How many km did I run this week?"*
2. **v2 graph memory:** ask *"What usually happens to my chess accuracy in weeks where my diary mentions low sleep or exam stress?"* — v1 physically couldn't answer this; v2 answers from linked diary + telemetry nodes.
3. **Insight persistence:** open the morning briefing and show it referencing an insight generated on a previous day.
4. Optional: show the `diary` node set in the Cognee Cloud graph view.

---

## Endpoint reference

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/chat` | Main chat (auto-routes: diary/goal/briefing/reflection/qa/general) |
| GET | `/api/status` | Health + `graph_memory` status |
| GET | `/api/dashboard` | Live telemetry (chess/running/goals + AI insights) |
| GET | `/brief`, `/api/briefing` | Morning briefing (5-min cache) |
| POST | `/diary`, `/api/voice-diary`, `/api/voice-diary/audio` | Diary logging (text / audio) |
| POST | `/goals`, `/qa` | Goal decomposition / Q&A |
| GET | `/reflection` | Behavioral pattern scan |
| GET | `/api/memory` | Graph memory status |
| POST | `/memory/backfill` | One-time graph backfill |

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `graph_memory.enabled = false` unexpectedly | `USE_GRAPH_MEMORY` not truthy, or `COGNEE_API_KEY` empty. Check `/api/status`. |
| `"connected": false` with flag on | Wrong `COGNEE_CLOUD_URL` / key, or tenant not reachable. Re-run `scripts/cognee_spike.py` to see the raw error. |
| Chat/QA answers ignore graph | Graph empty — run `/memory/backfill`, or log a diary entry first (ingest happens on save). |
| Coral queries return `[]` | Source not registered or token expired. `coral source list`; re-run startup; for Strava re-run `--strava-auth`. |
| Notion 404s | Integration not shared with that DB/page. |
| LLM "all providers failed" | No valid key, or all rate-limited. Add/rotate a key; Gemini free tier is the safest default. |
| Diary save feels slow | It shouldn't — graph ingest runs in a background thread. If it blocks, confirm you're on the current `diary.py`. |

---

## What runs where

- **Coral SQL** = live-fact plane (current numbers, cross-source JOINs).
- **Cognee Cloud** = memory plane (relationships, history, trends, persisted insights).
- **Notion** = human-editable storage + tasks.
- Feature flag `USE_GRAPH_MEMORY` cleanly toggles the memory plane on/off.
