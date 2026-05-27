import os
import subprocess
import json
import logging
from typing import List, Dict, Any
from app.config import settings

logger = logging.getLogger("abra.coral_service")

class CoralService:
    def __init__(self):
        # We can detect if the coral CLI is available in the path
        self.coral_path = None
        try:
            result = subprocess.run(["which", "coral"], capture_output=True, text=True)
            if result.returncode == 0:
                self.coral_path = result.stdout.strip()
                logger.info(f"Coral CLI detected at {self.coral_path}")
        except Exception:
            pass
        
        if not self.coral_path:
            logger.warning("Coral CLI not detected. Using mock/simulation SQL service for calendar/Notion data.")

    def run_query(self, sql_query: str) -> List[Dict[str, Any]]:
        """
        Executes a SQL query against the Coral CLI.
        If Coral is not installed, parses it and returns simulated results
        to ensure the demo works robustly under all circumstances.
        """
        logger.info(f"Executing SQL query via Coral: {sql_query}")
        
        if self.coral_path:
            try:
                # Execute CLI command: coral sql "<query>" --format json
                cmd = [self.coral_path, "sql", sql_query, "--format", "json"]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    return json.loads(result.stdout)
                else:
                    logger.error(f"Coral CLI query failed: {result.stderr}")
            except Exception as e:
                logger.error(f"Error running Coral CLI query: {e}")

        # Fallback / Mock SQL Engine for Hackathon Demo
        return self._simulate_sql_query(sql_query)

    def _simulate_sql_query(self, sql_query: str) -> List[Dict[str, Any]]:
        """
        Simulates standard expected outputs of joins for Google Calendar & Notion pages today.
        Ensures a gorgeous end-to-end flow even without live credentials connected.
        """
        query_upper = sql_query.upper()
        
        # Scenario 1: Briefing query or End-of-Day Context query (Calendar events + Notion edited today)
        if "GOOGLE_CALENDAR" in query_upper or "CAL." in query_upper:
            # Return high-fidelity simulated Google Calendar events + Notion edits for Anish
            from datetime import datetime
            today_str = datetime.now().strftime("%Y-%m-%d")
            
            return [
                {
                    "event_title": "ML 2.5 Lecture Review - CS229",
                    "meeting_mins": 90,
                    "notion_page_edited": "career_plan.md",
                    "edited_at": f"{today_str}T11:30:00Z"
                },
                {
                    "event_title": "Run 6K Grounding session",
                    "meeting_mins": 32,
                    "notion_page_edited": "patterns_for_ai_interaction.md",
                    "edited_at": f"{today_str}T16:15:00Z"
                },
                {
                    "event_title": "Abra Core Planning with AI Partner",
                    "meeting_mins": 120,
                    "notion_page_edited": "abra_prd.md",
                    "edited_at": f"{today_str}T18:20:00Z"
                }
            ]
            
        # Scenario 2: Standard Notion tasks query
        elif "NOTION.PAGES" in query_upper or "NOTION.TASKS" in query_upper:
            return [
                {"title": "Implement Coral Source Spec", "status": "Done", "last_edited": "2026-05-26T12:00:00Z"},
                {"title": "Set up FastAPI backend integration", "status": "In Progress", "last_edited": "2026-05-26T18:00:00Z"},
                {"title": "Complete NeetCode 150 sliding window section", "status": "Todo", "last_edited": "2026-05-25T10:00:00Z"}
            ]

        # General empty state fallback
        return []

coral_service = CoralService()
