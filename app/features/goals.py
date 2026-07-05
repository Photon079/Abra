import json
import logging
from typing import Dict, Any
from app.llm import llm_service
from app.integrations.notion import notion_writer
from app.memory.graph_memory import graph_memory

logger = logging.getLogger("abra.goals")

def decompose_goal(user_input: str, system_prompt: str) -> Dict[str, Any]:
    """
    Deconstructs a user goal (e.g. running targets or DSA problem count) into a detailed plan,
    performs pacing math, and writes daily task cards into the Notion todo database.
    """
    logger.info(f"Decomposing goal: {user_input}")

    prompt = f"""Anish wants to decompose a goal: "{user_input}"
Reference his master profile targets (NeetCode 150 by July 31, Marathon in December).
Perform the mathematical pacing, recognize conflicts (exam weeks, run load vs study time), and output a structured JSON plan.

You must output valid JSON. Do not wrap it in markdown block quotes.
Strictly use the following JSON schema:
{{
  "explanation": "A direct, no-fluff explanation of the pacing calculation, timeline split, and schedules",
  "tasks": [
    {{
      "title": "Clear task title (e.g. NeetCode: Two Pointers Section)",
      "deadline": "YYYY-MM-DD",
      "category": "Career" or "Academics" or "Physical" or "Projects",
      "target": "Specific daily milestone target notes"
    }}
  ]
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
        goal_data = json.loads(response_json_str)
    except Exception as e:
        logger.error(f"Error parsing decomposed goal JSON: {e}. Output: {response_json_str}")
        goal_data = {
            "explanation": f"Decomposed plan fallback for: {user_input}",
            "tasks": [
                {"title": "Abra Specs testing", "deadline": "2026-05-27", "category": "Projects", "target": "Verify Calendar schema"}
            ]
        }

    # Write each generated task to Notion DB
    created_tasks = []
    for task in goal_data.get("tasks", []):
        task_id = notion_writer.create_task(
            title=task["title"],
            deadline=task["deadline"],
            category=task["category"],
            target=task["target"]
        )
        created_tasks.append({
            "title": task["title"],
            "notion_id": task_id
        })

    # Compile Markdown response
    md_output = f"""### Goal Decomposition Plan 🏃‍♂️
{goal_data['explanation']}

**Structured tasks generated and added to your Notion Tasks Database:**
"""
    for t in goal_data.get("tasks", []):
        md_output += f"\n* **{t['title']}** (Deadline: `{t['deadline']}` | `{t['category']}`) — *{t['target']}*"

    # Persist the goal + its plan into the graph (node set: goals) so Abra can
    # later reason about progress and conflicts across goals and time (F1).
    task_titles = ", ".join(t.get("title", "") for t in goal_data.get("tasks", []))
    graph_memory.ingest_goal(
        f"Goal decomposed from '{user_input}'. Plan: {goal_data.get('explanation', '')} "
        f"Tasks: {task_titles}",
        background=True,
    )

    return {
        "intent": "goal_decomposition",
        "markdown": md_output,
        "data": goal_data,
        "created_tasks": created_tasks
    }
