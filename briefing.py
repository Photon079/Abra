import json
import logging
from typing import Dict, Any
from llm import llm_service
from coral_query import coral_query_service

logger = logging.getLogger("abra.briefing")

def generate_morning_briefing(system_prompt: str) -> Dict[str, Any]:
    """
    Assembles today's schedule and yesterday's activity data using Coral,
    and calls the LLM to format a concise, zero-fluff daily brief.
    Includes active checks for self-sabotage behavioral patterns.
    """
    logger.info("Generating Morning OS Briefing.")
    
    # 2. Fetch Notion pages modified recently via search (pages table requires page_id filter)
    notion_sql = "SELECT * FROM notion.search LIMIT 5"
    pages = coral_query_service.run_query(notion_sql)
    pages_str = json.dumps(pages, indent=2) if pages else "No pages edited recently."

    # 3. Request LLM briefing synthesis
    prompt = f"""Construct Anish's daily morning briefing.
Notion files recently modified:
{pages_str}

Yesterday's stated priority: Finish custom Spec and practice sliding window questions.

Briefing requirements:
1. Provide a concise bulleted list of his schedule today.
2. Formulate exactly oneSuggested Focus Block for today. Be direct, no fluff.
3. Check for behavioral patterns (e.g. Scatter Loop, Junk Fuel Days, late night overthinking) and flag them by name in warning panels.
Follow the zero-sugarcoating, peer-like tone laws strictly.
"""

    response_md = llm_service.call(system_prompt, prompt)
    return {
        "intent": "daily_briefing",
        "markdown": response_md
    }
