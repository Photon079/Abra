# Abra — Personal Life OS

> *Speak a your mind out, Get a structured diary entry in Notion. Ask what you should focus on today. Get an answer from abra that actually knows you.*

I have multiple hobbies and from a very long time tried to connect all my stuff in a single platform.I tried using multiple llms as personal assistants but none of them were good for context aware chats. 

I built Abra to fix this. It's a voice-first personal life OS that listens to whatever you speak, writes structured diary entries to Notion, and answers questions about your own life using live data from every source at once — queried as SQL via [Coral](https://withcoral.com).

This is v1. Chess.com and Strava are connected now. The goal is to eventually pipe in everything — GitHub activity, calendar events, learning progress, health data — so Abra has a complete picture of your life, not just fragments of it.

---

## ⚡ Powered by Coral SQL: Cross-Source Analytics

Abra doesn't just read APIs; it treats your life as a unified database. By leveraging Coral, we can run complex JOINs across completely different platforms in a single query.

For example, **does high cardiovascular fatigue lead to cognitive drops in chess?** 
Instead of writing complex Python scripts to fetch, parse, and correlate data, Abra just runs this:

```sql
SELECT 
    s.start_date_local AS run_date,
    s.distance AS km_ran,
    s.suffer_score AS physical_fatigue,
    c.white__result AS chess_result,
    c.accuracies__white AS chess_accuracy
FROM strava.activities s
JOIN chesscom.games c 
  ON substr(s.start_date_local, 1, 10) = date(datetime(c.end_time, 'unixepoch'))
WHERE s.sport_type = 'Run' 
  AND s.suffer_score > 50 
ORDER BY s.start_date DESC
LIMIT 5;
```

---

## Core Features

| Feature | Description |
|---|---|
| **Voice Diary** | Tap, speak, done. Your words get transcribed, structured, and saved to Notion with date, mood signal, and tomorrow's focus — automatically. |
| **Day Briefing** | Every morning Abra reads your goals, recent diary entries, and live stats, then gives you one human paragraph about what matters today. |
| **Context-Aware Chat** | Ask anything. *"How many km did I run this week?"* *"Am I improving at chess?"* *"What should I work on today?"* — it has the data to actually answer. |
| **Live Telemetry Dashboard** | Deep 7-day and 30-day tracking metrics for both physical endurance (Strava) and cognitive performance (Chess.com) alongside Notion tasks. |
| **Global Insights Engine** | Holistic AI analysis that dynamically correlates Notion pacing with physical/cognitive output to generate unified "Life & Goals" insights. |
| **Resilient AI Cascade** | Fail-fast LLM orchestration (Gemini → Groq) that auto-truncates payloads and seamlessly routes around rate-limits for instant UI responsiveness. |
| **Notion Sync** | Bi-directional. Diary logs, task updates, and goal tracking all write back to your existing Notion workspace. |
| **Strava Automation** | OAuth token management, 30-day distance tracking, and personal best detection — fully hands-off. |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                       Abra Dashboard                        │
│  ┌──────────┐  ┌─────────────────┐  ┌────────────────────┐  │
│  │  Voice   │  │ Live Telemetry  │  │  Morning Briefing  │  │
│  │  Portal  │  │ Dashboard       │  │  + Chat Terminal   │  │
│  └────┬─────┘  └───────┬─────────┘  └────────┬───────────┘  │
└───────┼────────────────┼──────────────────────┼─────────────┘
        │                │                      │
        ▼                ▼                      ▼
┌─────────────────────────────────────────────────────────────┐
│                FastAPI Backend (main.py)                    │
│  Intent Router → Diary / Goals / QA / Briefing / Chat       │
│                AI Models: Gemini → Groq  
└───────┬────────────────┬──────────────────────┬─────────────┘
        │                │                      │
   ┌────▼────┐    ┌──────▼──────┐      ┌───────▼───────┐
   │ Notion  │    │  Coral SQL  │      │ Groq Whisper  │
   │   API   │    │   Engine    │      │ (Voice→Text)  │
   └─────────┘    └──────┬──────┘      └───────────────┘
                         │
              ┌──────────┴──────────┐
              │                     │
         ┌────▼──┐             ┌────▼──┐
         │Chess  │             │Strava │
         │.com   │             │API    │
         └───────┘             └───────┘
