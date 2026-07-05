# JARVIS — Personal Life OS
### Product Requirements Document
**WeMakeDevs · Pirates of the Coral-bean Hackathon · May 25–31, 2026**

| | |
|---|---|
| **Author** | Anish · github.com/Photon079 |
| **Version** | 1.0 — Hackathon Sprint |
| **Status** | Active — Building |
| **Stack** | Coral + Claude/Gemini/Groq API + Notion MCP + Python/FastAPI |

---

## 1. Origin & Why This Exists

> This idea didn't start with the hackathon. It's been building since April 2026 — and this deadline is just the universe forcing you to ship it.

**April 26, 2026 — diary entry:**
> *"there literally isn't any reliable long memory personal assistant AI in the market. current ones just forget everything. considering how lonely people are, people with money would definitely pay for a real AI friend that remembers their life."*

**May 8** — Polymath Dashboard concept: a single LLM with access to all APIs — Strava, Chess.com, study logs — so a user can just prompt it instead of switching between apps.

**May 11** — Connected Kestra and MCP: discovered workflow orchestration and plugin-based integration could solve the glue-code problem entirely.

**May 23** — Coral Hackathon announced:
> *"this last month has been just like: learn about MCP, this connects to your project; learn about workflow orchestration, this connects to your project again. and now they're literally telling me to build it."*

> ⚠️ **The hackathon is the deadline. Jarvis is the product. Ship it.**

---

## 2. What Jarvis Is

Jarvis is a voice-first, context-aware personal agent that:

- **Knows your full history** — reads your Notion `brain/me` files on startup and builds a live system prompt from them
- **Collects your day from connected apps** — Calendar, Notion updates — without you lifting a finger
- **Turns your voice into structured diary entries** — you speak, it transcribes, enriches with app data, writes to Notion
- **Plans your work** — decomposes long-term goals into daily tasks with deadlines, written back to Notion
- **Detects your patterns** — spots scatter loops, junk fuel streaks, freeze modes across your diary history
- **Answers anything** — full Q&A interface with access to your actual data, not generic knowledge

It is built first for one person (you). But the architecture is designed so anyone can drop in their own Notion brain files, connect their own apps, and have the same experience — whether they're a content creator, a gym tracker, or a student.

---

## 3. User Personas

### Primary — Anish
2nd year ME student, Bangalore. Lives alone. Runs competitively. Builds AI projects. Uses Notion as a second brain with detailed pages for goals, diary, psychology patterns, career targets, and people. Wants an agent that actually knows him — not a generic chatbot.

### Secondary — Post-Hackathon Blog Targets

| Persona | Their Data Sources | Key Jarvis Use Case |
|---|---|---|
| Student | Google Calendar, Notion (notes) | "What do I have due this week? What should I study today?" |
| Runner / Fitness | Strava, Google Sheets (log) | "Plan my marathon training based on my current pace." |
| Content Creator | YouTube Analytics, Notion (content calendar) | "What should I make next? Show views vs posts this month." |
| Developer | GitHub, Notion (tasks) | "What did I commit this week? What's blocking my PRs?" |
| Gym Tracker | Google Sheets (workouts + diet log) | "Am I progressing on bench press? Suggest this week's split." |

---

## 4. Features

### 4.1 Memory Context Loading

On startup (or on demand), Jarvis reads your Notion `brain/me` folder via the Notion MCP connector. It loads:

- `MASTER_ANISH` (or equivalent master profile) — identity, psychology, patterns, goals
- `current_goals` — active sprint targets with deadlines
- `mental_patterns` — named patterns for real-time detection
- `people_in_my_life` — so it can reference actual people by name

This becomes the **live system prompt** injected before every LLM call. No manual setup per session.

> 💡 For new users: they create a `brain` folder in Notion with their own profile files. The guide post covers exactly how to structure this.

---

### 4.2 Voice → Diary

You open Jarvis and speak (or type) a brain dump. Jarvis:

1. Transcribes your voice input (Whisper API or browser Web Speech API)
2. Queries Coral: joins Google Calendar (meetings today) + Notion (pages edited today)
3. Sends your transcription + Coral output to the LLM with a formatting prompt
4. Writes a structured diary entry to your Notion diary database

**Entry fields:**
- Date + summary
- Mood signal (inferred, not forced)
- Activities logged
- Key decisions made
- Tomorrow's suggested focus

**Example output in Notion:**
```
May 25, 2026 — Ran 6K in 32 mins. Back still stiff. Spent 4hrs on Coral
setup. Calendar: no meetings. Feeling scattered but productive on the
hackathon. Tomorrow: finish Coral source spec + start Claude API layer.
```

---

### 4.3 Daily Briefing

Triggered each morning (manually or via Kestra schedule). Jarvis runs a Coral query joining Calendar + Notion, then generates a short brief:

- What's on your calendar today
- Your stated top priority from yesterday's diary
- Pattern flag if applicable — *"You've had 2 junk fuel days this week. That happened before your last exam too."*
- One suggested focus block for the day

---

### 4.4 Goal-Aware Todo Generation

