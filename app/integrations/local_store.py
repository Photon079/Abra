"""
local_store.py — zero-setup, local-first storage for diary entries and tasks.

Motivation: Notion onboarding (integration token + 3 DB IDs + sharing each page)
is the most painful part of setup. This SQLite-backed store lets Abra host its
own diary + to-do surfaces in the frontend with no external accounts. It sits
alongside the Notion integration, not replacing it — the frontend "Second Brain"
page uses this; the existing Notion flows are untouched.

SQLite (stdlib, no dependency) also keeps the door open for Coral to query these
as a local source later, preserving the "everything is SQL" story.
"""

import os
import sqlite3
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

from app import PROJECT_ROOT

logger = logging.getLogger("abra.local_store")

_DB_PATH = os.getenv("ABRA_LOCAL_DB", str(PROJECT_ROOT / "data" / "abra.db"))


class LocalStore:
    def __init__(self, db_path: str = _DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_schema()
        logger.info("LocalStore ready at %s", self.db_path)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self):
        with self._conn() as c:
            c.execute(
                """CREATE TABLE IF NOT EXISTS diary (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    mood TEXT,
                    activities TEXT,
                    summary TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )"""
            )
            c.execute(
                """CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    category TEXT,
                    status TEXT NOT NULL DEFAULT 'todo',
                    created_at TEXT NOT NULL,
                    done_at TEXT
                )"""
            )

    # ── diary ────────────────────────────────────────────────────────────────
    def add_diary(self, summary: str, mood: Optional[str] = None,
                  activities: Optional[List[str]] = None,
                  date: Optional[str] = None) -> Dict[str, Any]:
        now = datetime.now()
        date = date or now.strftime("%Y-%m-%d")
        acts = ", ".join(activities) if activities else ""
        with self._conn() as c:
            cur = c.execute(
                "INSERT INTO diary (date, mood, activities, summary, created_at) VALUES (?,?,?,?,?)",
                (date, mood, acts, summary, now.isoformat(timespec="seconds")),
            )
            return self._get_diary(c, cur.lastrowid)

    def list_diary(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT * FROM diary ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
            return [self._diary_row(r) for r in rows]

    def _get_diary(self, c, row_id) -> Dict[str, Any]:
        r = c.execute("SELECT * FROM diary WHERE id=?", (row_id,)).fetchone()
        return self._diary_row(r)

    @staticmethod
    def _diary_row(r) -> Dict[str, Any]:
        acts = r["activities"] or ""
        return {
            "id": r["id"],
            "date": r["date"],
            "mood": r["mood"],
            "activities": [a.strip() for a in acts.split(",") if a.strip()],
            "summary": r["summary"],
            "created_at": r["created_at"],
        }

    # ── tasks ────────────────────────────────────────────────────────────────
    def add_task(self, title: str, category: Optional[str] = None) -> Dict[str, Any]:
        now = datetime.now().isoformat(timespec="seconds")
        with self._conn() as c:
            cur = c.execute(
                "INSERT INTO tasks (title, category, status, created_at) VALUES (?,?,'todo',?)",
                (title, category, now),
            )
            return self._get_task(c, cur.lastrowid)

    def list_tasks(self, include_done: bool = True) -> List[Dict[str, Any]]:
        q = "SELECT * FROM tasks"
        if not include_done:
            q += " WHERE status != 'done'"
        # open tasks first, newest first within each group
        q += " ORDER BY (status='done') ASC, id DESC"
        with self._conn() as c:
            return [self._task_row(r) for r in c.execute(q).fetchall()]

    def set_task_status(self, task_id: int, status: str) -> Optional[Dict[str, Any]]:
        status = "done" if status == "done" else "todo"
        done_at = datetime.now().isoformat(timespec="seconds") if status == "done" else None
        with self._conn() as c:
            c.execute(
                "UPDATE tasks SET status=?, done_at=? WHERE id=?", (status, done_at, task_id)
            )
            r = c.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
            return self._task_row(r) if r else None

    def delete_task(self, task_id: int) -> bool:
        with self._conn() as c:
            cur = c.execute("DELETE FROM tasks WHERE id=?", (task_id,))
            return cur.rowcount > 0

    def _get_task(self, c, row_id) -> Dict[str, Any]:
        r = c.execute("SELECT * FROM tasks WHERE id=?", (row_id,)).fetchone()
        return self._task_row(r)

    @staticmethod
    def _task_row(r) -> Dict[str, Any]:
        return {
            "id": r["id"],
            "title": r["title"],
            "category": r["category"],
            "status": r["status"],
            "done": r["status"] == "done",
            "created_at": r["created_at"],
            "done_at": r["done_at"],
        }


# Global single instance (mirrors the other services in this codebase)
local_store = LocalStore()
