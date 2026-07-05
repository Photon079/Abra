"""
graph_memory.py — Abra v2 memory plane, backed by Cognee Cloud.

This is the retrieval source of truth for Abra v2. Where v1 dumped raw Notion
text into every prompt, v2 pushes diary entries, goals, and daily telemetry
summaries through Cognee's ``add() -> cognify()`` pipeline into a persistent
knowledge graph, and pulls ranked, relationship-aware context back out via
``search(GRAPH_COMPLETION)``.

Design notes
------------
* Everything is behind the ``USE_GRAPH_MEMORY`` feature flag. If the flag is
  off, Cognee isn't installed, or ``COGNEE_API_KEY`` is missing, every method
  degrades to a no-op / empty string so the legacy Notion path keeps working.
* Cognee's SDK is fully async. FastAPI calls into this module from a mix of
  sync and async request handlers, so we run all coroutines on a single
  long-lived background event loop (one persistent loop keeps the Cognee Cloud
  connection warm across calls). Retrieval blocks for a result; ingestion can
  fire-and-forget so the voice/diary flow is never blocked (PRD risk #2).
* Node sets scope the graph per domain (F5): diary / fitness / chess / goals /
  insights. Retrieval filters with Cognee's ``node_name`` parameter.
"""

import os
import json
import asyncio
import logging
import threading
from typing import Any, Dict, List, Optional

logger = logging.getLogger("abra.graph_memory")

# ── Node sets (F5): scoped retrieval per life domain ──────────────────────────
NODE_DIARY = "diary"
NODE_FITNESS = "fitness"
NODE_CHESS = "chess"
NODE_GOALS = "goals"
NODE_INSIGHTS = "insights"
ALL_NODE_SETS = [NODE_DIARY, NODE_FITNESS, NODE_CHESS, NODE_GOALS, NODE_INSIGHTS]


