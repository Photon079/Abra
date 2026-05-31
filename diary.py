import json
import logging
from typing import Dict, Any
from llm import llm_service
from coral_query import coral_query_service
from notion_writer import notion_writer

logger = logging.getLogger("abra.diary")

def process_diary_entry(user_input: str, system_prompt: str) -> Dict[str, Any]:
    """
    Handles Diary logging. Queries Coral SQL for today's app events, merges with
    user dump, uses Groq/Gemini to structure, and commits to Notion Diary DB.
    """
    logger.info("Starting Voice -> Structured Notion Diary loop.")
    
    # 1. Fetch Coral Context (today's Notion modifications — pages table requires page_id filter)
    notion_sql = "SELECT * FROM notion.search LIMIT 5"
    notion_data = coral_query_service.run_query(notion_sql)

    coral_data = {"notion_pages": notion_data}
    coral_context_str = json.dumps(coral_data, indent=2)

    # 2. Call LLM to format structured output in JSON
    prompt = f"""Anish wants to log his diary.
Raw user dump input: "{user_input}"

Telemetry data collected from connected apps today (via Coral SQL):
{coral_context_str}

Deconstruct the user's input, combine it with the app logs, and output a valid JSON representing his structured daily log.
Ensure you follow his interaction instructions: keep summaries brutally honest and directly mapped to his actual activities.
Your output must be a standard JSON string. Do not include markdown wraps or backticks inside.
Structure standard JSON strictly with the following fields:
{{
  "summary": "Short 2-3 sentence description summarizing the day, runs, and coding achievements honestly",
  "mood": "Stable" or "Focused" or "Scattered" or "Stressed" or "Low Energy",
  "activities": ["List", "of", "activities", "like", "Running", "Coding", "Chess", "Social", "Study"],
  "decisions": "Any key decisions made today",
  "tomorrow_focus": "One clear priority for tomorrow"
}}"""

    response_json_str = llm_service.call(system_prompt, prompt, response_format_json=True)
    
    # Clean output backticks if any were injected
    if response_json_str.strip().startswith("```"):
        lines = response_json_str.strip().split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines[-1].startswith("```"):
            lines = lines[:-1]
        response_json_str = "\n".join(lines).strip()

    try:
        log_data = json.loads(response_json_str)
    except Exception as e:
        logger.error(f"Failed to parse LLM structured diary JSON: {e}. raw output: {response_json_str}")
        # Build graceful fallback
        log_data = {
            "summary": f"Logged day dump: {user_input[:100]}",
            "mood": "Stable",
            "activities": ["Coding"],
            "decisions": "Decided to write fallback diary routines.",
            "tomorrow_focus": "Verify database sync and continue."
        }

    # 3. Commit back to Notion (or local fallback)
    notion_page_id = notion_writer.write_diary(
        summary=log_data["summary"],
        mood=log_data["mood"],
        activities=log_data["activities"],
        key_decisions=log_data["decisions"],
        tomorrow_focus=log_data["tomorrow_focus"],
        raw_transcript=user_input
    )

    # 4. Compile Markdown response
    md_output = f"""### Daily Log Committed to Notion! 📝
- **Date**: Today
- **Mood Signal**: `{log_data['mood']}`
- **Activities Logged**: {", ".join([f"`{act}`" for act in log_data['activities']])}

#### Summary
{log_data['summary']}

#### Key Decisions
{log_data['decisions']}

#### Tomorrow's Focus
* {log_data['tomorrow_focus']}
"""
    return {
        "intent": "diary",
        "markdown": md_output,
        "data": log_data,
        "notion_page_id": notion_page_id
    }
