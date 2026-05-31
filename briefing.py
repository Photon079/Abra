"""
briefing.py — Abra daily briefing
Returns structured JSON (not markdown) so the frontend can render it beautifully.
"""

import json
import logging
import os
import datetime
from datetime import timezone, timedelta
from typing import Dict, Any, List

import httpx

from llm import llm_service

logger = logging.getLogger("abra.briefing")


def _get_greeting(hour: int) -> str:
    if 5 <= hour < 12:
        return "Good morning"
    elif 12 <= hour < 17:
        return "Good afternoon"
    elif 17 <= hour < 21:
        return "Good evening"
    else:
        return "Hey, it's late"


def _fetch_recent_tasks(headers: dict, tasks_db_id: str) -> List[Dict]:
    """Fetch tasks created or due in the last 3 days that aren't done."""
    now = datetime.datetime.now(timezone.utc)
    cutoff = now - timedelta(days=3)
    today_str = now.strftime("%Y-%m-%d")

    try:
        res = httpx.post(
            f"https://api.notion.com/v1/databases/{tasks_db_id}/query",
            headers=headers,
            json={"page_size": 100},
            timeout=8,
        )
        res.raise_for_status()
        results = res.json().get("results", [])
    except Exception as e:
        logger.error(f"Failed to fetch tasks: {e}")
        return []

    tasks = []
    for t in results:
        props = t.get("properties", {})

        # Status check — skip done/completed
        status = "Todo"
        if props.get("Status", {}).get("status"):
            status = props["Status"]["status"]["name"]
        if status.lower() in ["done", "completed", "cancelled"]:
            continue

        # Created within last 3 days OR deadline within last 3 days
        created_str = t.get("created_time", "")
        deadline_str = None
        if props.get("Deadline", {}).get("date"):
            deadline_str = props["Deadline"]["date"].get("start", "")

        in_window = False
        overdue = False

        if deadline_str:
            if deadline_str <= today_str:
                overdue = True
            try:
                # If it has a deadline, the deadline MUST be within the last 3 days or in the future
                deadline_dt = datetime.datetime.fromisoformat(deadline_str[:10]).replace(tzinfo=timezone.utc)
                if deadline_dt >= cutoff:
                    in_window = True
            except Exception:
                pass
        else:
            # If no deadline, fallback to checking if it was actually created in the last 3 days
            if created_str:
                try:
                    created_dt = datetime.datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                    if created_dt >= cutoff:
                        in_window = True
                except Exception:
                    pass

        if not in_window:
            continue

        # Title
        title = "Untitled Task"
        for field in ["Task", "Task Name", "Name", "Title"]:
            title_prop = props.get(field, {})
            title_list = title_prop.get("title") or title_prop.get("rich_text", [])
            if title_list and title_list[0].get("plain_text"):
                title = title_list[0]["plain_text"]
                break

        # Category
        category = "General"
        if props.get("Category", {}).get("select"):
            category = props["Category"]["select"]["name"]
        elif props.get("Tags", {}).get("multi_select"):
            tags = props["Tags"]["multi_select"]
            if tags:
                category = tags[0]["name"]

        tasks.append({
            "name": title,
            "category": category,
            "overdue": overdue,
            "status": status,
        })

    return tasks


def _fetch_recent_diary(headers: dict, diary_db_id: str) -> List[Dict]:
    """Fetch last 3 diary entries."""
    try:
        res = httpx.post(
            f"https://api.notion.com/v1/databases/{diary_db_id}/query",
            headers=headers,
            json={"page_size": 3, "sorts": [{"timestamp": "created_time", "direction": "descending"}]},
            timeout=8,
        )
        res.raise_for_status()
        results = res.json().get("results", [])
    except Exception as e:
        logger.error(f"Failed to fetch diary: {e}")
        return []

    entries = []
    for d in results:
        props = d.get("properties", {})
        date_val = d.get("created_time", "")[:10]
        if props.get("Date", {}).get("date"):
            date_val = props["Date"]["date"].get("start", date_val)

        mood = None
        if props.get("Mood", {}).get("select"):
            mood = props["Mood"]["select"]["name"]

        summary = None
        for field in ["Summary", "Entry", "Notes"]:
            if props.get(field, {}).get("rich_text"):
                texts = props[field]["rich_text"]
                if texts:
                    summary = texts[0].get("plain_text", "")[:200]
                    break

        entries.append({"date": date_val, "mood": mood, "summary": summary})

    return entries


