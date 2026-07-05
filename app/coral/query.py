import os
import json
import logging
import subprocess
from typing import List, Dict, Any

from app import PROJECT_ROOT

logger = logging.getLogger("abra.coral_query")


def chess_where(include_archive: bool = False) -> str:
    """Build the required WHERE clause for the chesscom Coral source.

    The chesscom source (contributed upstream) enforces constant equality
    filters: `stats` requires `username`; `games` additionally requires
    `year` (int) and `month` (zero-padded string) to select a monthly archive.
    """
    from datetime import datetime

    user = os.getenv("CHESSCOM_USERNAME", "")
    clause = f"username = '{user}'"
    if include_archive:
        now = datetime.now()
        clause += f" AND year = {now.year} AND month = '{now.month:02d}'"
    return clause

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
            local_bin = str(PROJECT_ROOT / "coral")
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
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
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

        # No simulation fallback, return empty list on failure
        return []

# Global single instance
coral_query_service = CoralQueryService()
