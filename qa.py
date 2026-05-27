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
        sql = "SELECT chess_rapid__last__rating AS rating_rapid, chess_rapid__record__win AS rapid_wins, chess_rapid__record__loss AS rapid_losses, chess_rapid__record__draw AS rapid_draws FROM chesscom.stats"
        res = coral_query_service.run_query(sql)
        context_data.append({"chess_stats": res})
        
        # Also grab recent matches
        games_sql = "SELECT time_class, end_time, rated, white__username AS white_username, white__result AS white_result, black__username AS black_username, black__result AS black_result FROM chesscom.games LIMIT 3"
        games_res = coral_query_service.run_query(games_sql)
        context_data.append({"recent_games": games_res})

    # 2. Route to Running telemetry
    elif "run" in user_input_lower or "pb" in user_input_lower or "marathon" in user_input_lower:
        sql = "SELECT start_date, distance_km, pace_per_km, heart_rate_avg FROM strava.activities LIMIT 3"
        res = coral_query_service.run_query(sql)
        context_data.append({"strava_activities": res})

    context_str = json.dumps(context_data, indent=2) if context_data else "No live telemetry found for this query context."

    # Call LLM to compile direct response
    prompt = f"""Anish has asked a question: "{user_input}"
Telemetry retrieved via Coral SQL:
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