def generate_morning_briefing(system_prompt: str) -> Dict[str, Any]:
    now = datetime.datetime.now()
    hour = now.hour
    greeting = _get_greeting(hour)
    time_str = now.strftime("%I:%M %p")

    # ── Fetch Notion data ──────────────────────────────────────────
    from notion_writer import notion_writer

    headers = {
        "Authorization": f"Bearer {os.getenv('NOTION_TOKEN') or os.getenv('NOTION_API_KEY')}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }

    tasks = []
    diary_entries = []

    if notion_writer.client:
        if notion_writer.tasks_db_id and notion_writer.is_database_id(notion_writer.tasks_db_id):
            tasks = _fetch_recent_tasks(headers, notion_writer.tasks_db_id)
        if notion_writer.diary_db_id and notion_writer.is_database_id(notion_writer.diary_db_id):
            diary_entries = _fetch_recent_diary(headers, notion_writer.diary_db_id)

    no_tasks = len(tasks) == 0

    # ── Task message ───────────────────────────────────────────────
    overdue_count = sum(1 for t in tasks if t["overdue"])
    if no_tasks:
        task_message = "nothing open in the last 3 days"
    elif overdue_count > 0:
        task_message = f"{len(tasks)} open task{'s' if len(tasks) != 1 else ''}, {overdue_count} overdue"
    else:
        task_message = f"{len(tasks)} open task{'s' if len(tasks) != 1 else ''} from the last few days"

    # ── LLM prompt ────────────────────────────────────────────────
    tasks_text = "\n".join([f"- {t['name']} [{t['category']}]{' (overdue)' if t['overdue'] else ''}" for t in tasks]) if tasks else "None"
    diary_text = "\n".join([f"- {e['date']}: mood={e['mood'] or 'unknown'}, {e['summary'] or 'no summary'}" for e in diary_entries]) if diary_entries else "None"

    llm_prompt = f"""You are Abra — Anish's personal assistant. You know him well. Right now it's {time_str}.

Here's what's on his plate (last 3 days only):
{tasks_text}

Recent diary:
{diary_text}

Write TWO things. Return ONLY valid JSON, nothing else, no markdown fences:

{{
  "message": "...",
  "nudge": "..."
}}

Rules for message (1-2 sentences):
- Speak like a friend who actually knows him, not a corporate assistant
- Reference something specific from his tasks or diary if available  
- Acknowledge if things feel heavy, or celebrate if things look good
- No "I notice that" or "Based on your data" — just talk normally
- If no tasks and no diary: something warm about a fresh slate

Rules for nudge (1 sentence):
- One specific, concrete thing he could do right now
- Not generic advice — tie it to his actual situation
- Warm but direct. Like: "that research abstract isn't going to write itself — 20 minutes is all it needs"
- If no tasks: something about capturing today before it passes

Tone: Jarvis meets a close friend. Not corporate. Not therapy-speak. Just human."""

    response = llm_service.call(system_prompt, llm_prompt)

    # Parse LLM JSON response
    message = "You showed up. That's the first step."
    nudge = "Pick one thing on that list. Just one. Start there."

    try:
        clean = response.strip()
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        parsed = json.loads(clean.strip())
        message = parsed.get("message", message)
        nudge = parsed.get("nudge", nudge)
    except Exception as e:
        logger.warning(f"LLM returned non-JSON briefing, using fallback. Error: {e}")
        # If LLM returned plain text, use it as the message
        if len(response.strip()) > 10:
            message = response.strip()[:300]

    return {
        "intent": "daily_briefing",
        # Structured fields for the new frontend renderer
        "greeting": greeting,
        "name": "Anish",
        "task_count": len(tasks),
        "task_message": task_message,
        "tasks": tasks[:5],  # cap at 5 cards
        "message": message,
        "nudge": nudge,
        "no_tasks": no_tasks,
        # Keep markdown fallback for compatibility
        "markdown": f"**{greeting}, Anish.**\n\n{message}\n\n_{nudge}_",
    }