def _flag(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


class GraphMemory:
    def __init__(self):
        self.enabled = _flag("USE_GRAPH_MEMORY", False)
        self.api_key = os.getenv("COGNEE_API_KEY")
        # PRD uses COGNEE_CLOUD_URL; the SDK docs use COGNEE_SERVICE_URL. Accept both.
        self.cloud_url = os.getenv("COGNEE_CLOUD_URL") or os.getenv("COGNEE_SERVICE_URL")
        self.dataset = os.getenv("COGNEE_DATASET", "abra")
        self.top_k = int(os.getenv("COGNEE_TOP_K", "10"))
        self.search_timeout = float(os.getenv("COGNEE_SEARCH_TIMEOUT", "30"))
        self.ingest_timeout = float(os.getenv("COGNEE_INGEST_TIMEOUT", "120"))

        self._cognee = None
        self._connected = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._loop_lock = threading.Lock()

        if self.enabled and not self.api_key:
            logger.warning(
                "USE_GRAPH_MEMORY is on but COGNEE_API_KEY is missing. "
                "Graph memory disabled; falling back to the legacy Notion loader."
            )
            self.enabled = False

        if self.enabled:
            logger.info(
                "Graph memory ENABLED (Cognee Cloud). dataset=%s url=%s",
                self.dataset, self.cloud_url or "<default>",
            )
        else:
            logger.info("Graph memory DISABLED. Using legacy flat memory.")

    # ── background event loop plumbing ────────────────────────────────────────
    def _ensure_loop(self) -> asyncio.AbstractEventLoop:
        with self._loop_lock:
            if self._loop and self._loop.is_running():
                return self._loop
            self._loop = asyncio.new_event_loop()
            t = threading.Thread(
                target=self._loop.run_forever, name="cognee-loop", daemon=True
            )
            t.start()
            return self._loop

    def _submit(self, coro):
        """Schedule a coroutine on the background loop; returns a concurrent.futures.Future."""
        return asyncio.run_coroutine_threadsafe(coro, self._ensure_loop())

    # ── connection ────────────────────────────────────────────────────────────
    async def _connect(self) -> bool:
        if self._connected:
            return True
        import cognee  # lazy: heavy import, only when the flag is on
        self._cognee = cognee

        serve_kwargs: Dict[str, Any] = {}
        if self.cloud_url:
            serve_kwargs["url"] = self.cloud_url
        if self.api_key:
            serve_kwargs["api_key"] = self.api_key
        # Also mirror into env for any code path that reads config directly.
        if self.api_key:
            os.environ.setdefault("COGNEE_API_KEY", self.api_key)
        if self.cloud_url:
            os.environ.setdefault("COGNEE_SERVICE_URL", self.cloud_url)

        await cognee.serve(**serve_kwargs)
        self._connected = True
        logger.info("Connected to Cognee Cloud (dataset=%s).", self.dataset)
        return True

    def connect_check(self, timeout: float = 20.0) -> bool:
        """Verify Cognee Cloud connectivity at startup (G4 / success metric)."""
        if not self.enabled:
            return False
        try:
            self._submit(self._connect()).result(timeout=timeout)
            logger.info("Cognee Cloud connectivity: OK")
            return True
        except Exception as e:
            logger.warning("Cognee Cloud connectivity check failed: %s", e)
            return False

    # ── low-level ingest / retrieve coroutines ────────────────────────────────
    async def _ingest(self, text: str, node_set: List[str]) -> None:
        await self._connect()
        c = self._cognee
        await c.add(text, dataset_name=self.dataset, node_set=node_set)
        # cognify signature varies across versions; datasets kwarg is optional.
        try:
            await c.cognify(datasets=[self.dataset])
        except TypeError:
            await c.cognify()

    async def _ingest_many(self, items: List[Any]) -> None:
        """items: list of (text, node_set). Adds all, then cognifies ONCE."""
        await self._connect()
        c = self._cognee
        for text, node_set in items:
            if text and str(text).strip():
                await c.add(text, dataset_name=self.dataset, node_set=node_set)
        try:
            await c.cognify(datasets=[self.dataset])
        except TypeError:
            await c.cognify()

    async def _retrieve(self, query: str, node_sets: Optional[List[str]]) -> str:
        await self._connect()
        c = self._cognee
        from cognee import SearchType

        kwargs: Dict[str, Any] = dict(
            query_text=query,
            query_type=SearchType.GRAPH_COMPLETION,
            datasets=[self.dataset],
            top_k=self.top_k,
        )
        if node_sets:
            kwargs["node_name"] = node_sets
            kwargs["node_name_filter_operator"] = "OR"
        try:
            results = await c.search(**kwargs)
        except TypeError:
            # Older/newer signature may not accept node_name — retry unscoped.
            kwargs.pop("node_name", None)
            kwargs.pop("node_name_filter_operator", None)
            results = await c.search(**kwargs)
        return _stringify(results)

    # ── public sync API ───────────────────────────────────────────────────────
    def retrieve(self, query: str, node_sets: Optional[List[str]] = None) -> str:
        """Blocking GRAPH_COMPLETION retrieval. Returns context string or ''."""
        if not self.enabled or not query:
            return ""
        try:
            ctx = self._submit(self._retrieve(query, node_sets)).result(
                timeout=self.search_timeout
            )
            ctx = (ctx or "").strip()
            logger.info("Graph retrieve: %d chars (node_sets=%s)", len(ctx), node_sets)
            return ctx
        except Exception as e:
            logger.warning("Graph retrieve failed (%s). Falling back.", e)
            return ""

    def _ingest_sync(self, text: str, node_set: List[str], background: bool) -> bool:
        if not self.enabled or not text or not text.strip():
            return False
        coro = self._ingest(text, node_set)
        if background:
            fut = self._submit(coro)

            def _log_done(f):
                exc = f.exception()
                if exc:
                    logger.warning("Background graph ingest failed: %s", exc)
                else:
                    logger.info("Background graph ingest OK (node_set=%s).", node_set)

            fut.add_done_callback(_log_done)
            return True
        try:
            self._submit(coro).result(timeout=self.ingest_timeout)
            logger.info("Graph ingest OK (node_set=%s).", node_set)
            return True
        except Exception as e:
            logger.warning("Graph ingest failed: %s", e)
            return False

    # F1 — diary ingestion
    def ingest_diary(self, entry: Dict[str, Any], date: Optional[str] = None,
                     background: bool = True) -> bool:
        return self._ingest_sync(_diary_to_text(entry, date), [NODE_DIARY], background)

    # F3 — daily telemetry snapshot (compact summary, not raw rows — PRD risk #3)
    def ingest_telemetry(self, text: str, node_sets: Optional[List[str]] = None,
                         background: bool = True) -> bool:
        return self._ingest_sync(text, node_sets or [NODE_FITNESS, NODE_CHESS], background)

    # F4 — insight persistence (compounds over time)
    def ingest_insight(self, text: str, background: bool = True) -> bool:
        return self._ingest_sync(text, [NODE_INSIGHTS], background)

    # goals
    def ingest_goal(self, text: str, background: bool = True) -> bool:
        return self._ingest_sync(text, [NODE_GOALS], background)

    def ingest_batch(self, items: List[Any], timeout: Optional[float] = None) -> int:
        """Backfill helper: ingest many (text, node_set) pairs, cognify once.
        Returns the number of items added. Blocking."""
        if not self.enabled:
            return 0
        items = [(t, ns) for (t, ns) in items if t and str(t).strip()]
        if not items:
            return 0
        try:
            self._submit(self._ingest_many(items)).result(
                timeout=timeout or (self.ingest_timeout * 4)
            )
            logger.info("Batch ingest OK: %d items.", len(items))
            return len(items)
        except Exception as e:
            logger.warning("Batch ingest failed: %s", e)
            return 0

    def status(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "connected": self._connected,
            "dataset": self.dataset,
            "cloud_url": self.cloud_url,
            "has_api_key": bool(self.api_key),
        }


# ── helpers ───────────────────────────────────────────────────────────────────
def _diary_to_text(entry: Dict[str, Any], date: Optional[str]) -> str:
    """Render a structured diary dict as natural-language text so Cognee can
    extract entities (mood, activities) and link them to goals across time."""
    if isinstance(entry, str):
        return entry
    from datetime import datetime
    date = date or datetime.now().strftime("%Y-%m-%d")
    activities = entry.get("activities") or []
    if isinstance(activities, list):
        activities = ", ".join(str(a) for a in activities)
    parts = [f"Diary entry for {date}."]
    if entry.get("mood"):
        parts.append(f"Mood: {entry['mood']}.")
    if activities:
        parts.append(f"Activities: {activities}.")
    if entry.get("summary"):
        parts.append(f"Summary: {entry['summary']}")
    if entry.get("decisions"):
        parts.append(f"Key decisions: {entry['decisions']}")
    if entry.get("tomorrow_focus"):
        parts.append(f"Focus for tomorrow: {entry['tomorrow_focus']}")
    return " ".join(parts)


def _stringify(results: Any) -> str:
    """Cognee search results come back as a list of SearchResult-ish objects.
    For GRAPH_COMPLETION each entry is usually the natural-language answer.
    Extract text robustly across shapes."""
    if not results:
        return ""
    if isinstance(results, str):
        return results
    parts: List[str] = []
    items = results if isinstance(results, (list, tuple)) else [results]
    for r in items:
        if r is None:
            continue
        if isinstance(r, str):
            parts.append(r)
        elif isinstance(r, dict):
            # Cognee Cloud shape: {'dataset_id':..., 'search_result': ['answer', ...]}
            sr = r.get("search_result")
            if sr is not None:
                if isinstance(sr, (list, tuple)):
                    parts.extend(str(x) for x in sr if x)
                else:
                    parts.append(str(sr))
            else:
                parts.append(r.get("answer") or r.get("text") or r.get("content") or json.dumps(r))
        else:
            val = None
            for attr in ("answer", "text", "content", "result"):
                val = getattr(r, attr, None)
                if val:
                    break
            parts.append(str(val) if val else str(r))
    return "\n".join(p for p in parts if p and str(p).strip()).strip()


# Global single instance (mirrors the other services in this codebase)
graph_memory = GraphMemory()
