import os
import json
import logging
import subprocess
from typing import List, Dict, Any

logger = logging.getLogger("abra.coral_query")

class CoralQueryService:
    def __init__(self):
        self.coral_path = None
        try:
            # Look up Coral CLI in system PATH
            result = subprocess.run(["which", "coral"], capture_output=True, text=True)
            if result.returncode == 0:
                self.coral_path = result.stdout.strip()
        except Exception:
            pass

        # Fallback: Look in local project root directory
        if not self.coral_path:
            local_bin = os.path.join(os.path.dirname(os.path.abspath(__file__)), "coral")
            if os.path.exists(local_bin) and os.access(local_bin, os.X_OK):
                self.coral_path = local_bin

        if self.coral_path:
            logger.info(f"Coral CLI detected in path: {self.coral_path}")
        else:
            logger.warning("Coral CLI not installed. Operating in simulation mode for SQL data.")

    def run_query(self, sql_query: str) -> List[Dict[str, Any]]:
        """
        Executes a SQL query against the Coral CLI query engine.
        If Coral is not installed locally, interprets the query and returns high-fidelity simulated
        cross-source joins across Chess.com, Google Calendar, Notion, and Strava.
        """
        logger.info(f"Coral executing SQL query: {sql_query.strip()}")
        
        if self.coral_path:
            try:
                # Command: coral sql "<sql>" --format json
                cmd = [self.coral_path, "sql", sql_query, "--format", "json"]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
                if result.returncode == 0:
                    return json.loads(result.stdout)
                else:
                    err_msg = result.stderr.strip()
                    if "not found" in err_msg or "not currently registered" in err_msg:
                        logger.info("Schema/Table not registered in Coral yet. Using simulation fallback for query.")
                    else:
                        logger.error(f"Coral query error: {err_msg}")
            except Exception as e:
                logger.error(f"Error querying Coral CLI binary: {e}")

        # High-Fidelity Simulation Engine for Hackathon Demo
        return self._simulate_sql_query(sql_query)

    def _simulate_sql_query(self, sql_query: str) -> List[Dict[str, Any]]:
        """
        Mock SQL resolver to provide seamless, realistic telemetry data for Anish's daily routines.
        """
        query_upper = sql_query.upper()
        from datetime import datetime, timedelta
        
        today_date = datetime.now().strftime("%Y-%m-%d")
        yesterday_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

        # 1. Chess.com Stats Query
        if "CHESSCOM.STATS" in query_upper:
            return [
                {
                    "username": "anish789098",
                    "rating_rapid": 1485,
                    "rating_blitz": 1395,
                    "rating_bullet": 1310,
                    "rapid_wins": 182,
                    "rapid_losses": 161,
                    "rapid_draws": 24
                }
            ]

        # 2. Chess.com Games Query (Match History)
        elif "CHESSCOM.GAMES" in query_upper:
            return [
                {
                    "date": today_date,
                    "time_class": "rapid",
                    "rating": 1485,
                    "opponent": "Grandmaster_Mock",
                    "result": "win",
                    "opening": "Sicilian Defense: Alapin Variation"
                },
                {
                    "date": yesterday_date,
                    "time_class": "blitz",
                    "rating": 1395,
                    "opponent": "RookSacrifice",
                    "result": "loss",
                    "opening": "Queen's Gambit Declined"
                },
                {
                    "date": yesterday_date,
                    "time_class": "blitz",
                    "rating": 1401,
                    "opponent": "EnPassantMate",
                    "result": "loss",
                    "opening": "Italian Game: Evans Gambit"
                }
            ]

        # 3. Google Calendar Events Query
        elif "GOOGLE_CALENDAR.EVENTS" in query_upper or "CAL." in query_upper:
            # If joining with Notion.pages today
            if "NOTION.PAGES" in query_upper or "N.TITLE" in query_upper:
                return [
                    {
                        "event_title": "ML CS229 Lecture Review",
                        "meeting_mins": 90,
                        "notion_page_edited": "career_plan.md",
                        "edited_at": f"{today_date}T11:30:00Z"
                    },
                    {
                        "event_title": "Run 6K Grounding session",
                        "meeting_mins": 32,
                        "notion_page_edited": "patterns_for_ai_interaction.md",
                        "edited_at": f"{today_date}T16:15:00Z"
                    },
                    {
                        "event_title": "Abra Core Planning session",
                        "meeting_mins": 120,
                        "notion_page_edited": "abra_prd.md",
                        "edited_at": f"{today_date}T18:20:00Z"
                    }
                ]
            
            # Simple Calendar Query
            return [
                {"title": "ML CS229 Lecture Review", "start_time": f"{today_date} 11:30:00", "duration_min": 90},
                {"title": "Run 6K Grounding session", "start_time": f"{today_date} 16:15:00", "duration_min": 32},
                {"title": "Abra Core planning", "start_time": f"{today_date} 18:00:00", "duration_min": 120}
            ]

        # 4. Notion Search Query (notion.search works without page_id filter)
        elif "NOTION.SEARCH" in query_upper:
            return [
                {"id": "abc123", "object": "page", "url": "https://notion.so/abra_prd", "last_edited_time": f"{today_date}T18:11:00Z", "properties": {"title": "abra_prd.md"}},
                {"id": "def456", "object": "page", "url": "https://notion.so/career_plan", "last_edited_time": f"{today_date}T12:00:00Z", "properties": {"title": "career_plan.md"}},
                {"id": "ghi789", "object": "page", "url": "https://notion.so/patterns", "last_edited_time": f"{yesterday_date}T15:00:00Z", "properties": {"title": "patterns_for_ai_interaction.md"}}
            ]

        # 4b. Notion Pages Query (requires page_id filter in real Coral, but kept for simulation)
        elif "NOTION.PAGES" in query_upper:
            return [
                {"id": "abc123", "url": "https://notion.so/abra_prd", "last_edited_time": f"{today_date}T18:11:00Z", "properties": {"title": "abra_prd.md"}},
                {"id": "def456", "url": "https://notion.so/career_plan", "last_edited_time": f"{today_date}T12:00:00Z", "properties": {"title": "career_plan.md"}},
                {"id": "ghi789", "url": "https://notion.so/patterns", "last_edited_time": f"{yesterday_date}T15:00:00Z", "properties": {"title": "patterns_for_ai_interaction.md"}}
            ]

        # 5. Strava Running Telemetry Query
        elif "STRAVA.ACTIVITIES" in query_upper:
            return [
                {
                    "distance_km": 6.2,
                    "elapsed_time_mins": 32,
                    "average_speed": 3.22,
                    "pace_per_km": "5:10",
                    "start_date": today_date,
                    "average_heartrate": 145.0
                },
                {
                    "distance_km": 10.0,
                    "elapsed_time_mins": 54,
                    "average_speed": 3.08,
                    "pace_per_km": "5:28",
                    "start_date": (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d"),
                    "average_heartrate": 158.0
                },
                {
                    "distance_km": 14.2,
                    "elapsed_time_mins": 81,
                    "average_speed": 2.92,
                    "pace_per_km": "5:42",
                    "start_date": (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d"),
                    "average_heartrate": 155.0
                }
            ]

        # General Fallback array
        return []

# Global single instance
coral_query_service = CoralQueryService()
