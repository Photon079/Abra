# Abra — Personal Life OS

Abra is a voice-first AI life dashboard designed to structure unstructured inputs, interact with Notion APIs, and monitor cross-platform telemetry (Chess.com, Strava) via SQL integrations. 

Built on [Coral](https://withcoral.com) for cross-source SQL queries over personal data, Abra acts as a unified command center.

---

## Core Features

| Feature | Description |
|---------|-------------|
| **Voice Logging** | Browser-based audio capture and transcription for structured data entry directly to Notion. |
| **Live Telemetry Dashboard** | Real-time synchronization of Chess.com ratings, Strava activity metrics, and Notion task completion. |
| **Automated Briefing** | AI-generated daily summaries based on goal tracking, past entries, and current activity telemetry. |
| **Context-Aware Analytics** | Conversational interface with access to live SQL data for querying performance metrics (e.g., Chess games or running volume). |
| **Notion Integration** | Bi-directional synchronization for tasks, statuses, and diary logs. |
| **Strava Automation** | OAuth token management, weekly distance tracking, and personal best detection. |

## Architecture

```text
┌─────────────────────────────────────────────────────────────┐
│                    Abra Life OS Dashboard                   │
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
│  LLM Cascade: Gemini → Groq → Cerebras (auto-fallback)      │
└───────┬────────────────┬──────────────────────┬─────────────┘
        │                │                      │
   ┌────▼────┐    ┌──────▼──────┐      ┌───────▼───────┐
   │ Notion  │    │  Coral SQL  │      │ Groq Whisper  │
   │   API   │    │   Engine    │      │ (Voice→Text)  │
   └─────────┘    └──────┬──────┘      └───────────────┘
                         │
              ┌──────────┼──────────┐
              │          │          │
         ┌────▼──┐  ┌───▼────┐ ┌───▼────────┐
         │Chess  │  │Strava  │ │Google      │
         │.com   │  │API     │ │Calendar    │
         └───────┘  └────────┘ └────────────┘
```

## Quick Start

### Prerequisites
- Python 3.10+
- Node.js v18+ (for frontend)
- [Coral CLI](https://withcoral.com/docs/getting-started/installation)
- A Notion integration ([Configuration Guide](https://www.notion.so/my-integrations))
- At least one LLM API key (Gemini recommended)

### Setup

```bash
# Clone the repository
git clone https://github.com/Photon079/Abra.git
cd Abra

# 1. Install Python backend dependencies
pip install -r requirements.txt

# 2. Install React frontend dependencies
cd frontend
npm install
cd ..

# 3. Configure environment variables
cp .env.example .env
# Edit .env with appropriate API keys and secrets

# 4. Register Coral data sources
coral source add --file sources/chesscom.yml
coral source add --file sources/strava.yml

# 5. Authorize Strava OAuth
python3 coral_startup.py --strava-auth

# 6. Start the FastAPI backend
python3 main.py
```

Access the application at **http://127.0.0.1:8000**.

## Coral Source Specifications

Abra utilizes community source specifications for Coral SQL integration:

| Source | Authentication | Tables | Description |
|--------|----------------|--------|-------------|
| **Chess.com** | Public API (None) | `stats`, `profile`, `games`, `clubs` | Player ratings, match history with PGN, and accuracy metrics. |
| **Strava** | OAuth 2.0 | `activities`, `athlete`, `athlete_stats` | Activity tracking, weekly volume, and performance records. |

### Validation
```bash
coral source lint sources/chesscom.yml
coral source lint sources/strava.yml
```

### Example SQL Queries
```sql
-- Chess.com ratings across formats
SELECT chess_blitz__last__rating, chess_rapid__last__rating
FROM chesscom.stats;

-- Recent match accuracy
SELECT white__username, white__result, accuracies__white, time_class
FROM chesscom.games LIMIT 5;

-- Weekly running volume
SELECT name, distance, moving_time, start_date_local
FROM strava.activities LIMIT 10;
```

## Context Files

Abra's LLM context relies on markdown files located in `brain_files/`:

| File | Description |
|------|-------------|
| `master_profile.md` | Core identity, background, and operational priorities. |
| `career_plan.md` | Active milestones and professional objectives. |
| `patterns_for_ai_interaction.md` | Behavioral anti-patterns and intervention protocols. |

## Technology Stack

- **Backend**: Python, FastAPI
- **Frontend**: React 18, Tailwind CSS, Lucide React
- **LLM Orchestration**: Gemini, Groq, Cerebras
- **Transcription**: Groq Whisper API, Web Speech API
- **Data Layer**: Coral SQL Engine
- **State Management**: Notion API

## Project Structure

```text
Abra/
├── main.py              # FastAPI server and API endpoints
├── coral_startup.py     # Source registration and Strava OAuth management
├── llm.py               # LLM provider fallback logic
├── coral_query.py       # Coral SQL query execution interface
├── notion_writer.py     # Notion API integration (diary, tasks, context)
├── memory_loader.py     # Context aggregation from local storage or Notion
├── briefing.py          # Briefing generation module
├── diary.py             # Audio-to-structured diary processor
├── goals.py             # Goal decomposition system
├── qa.py                # Context-aware query handler
├── intent_router.py     # NLP-based message routing
├── patterns.py          # Behavioral pattern analysis
├── sources/
│   ├── chesscom.yml     # Chess.com Coral specification
│   └── strava.yml       # Strava Coral specification
├── brain_files/         # System context and memory
├── frontend/
│   ├── src/             # React application source code
│   ├── public/          # Static web assets
│   └── package.json     # Node.js dependencies
├── .env.example         # Environment variable template
└── requirements.txt     # Python dependencies
```

## Development and Deployment

This repository was developed to showcase how Coral's SQL interface can manage and query disparate personal data sources (Notion, Chess.com, Strava) under a unified conversational interface.

---

**Author:** [Anish](https://github.com/Photon079)  
**Powered by:** [Coral](https://withcoral.com)
