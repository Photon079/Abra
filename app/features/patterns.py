import logging
from typing import Dict, Any
from app.llm import llm_service
from app.coral.query import coral_query_service
from app.memory.graph_memory import graph_memory, NODE_DIARY, NODE_INSIGHTS

logger = logging.getLogger("abra.patterns")

def scan_self_sabotage_patterns(system_prompt: str) -> Dict[str, Any]:
    """
    Scans recent diary logs and pages to perform a behavioral analysis.
    Identifies Scatter Loop, Junk Fuel, Freeze-Then-Panic, or 2 AM Spiral by name.
    """
    logger.info("Scanning for behavioral self-sabotage loops.")

    # Query recent logs or diary entries via Coral (pages table requires page_id filter)
    sql = "SELECT * FROM notion.search LIMIT 10"
    pages = coral_query_service.run_query(sql)

    # Pull behavioral history from the graph — this is where relational/temporal
    # signal lives (recurring loops across weeks, not just this week's files).
    graph_history = graph_memory.retrieve(
        "What recurring behavioral patterns, moods, and self-sabotage loops show up "
        "across the diary and past reflections? Note how they relate to sleep, "
        "running, and productivity.",
        node_sets=[NODE_DIARY, NODE_INSIGHTS],
    )
    history_block = graph_history if graph_history else "No graph history yet."

    prompt = f"""Perform a direct, honest, zero-sugarcoating behavioral patterns audit on Anish.
Recent files modified: {pages}

Behavioral history from his knowledge graph (past reflections + diary, relationship-aware):
{history_block}

Audit the last week's logged telemetry.
Examine and search for named loops:
1. **Scatter Loop** (Task avoidance via stack switching, Neovim config scrolling, stack comparison).
2. **Junk Fuel Day** (Eating junk food, consecutive days skipping high-nutrition meals).
3. **Freeze-Then-Panic** (Avoidance loops followed by last-minute deadline crunches).
4. **2 AM Spiral** (Philosophical night worries and overthinking instead of sleeping).
5. **Momentum Day** (High productivity, running logged, positive mood).

Be brutally honest, bruh. Give it to him straight.
"""

    response_md = llm_service.call(system_prompt, prompt)

    # Persist the audit back into the graph as a first-class insight so future
    # reflections compound on it (F4).
    graph_memory.ingest_insight(f"Behavioral pattern audit: {response_md}", background=True)

    return {
        "intent": "reflection",
        "markdown": response_md,
        "graph_history": graph_history,
    }
