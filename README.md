# 🔮 Abra — Voice-First Personal Life OS

> Speak your thoughts. Abra structures them, writes to Notion, and tracks your life across Chess.com, Strava, and more — all queryable via SQL.

**Abra** is a voice-first AI life dashboard that turns scattered brain dumps into structured diary entries, tracks your goals across multiple platforms, and gives you a morning briefing that actually knows your life.

Built on [Coral](https://withcoral.com) for cross-source SQL queries over your personal data.

---

## ✨ What It Does

| Feature | How It Works |
|---------|-------------|
| 🎙️ **Voice Diary** | Tap the orb, speak naturally → AI structures it → diary entry appears in Notion |
| 📊 **Live Dashboard** | Real-time Chess.com ratings, Strava running stats, Notion goal progress |
| 🧠 **Morning Briefing** | AI reads your goals, past entries, and activity data to brief you each morning |
| 💬 **Context-Aware Chat** | Ask "analyze my last chess game" or "how's my running this week" — it queries live data |
| 📝 **Notion Write-Back** | Create tasks, update statuses, write diary entries — all from chat or voice |
| 🏃 **Auto Strava Sync** | OAuth token auto-refresh, weekly distance/time tracking, PB detection |

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Abra Life OS Dashboard                    │
│  ┌──────────┐  ┌─────────────────┐  ┌────────────────────┐ │
│  │  Voice    │  │  Live Telemetry │  │  Morning Briefing  │ │
│  │  Portal   │  │  Dashboard      │  │  + Chat Terminal   │ │
│  └────┬─────┘  └───────┬─────────┘  └────────┬───────────┘ │
└───────┼────────────────┼──────────────────────┼─────────────┘
        │                │                      │
        ▼                ▼                      ▼
┌─────────────────────────────────────────────────────────────┐
│                FastAPI Backend (main.py)                      │
│  Intent Router → Diary / Goals / QA / Briefing / Chat        │
│  LLM Cascade: Gemini → Groq → Cerebras (auto-fallback)      │
└───────┬────────────────┬──────────────────────┬─────────────┘
        │                │                      │
   ┌────▼────┐    ┌──────▼──────┐      ┌───────▼───────┐
   │ Notion  │    │  Coral SQL  │      │  Groq Whisper │
   │  API    │    │   Engine    │      │  (voice→text) │
   └─────────┘    └──────┬──────┘      └───────────────┘
                         │
              ┌──────────┼──────────┐
              │          │          │
         ┌────▼──┐  ┌───▼────┐ ┌───▼────────┐
         │Chess  │  │Strava  │ │Google      │
         │.com   │  │API     │ │Calendar    │
         └───────┘  └────────┘ └────────────┘
```

## 🚀 Quick Start (5 minutes)

### Prerequisites
- Python 3.10+
- [Coral CLI](https://withcoral.com/docs/getting-started/installation)
- A Notion integration ([create one here](https://www.notion.so/my-integrations))
- At least one LLM API key (Gemini recommended — [free tier](https://aistudio.google.com/apikey))

### Setup

```bash
# Clone the repo
git clone https://github.com/Photon079/Abra.git
cd Abra

# Run interactive setup (asks for your API keys, configures everything)
python3 setup.py

# Start the server
python3 main.py
```

Open **http://127.0.0.1:8000** — you're live.

### Manual Setup (if you prefer)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Copy and fill in your config
cp .env.example .env
# Edit .env with your API keys

# 3. Register Coral sources
coral source add --file sources/chesscom.yml
coral source add --file sources/strava.yml

# 4. Connect Strava OAuth (one-time)
python3 coral_startup.py --strava-auth

# 5. Personalize your brain context
# Edit files in brain_files/ with your profile, goals, and patterns

# 6. Launch
python3 main.py
```

## 📁 Coral Source Specs

Abra ships with community source specs for Coral:

| Source | Auth | Tables | Description |
|--------|------|--------|-------------|
| **Chess.com** | None (public API) | `stats`, `profile`, `games`, `clubs` | Player ratings, game history with PGN, accuracy scores |
| **Strava** | OAuth 2.0 | `activities`, `athlete`, `athlete_stats` | Running/cycling data, weekly volume, personal bests |

### Validate specs
```bash
coral source lint sources/chesscom.yml
coral source lint sources/strava.yml
```

### Example Coral SQL queries
```sql
-- Your chess ratings across all formats
SELECT chess_blitz__last__rating, chess_rapid__last__rating
FROM chesscom.stats

-- Recent games with accuracy
SELECT white__username, white__result, accuracies__white, time_class
FROM chesscom.games LIMIT 5

-- This week's running volume
SELECT name, distance, moving_time, start_date_local
FROM strava.activities LIMIT 10
```

## 🧠 Brain Files

Abra's context comes from markdown files in `brain_files/`:

| File | Purpose |
|------|---------|
| `master_profile.md` | Who you are — background, personality, what matters to you |
| `career_plan.md` | Current goals and milestones Abra tracks |
| `patterns_for_ai_interaction.md` | Behavioral patterns you want Abra to watch for |

The more context you give Abra, the better it knows you. Think of these as your AI's memory.

## 🔧 Tech Stack

- **Backend**: FastAPI + Python
- **Frontend**: Vanilla HTML/CSS/JS (cyberpunk HUD aesthetic)
- **LLM**: Gemini / Groq / Cerebras (cascading fallback)
- **Voice**: Groq Whisper (audio → text) + browser MediaRecorder
- **Data**: Coral SQL engine for cross-source queries
- **Storage**: Notion API (diary + tasks) with local file fallback

## 📂 Project Structure

```
Abra/
├── main.py              # FastAPI server + all API routes
├── setup.py             # Interactive first-time setup
├── coral_startup.py     # Auto-registers sources + Strava OAuth refresh
├── llm.py               # LLM provider cascade (Gemini → Groq → Cerebras)
├── coral_query.py       # Coral SQL query executor
├── notion_writer.py     # Notion API read/write (diary, tasks, brain files)
├── memory_loader.py     # Loads brain context from local files or Notion
├── briefing.py          # Morning briefing generator
├── diary.py             # Diary entry processor
├── goals.py             # Goal decomposition engine
├── qa.py                # Memory-aware Q&A handler
├── intent_router.py     # Routes chat messages to correct handler
├── patterns.py          # Self-sabotage pattern scanner
├── sources/
│   ├── chesscom.yml     # Chess.com Coral source spec (DSL v3)
│   └── strava.yml       # Strava Coral source spec (DSL v3, OAuth)
├── brain_files/         # Your personal context files
├── frontend/
│   ├── index.html       # Dashboard UI
│   └── chat.html        # Full chat terminal
├── .env.example         # Configuration template
└── requirements.txt     # Python dependencies
```

## 🏆 Built for Coral Hackathon

This project was built for the [Coral Hackathon](https://withcoral.com) — demonstrating how Coral's SQL interface can power a personal life operating system that joins data across:
- **Notion** (tasks, diary, brain context)
- **Chess.com** (ratings, game analysis)
- **Strava** (running telemetry, fitness tracking)

### Hackathon Submissions
- **Personal Track**: Voice-first Life OS with cross-source SQL joins
- **Community Source Specs**: Chess.com (no auth) + Strava (OAuth)

---

**Made by [Anish](https://github.com/Photon079)** · Powered by [Coral](https://withcoral.com)
