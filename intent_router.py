import logging
from typing import Dict, List

logger = logging.getLogger("abra.intent_router")

# These intents ONLY trigger on explicit user commands, not casual conversation
INTENT_PATTERNS = {
    "diary": [
        "add this to today", "add to today", "add to diary", "add to notes",
        "log this", "log today", "save this", "record this",
        "note this down", "write this down", "diary entry"
    ],
    "goal_decomposition": [
        "decompose", "break down this goal", "plan for", "create a plan",
        "training plan", "help me achieve", "set goal"
    ],
    "daily_briefing": [
        "briefing", "brief me", "today's plan", "morning briefing",
        "what's my schedule", "what do i have today"
    ],
    "reflection": [
        "run reflection", "pattern audit", "behavioral audit",
        "check my patterns", "sabotage check", "reflection"
    ],
}

def classify_intent(user_input: str) -> str:
    """
    Routes ONLY on explicit action commands. Everything else is general chat.
    Chat is the default — diary/goals/briefing only fire on deliberate requests.
    """
    logger.info(f"Classifying intent for input: '{user_input[:40]}...'")
    text_lower = user_input.lower().strip()
    
    # Only match explicit commands
    for mode, keywords in INTENT_PATTERNS.items():
        if any(keyword in text_lower for keyword in keywords):
            logger.info(f"Explicit command detected. Routed to: {mode}")
            return mode
            
    logger.info("General chat mode (default).")
    return "general"