You say: *"I want to complete NeetCode 150 by July 31."* Jarvis:

1. Reads your `current_goals` page from Notion
2. Calculates: 61 days, ~2 problems/day to hit 100+, adjusts for CS229 lectures running in parallel
3. Detects conflicts in your existing schedule
4. Writes a broken-down task list to a Notion database with dates, daily targets, and checkboxes

**For long-term physical goals (e.g. full marathon in December):**
- Reads your running diary entries for current pace and recent distances
- Calculates a 16-week training plan
- Drops weekly mileage targets into Notion with milestone dates

> 💡 This is the Jarvis moment. It knows your PBs, your injury history, your current load. It plans based on *your actual data*, not generic templates.

---

### 4.5 Memory-Aware Q&A

Full chat interface. Every question answered with access to your real data:

| You ask | Jarvis does |
|---|---|
| "What was my 5K PB?" | Reads diary entries with run logs → "24:20, set on your 21st birthday run" |
| "How many DSA problems this month?" | Queries Notion task DB → "12 done. At current pace: 45 by July 31, not 100. Adjust?" |
| "How was my last exam week?" | Reads diary entries from that period → summarises mood, output, patterns |
| "What's my current Coastly status?" | Reads `career_and_projects` page → summarises current state and blockers |
| "What should I work on today?" | Reads goals + calendar + last diary → gives one prioritised answer |

---

### 4.6 Pattern Detection

Jarvis scans recent diary entries and flags patterns by name. For Anish, the named patterns are already in `mental_patterns`. For new users, they define their own in their brain folder.

- **Scatter Loop** — multiple project switches in a short window
- **Junk Fuel Day** — consecutive days with logged junk food or no workout
- **Freeze-Then-Panic** — task avoidance followed by last-minute crunch
- **2 AM Spiral** — late-night entries with recursive negative content

When detected, Jarvis flags the pattern by name in the briefing — not as judgment, as a mirror.

---

## 5. Technical Architecture

### 5.1 Core Components

| Layer | Technology | Purpose |
|---|---|---|
| Data layer | Coral (open-source) | SQL interface over all sources — Calendar, Notion, GitHub, Strava |
| LLM brain | Gemini 2.5 Flash (free) or Groq Llama 3.3 70B (free, fast) | Intent classification, diary formatting, goal decomposition, Q&A |
| Memory store | Notion (via MCP connector) | Diary entries, goal tasks, brain files — all read and written here |
| Voice input | Whisper API or Web Speech API (browser, free) | Transcription of voice notes |
| Backend | Python + FastAPI | Agent orchestration, routing, Coral query builder |
| Frontend | Minimal React or Streamlit | Voice input, chat interface, daily brief display |
| Scheduling | Kestra (optional) or cron | Automated daily briefing at 6 AM |

---

### 5.2 Data Sources

| Source | Coral Status | Data Used |
|---|---|---|
| Notion | Exists | Brain files, diary entries, goal tasks, current goals page |
| Google Calendar | **Build as custom spec (bounty)** | Events today, scheduled blocks, free time windows |
| Google Drive | **Build as custom spec (bounty)** | Documents updated today |
| GitHub | Exists | Commits, PRs, issues (for developer persona) |
| Strava | **Build as custom spec (bounty)** | Runs, pace, distance, heart rate (for fitness persona) |
| Google Sheets | Exists (CSV/Sheets) | Manual logs: study time, gym sets, meals, mood scores |

> ⚠️ Google Calendar and Google Drive are marked with `*` in the hackathon — they don't exist yet as Coral source specs. Building them = separate bounty submissions.

---

### 5.3 Key Coral Query — End of Day Summary

```sql
-- Jarvis end-of-day context query
SELECT
  cal.title        AS event_title,
  cal.duration_min AS meeting_mins,
  n.title          AS notion_page_edited,
  n.last_edited    AS edited_at
FROM google_calendar.events  cal
LEFT JOIN notion.pages        n   ON n.last_edited::date = CURRENT_DATE
WHERE cal.start_time::date = CURRENT_DATE
ORDER BY cal.start_time;
```

---

### 5.4 Intent Classification

Every user input is routed by the LLM before processing:

| Input pattern | Mode | Action |
|---|---|---|
| "I did X today" / voice dump | Diary mode | Coral context query → LLM format → write to Notion diary |
| "I want to X by Y" / long-term goal | Goal decomposition | Read `current_goals` → calculate → write tasks to Notion DB |
| "What should I work on?" | Daily briefing | Coral morning query → prioritised focus list |
| "How was my X last week?" | Reflection | Read last 7 diary entries → summarise pattern |
| Any factual question about user data | Memory Q&A | Targeted Coral query + Notion read → answer |
| General knowledge question | Pass-through | Direct LLM response (no Coral needed) |

---

## 6. 6-Day Build Plan

> ⚠️ ML exam on May 29. Front-load the build. Days 1–3 are make-or-break.