```

The key insight: Coral turns Chess.com and Strava into SQL tables Abra can query directly — no ETL, no stitched API calls. Notion is queried separately via its own API and merged at the application layer. Together they give the AI a complete picture of your life across every source. More sources coming.

---

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js v18+ (for frontend)
- [Coral CLI](https://withcoral.com/docs/getting-started/installation)
- A Notion integration ([guide](https://www.notion.so/my-integrations))
- At least one LLM API key (Gemini recommended, others auto-fallback)

### Setup

```bash
# Clone the repository
git clone https://github.com/Photon079/Abra.git
cd Abra

# Install Python dependencies
pip install -r requirements.txt

# Install React frontend dependencies
cd frontend && npm install && cd ..

# Configure environment variables
cp .env.example .env
# Edit .env with your API keys

# Register Coral data sources (auto-registers on every startup after this)
coral source add --file sources/chesscom.yml
coral source add --file sources/strava.yml

# One-time Strava OAuth (opens browser, writes token to .env automatically)
python3 coral_startup.py --strava-auth

# Start everything
python3 main.py
```

Open **http://127.0.0.1:8000** — the dashboard loads with your live data.

> After first setup, `coral_startup.py` auto-registers all sources and refreshes Strava tokens on every `python3 main.py`. No manual steps.

---

## Coral Source Specifications

Two community source specs ship with Abra — also submitted as standalone bounty contributions to the Coral registry:

| Source | Auth | Tables | Notes |
|---|---|---|---|
| **Chess.com** | None (public API) | `stats`, `profile`, `games`, `clubs` | Ratings, match history with PGN and accuracy scores. Works for any username via input variable. |
| **Strava** | OAuth 2.0 + PKCE | `activities`, `athlete`, `athlete_stats` | Full activity history, weekly volume, personal records. Token refresh handled automatically. |

### Lint before you use

```bash
coral source lint sources/chesscom.yml
coral source lint sources/strava.yml
```

### Example queries Abra runs under the hood

```sql
-- Morning briefing: what's my chess trend?
SELECT chess_blitz__last__rating, chess_rapid__last__rating,
       chess_blitz__record__win, chess_blitz__record__loss
FROM chesscom.stats;

-- Recent game accuracy
SELECT white__username, white__result, accuracies__white, time_class
FROM chesscom.games LIMIT 5;

-- This week's running volume
SELECT name, distance, moving_time, start_date_local
FROM strava.activities
WHERE start_date_local >= '2026-05-25'
ORDER BY start_date_local DESC;
```

---

## Personalizing Abra

Abra's personality and context are dynamically loaded from your Notion workspace on every request. Set `NOTION_BRAIN_PAGE_ID` in your `.env` to point to a main "Brain" page. 

Abra automatically scans its sub-pages by title keywords:

| Notion Sub-page Title Keyword | What goes here |
|---|---|
| `profile`, `who`, `story` | Who you are — background, values, what matters most to you |
| `goal`, `career`, `plan` | Active goals, milestones, timelines |
| `pattern`, `interaction` | Habits to watch for, nudges that help you stay on track |

The LLM reads these sub-pages live on every single chat request. The more honest you are in Notion, the more useful Abra becomes.

---

## Tech Stack

- **Backend:** Python, FastAPI
- **Frontend:** React 18, Tailwind CSS, Lucide React
- **AI:** Gemini → Groq → OpenRouter (cascading fallback)
- **Voice Transcription:** Groq Whisper, Web Speech API
- **Data Engine:** Coral SQL
- **Memory & Tasks:** Notion API

## Project Structure

```
Abra/
├── main.py              # FastAPI server and API endpoints
├── coral_startup.py     # Auto source registration + Strava OAuth
├── llm.py               # Multi-provider AI fallback logic
├── coral_query.py       # Coral SQL execution interface
├── notion_writer.py     # Notion API (diary, tasks, context)
├── memory_loader.py     # Context aggregation from Notion or local
├── briefing.py          # Morning briefing generation
├── diary.py             # Voice → structured diary processor
├── goals.py             # Goal decomposition
├── qa.py                # Context-aware Q&A handler
├── intent_router.py     # NLP message routing
├── patterns.py          # Behavioral pattern analysis
├── sources/
│   ├── chesscom.yml     # Chess.com Coral spec (bounty submission)
│   └── strava.yml       # Strava Coral spec (bounty submission)
├── brain_files/         # Your personal context files (not committed)
├── frontend/
│   ├── src/             # React components
│   └── package.json
├── .env.example
└── requirements.txt
```

---

**Built by [Anish](https://github.com/Photon079) for the Pirates of the Coral-bean hackathon.**  
**Powered by [Coral](https://withcoral.com).**
