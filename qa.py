import json
import logging
from typing import Dict, Any
from llm import llm_service
from coral_query import coral_query_service

logger = logging.getLogger("abra.qa")

def answer_memory_query(user_input: str, system_prompt: str) -> Dict[str, Any]:
    """
    Resolves memory queries about Anish's stats (Chess rating, 5K PB, Landslide paper)
    by running targeted SQL queries through Coral and compiling responses.
    """
    logger.info(f"Resolving memory Q&A query: '{user_input}'")
    
    context_data = []
    user_input_lower = user_input.lower()
    
    # 1. Route to Chess.com stats
    if "chess" in user_input_lower or "rating" in user_input_lower or "win" in user_input_lower:
        sql = "SELECT chess_blitz__last__rating, chess_rapid__last__rating, chess_rapid__record__win, chess_rapid__record__loss FROM chesscom.stats"
        res = coral_query_service.run_query(sql)
        context_data.append({"chess_stats": res})
        
        # Also grab recent matches
        games_sql = "SELECT pgn, time_class, white__username, white__rating, white__result, black__username, black__rating, black__result, accuracies__white, accuracies__black FROM chesscom.games ORDER BY end_time DESC LIMIT 2"
        games_res = coral_query_service.run_query(games_sql)
        context_data.append({"recent_games": games_res})

    # 2. Route to Running telemetry
    if "run" in user_input_lower or "pb" in user_input_lower or "marathon" in user_input_lower or "strava" in user_input_lower or "pace" in user_input_lower:
        sql = "SELECT (distance / 1000) AS distance_km, elapsed_time, average_speed, start_date, type FROM strava.activities ORDER BY start_date DESC LIMIT 5"
        res = coral_query_service.run_query(sql)
        context_data.append({"strava_activities": res})

    # 3. Route to Notion Tasks and Diary
    if any(kw in user_input_lower for kw in ["notion", "task", "diary", "schedule", "goal", "plan", "todo", "today"]):
        try:
            import httpx
            from notion_writer import notion_writer
            if notion_writer.client and notion_writer.tasks_db_id and notion_writer.diary_db_id:
                headers = {
                    "Authorization": f"Bearer {notion_writer.client.auth}",
                    "Notion-Version": "2022-06-28",
                    "Content-Type": "application/json"
                }
                
                # Fetch tasks
                if notion_writer.is_database_id(notion_writer.tasks_db_id):
                    tasks_res = httpx.post(f"https://api.notion.com/v1/databases/{notion_writer.tasks_db_id}/query", headers=headers, json={"page_size": 10})
                    tasks = []
                    for p in tasks_res.json().get("results", []):
                        try:
                            title = p.get("properties", {}).get("Task Name", {}).get("title", [{"plain_text": "Untitled"}])[0].get("plain_text", "Untitled")
                            status = p.get("properties", {}).get("Status", {}).get("status", {}).get("name", "Todo")
                            tasks.append({"title": title, "status": status})
                        except: pass
                    context_data.append({"recent_tasks": tasks})
                
                # Fetch diary
                if notion_writer.is_database_id(notion_writer.diary_db_id):
                    diary_res = httpx.post(f"https://api.notion.com/v1/databases/{notion_writer.diary_db_id}/query", headers=headers, json={"page_size": 5})
                    diary = []
                    for p in diary_res.json().get("results", []):
                        try:
                            date = p.get("properties", {}).get("Date", {}).get("date", {}).get("start", "")
                            r_text = p.get("properties", {}).get("Summary", {}).get("rich_text", [])
                            summary = r_text[0].get("plain_text", "") if r_text else ""
                            diary.append({"date": date, "summary": summary})
                        except: pass
                    context_data.append({"recent_diary": diary})
        except Exception as e:
            logger.warning(f"Failed to fetch notion context in QA: {e}")

    context_str = json.dumps(context_data, indent=2) if context_data else "No live telemetry found for this query context."

    # Call LLM to compile direct response
    prompt = f"""Anish has asked a question: "{user_input}"
Telemetry retrieved via Coral SQL & Notion:
{context_str}

Examine this context and answer his question accurately.
Ground your response in his master profile, goals, and these telemetry stats.
Follow the brutal honesty and conciseness rules strictly.
"""

    response_md = llm_service.call(system_prompt, prompt)
    return {
        "intent": "qna",
        "markdown": response_md,
        "telemetry_context": context_data
    }