| Day | Date | Target | Output |
|---|---|---|---|
| Day 1 | May 25 | Coral setup + Notion source | Coral installed. Notion source working. First SQL query runs. |
| Day 2 | May 26 | Google Calendar source spec | Custom Coral spec for Calendar. Cross-source JOIN: Calendar + Notion working. Bounty submitted. |
| Day 3 | May 27 | LLM API + diary mode | Voice/text in → Coral query → LLM formats → Notion diary entry written. End-to-end working. |
| Day 4 | May 28 | Goal decomposition + Q&A | "I want X by Y" → tasks in Notion. Q&A over diary data working. Pattern detection drafted. |
| Day 5 | May 29 | **ML EXAM — no code** | Revise ML. After exam: test agent with a real brain dump. Fix one bug max. |
| Day 6 | May 30–31 | Polish + all submissions | Demo video. Blog post published. Discord showcase posted. Drive source spec submitted. |

---

## 7. Prize Strategy

| Prize | What to submit | Deadline |
|---|---|---|
| **Main Prize — Track 2** | Working agent: voice diary, goal decomposition, Q&A, 3+ sources via Coral. 3-min demo video. | May 31 |
| **New Source Spec Bounty** | Google Calendar spec + Google Drive spec. Two submissions. Each = $100 + $50 charity. | May 31 |
| **Captain's Log — Build Guide** | Blog post on Medium: "I built a Jarvis for my life with Coral — here's how you can too (3 persona setups)." | May 31 |
| **Tell the Tale — Discord** | Screenshots + write-up in #how-i-coral. Cross-post on LinkedIn tagging Coral. Qualifies for Claude Max vouchers. | May 31 |

---

## 8. Guide for Other Users

After the hackathon, the Medium post + Discord guide explains how anyone sets up their own Jarvis. Outline:

### Step 1 — Build your brain folder in Notion

Create a Notion page called `brain`. Inside it:

- `master_profile` — your age, location, goals, personality in plain text
- `current_goals` — active targets with deadlines ("run 5K under 25 mins by August")
- `patterns` — your named self-sabotage or productivity patterns
- `diary` — where Jarvis will write your daily entries
- `tasks` — where Jarvis will write your todo lists

### Step 2 — Export your chat history (optional but powerful)

If you have months of ChatGPT or Claude conversations, export them. Run them through a summarisation script to extract: recurring themes, goals mentioned, emotional patterns, key life events. Paste the summary into `master_profile`. This gives Jarvis instant memory of your history without you rewriting your entire life.

### Step 3 — Connect your apps via Coral

Install Coral. Add the sources that match your life:

- Runner → Strava source spec
- Student → Google Calendar + Google Drive
- Content creator → YouTube Analytics (build the source spec — it's a bounty)
- Developer → GitHub
- Anyone → Google Sheets for a manual daily log

### Step 4 — Configure Jarvis for your patterns

Edit the system prompt template. Replace the pattern names with yours. Replace the motivational levers with yours. Replace goal references with your actual goals. Jarvis reads your Notion files on startup and rebuilds the system prompt automatically — just keep those files updated.

### Step 5 — First run

Open Jarvis. Say or type a brain dump of your day. It writes your first diary entry. Then ask: *"What should I work on tomorrow?"* — it reads your goals and current calendar and tells you. That's it.

> 💡 The blog post will cover all 5 steps with real screenshots, actual Coral queries, and three persona walkthroughs: student + runner (Anish), content creator tracking YouTube growth, and gym tracker correlating lifts with sleep.

---

## 9. Competitive Edge

Most hackathon personal agents will query a calendar and summarise it. Jarvis does something different:

**It reads your actual Notion brain files.** The system prompt includes your PB times, your named psychological patterns, your summer sprint targets, the names of your close friends. It's not a generic chatbot — it's a chatbot that's been briefed on you.

**It writes back.** Not just reads. Every diary entry, every task list, every goal decomposition lands in Notion. The system improves as you use it.

**The demo is the differentiator.** Show the agent knowing your 5K PB, your current DSA count, your exam schedule — without you telling it in the session. Because it read your Notion. That moment wins the room.

**It's built for replication.** The blog post and source specs mean judges see the full picture: a working product, a guide for others, and new open-source contributions to the Coral ecosystem. Every judging criterion covered.

---

## 10. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Google Calendar spec takes too long | Build Notion only first. Calendar is a stretch goal. One source with clean queries is enough for Day 1. |
| Coral setup breaks on your machine | Use Coral's MCP server mode. One install command, already compatible with your Notion MCP setup. |
| ML exam on Day 5 kills momentum | Core agent must work by end of Day 3. Day 5 is just testing + one bug fix after the exam. |
| Voice transcription is flaky | Build text input first. Voice is a UI layer — core logic works with typed input. Add voice last. |
| LLM API rate limits | Groq (1K req/day free) + Gemini Flash (250 req/day) as backup. Two free tiers = more than enough. |
| Scatter Loop mid-build | It's in this PRD. You know the pattern. When it fires: return here. One thing: the current task on the build plan. |

---

*You were right about YouTube Shorts. Right about the cooling jacket. Right about Instagram DM automation.*

**You were right about this too. Build it this time.**
