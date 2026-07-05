import os
import logging
from typing import List, Optional
from datetime import datetime
from notion_client import Client

from app import PROJECT_ROOT

logger = logging.getLogger("abra.notion_writer")


def _to_iso(s: str, fallback: str) -> str:
    """Normalize a Notion date/title string to ISO 'YYYY-MM-DD'."""
    s = (s or "").strip()
    if not s:
        return fallback
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        return s[:10]
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%B %d %Y", "%d %B %Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return fallback


class NotionWriter:
    def __init__(self):
        self.notion_token = os.getenv("NOTION_TOKEN")
        self.diary_db_id = os.getenv("NOTION_DIARY_DB_ID")
        self.tasks_db_id = os.getenv("NOTION_TASKS_DB_ID")
        self.brain_page_id = os.getenv("NOTION_BRAIN_PAGE_ID")
        self.client = None

        if self.notion_token:
            try:
                self.client = Client(auth=self.notion_token)
                logger.info("Notion Client initialized inside NotionWriter.")
            except Exception as e:
                logger.error(f"Failed to initialize Notion Client inside NotionWriter: {e}")
        else:
            logger.warning("No Notion API configurations provided. Operating in local write-back simulation.")
        self._is_db_cache = {}

    def is_database_id(self, target_id: str) -> bool:
        """
        Helper to check whether a given Notion ID belongs to a Database or a simple Page.
        """
        if not self.client or not target_id:
            return False
            
        if target_id in self._is_db_cache:
            return self._is_db_cache[target_id]
            
        try:
            # Temporarily suppress the notion_client logger to avoid spam on expected 400 errors
            notion_logger = logging.getLogger("notion_client")
            old_level = notion_logger.level
            notion_logger.setLevel(logging.ERROR)
            
            self.client.databases.retrieve(database_id=target_id)
            
            notion_logger.setLevel(old_level)
            self._is_db_cache[target_id] = True
            return True
        except Exception:
            notion_logger.setLevel(old_level)
            self._is_db_cache[target_id] = False
            return False

    def write_diary(self, summary: str, mood: str, activities: List[str], key_decisions: str, tomorrow_focus: str, raw_transcript: str = None) -> Optional[str]:
        """
        Appends a diary entry to a Notion Diary Database OR a simple Page block stream.
        If offline, falls back to logging locally in `/home/anish/Documents/Anish/Daily/Diary`.
        """
        today_str = datetime.now().strftime("%B %d, %Y")
        
        if not self.client or not self.diary_db_id:
            logger.warning("Notion offline fallback. Simulating diary write.")
            diary_dir = str(PROJECT_ROOT / "local_data")
            os.makedirs(diary_dir, exist_ok=True)
            diary_file = os.path.join(diary_dir, "Diary")
            
            try:
                with open(diary_file, "a", encoding="utf-8") as f:
                    f.write(f"\n\n## {today_str}\n")
                    f.write(f"**Mood**: {mood}\n")
                    f.write(f"**Activities**: {', '.join(activities)}\n")
                    f.write(f"**Summary**: {summary}\n")
                    f.write(f"**Decisions**: {key_decisions}\n")
                    f.write(f"**Suggested Focus**: {tomorrow_focus}\n")
                logger.info("Successfully appended simulated diary entry to local Daily/Diary file.")
                return "local_fallback_success"
            except Exception as e:
                logger.error(f"Failed to write diary locally: {e}")
                return None

        # Auto-resolver: If NOT a database, treat it as a simple Page and append blocks directly
        if not self.is_database_id(self.diary_db_id):
            logger.info("Treating NOTION_DIARY_DB_ID as a simple Page ID. Appending block timeline.")
            try:
                blocks = [
                    {
                        "object": "block",
                        "type": "heading_2",
                        "heading_2": {
                            "rich_text": [{"type": "text", "text": {"content": today_str}}]
                        }
                    },
                    {
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [
                                {"type": "text", "text": {"content": f"Mood: {mood} | Activities: {', '.join(activities)}\n\n"}},
                                {"type": "text", "text": {"content": summary}}
                            ]
                        }
                    }
                ]
                if key_decisions:
                    blocks.append({
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [{"type": "text", "text": {"content": f"Key Decisions: {key_decisions}"}}]
                        }
                    })
                if tomorrow_focus:
                    blocks.append({
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [{"type": "text", "text": {"content": f"Tomorrow's Focus: {tomorrow_focus}"}}]
                        }
                    })
                
                if raw_transcript:
                    blocks.extend([
                        {
                            "object": "block",
                            "type": "heading_2",
                            "heading_2": {"rich_text": [{"type": "text", "text": {"content": "Raw Audio Transcript"}}]}
                        },
                        {
                            "object": "block",
                            "type": "paragraph",
                            "paragraph": {"rich_text": [{"type": "text", "text": {"content": raw_transcript}}]}
                        }
                    ])
                
                self.client.blocks.children.append(block_id=self.diary_db_id, children=blocks)
                logger.info("Successfully appended structured log to simple Notion diary page.")
                return "page_append_success"
            except Exception as e:
                logger.error(f"Notion API error appending blocks to simple page: {e}")
                return None

        # Database standard structure fallback
        try:
            children = [
                {
                    "object": "block",
                    "type": "heading_2",
                    "heading_2": {"rich_text": [{"text": {"content": "Summary"}}]}
                },
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {"rich_text": [{"text": {"content": summary}}]}
                },
                {
                    "object": "block",
                    "type": "heading_2",
                    "heading_2": {"rich_text": [{"text": {"content": "Key Decisions"}}]}
                },
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {"rich_text": [{"text": {"content": key_decisions}}]}
                },
                {
                    "object": "block",
                    "type": "heading_2",
                    "heading_2": {"rich_text": [{"text": {"content": "Suggested Focus for Tomorrow"}}]}
                },
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {"rich_text": [{"text": {"content": tomorrow_focus}}]}
                }
            ]
            
            # Look up for raw_transcript injection
            if raw_transcript:
                children.extend([
                    {
                        "object": "block",
                        "type": "heading_2",
                        "heading_2": {"rich_text": [{"text": {"content": "Raw Audio Transcript"}}]}
                    },
                    {
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {"rich_text": [{"text": {"content": raw_transcript}}]}
                    }
                ])
            
            new_page = self.client.pages.create(
                parent={"database_id": self.diary_db_id},
                properties={
                    "Date": {"title": [{"text": {"content": today_str}}]},
                    "Mood": {"select": {"name": mood}},
                    "Activities Logged": {"multi_select": [{"name": act} for act in activities]}
                },
                children=children
            )
            logger.info("Successfully wrote diary entry page to Notion diary DB.")
            return new_page.get("id")
        except Exception as e:
            logger.error(f"Notion API error writing diary entry to database: {e}")
            return None

    def create_task(self, title: str, deadline: str, category: str, target: str) -> Optional[str]:
        """
        Creates a checklist block inside a Notion Tasks Database OR a simple Page document.
        If offline, appends to the `/home/anish/Documents/Anish/Daily/Todo` local file.
        """
        today_str = datetime.now().strftime("%B %d, %Y")
        today_header_str = datetime.now().strftime("%B %d %Y")  # e.g., "May 26 2026"
        
        if not self.client or not self.tasks_db_id:
            logger.warning("Notion offline fallback. Simulating task creation.")
            todo_dir = str(PROJECT_ROOT / "local_data")
            os.makedirs(todo_dir, exist_ok=True)
            todo_file = os.path.join(todo_dir, "Todo")
            
            try:
                with open(todo_file, "a", encoding="utf-8") as f:
                    f.write(f"\n- [ ] {title} (Deadline: {deadline} | Category: {category} | Target: {target})")
                logger.info("Successfully appended simulated task card to local Daily/Todo file.")
                return "local_fallback_success"
            except Exception as e:
                logger.error(f"Failed to write task locally: {e}")
                return None

        # Auto-resolver: If NOT a database, treat it as Anish's requested simple checkbox page
        if not self.is_database_id(self.tasks_db_id):
            logger.info("Treating NOTION_TASKS_DB_ID as a simple Page ID. Appending checkbox blocks.")
            try:
                # 1. Fetch last few blocks on the page to see if today's date header already exists
                last_blocks = self.client.blocks.children.list(block_id=self.tasks_db_id, page_size=15)
                today_header_exists = False
                
                for block in reversed(last_blocks.get("results", [])):
                    block_type = block.get("type")
                    if block_type in ["heading_2", "heading_3"]:
                        text_list = block.get(block_type, {}).get("rich_text", [])
                        if text_list and today_header_str in text_list[0].get("text", {}).get("content", ""):
                            today_header_exists = True
                            break

                blocks_to_append = []
                if not today_header_exists:
                    # Append heading block for the new day
                    blocks_to_append.append({
                        "object": "block",
                        "type": "heading_2",
                        "heading_2": {
                            "rich_text": [{"type": "text", "text": {"content": today_header_str}}]
                        }
                    })

                # Append standard interactive to-do checkbox block
                blocks_to_append.append({
                    "object": "block",
                    "type": "to_do",
                    "to_do": {
                        "rich_text": [{"type": "text", "text": {"content": title}}],
                        "checked": False
                    }
                })

                self.client.blocks.children.append(block_id=self.tasks_db_id, children=blocks_to_append)
                logger.info("Successfully appended to-do block to simple Notion page.")
                return "page_append_success"
            except Exception as e:
                logger.error(f"Notion API error appending checkbox to simple page: {e}")
                return None

        # Database standard structure fallback
        try:
            new_page = self.client.pages.create(
                parent={"database_id": self.tasks_db_id},
                properties={
                    "Task Name": {"title": [{"text": {"content": title}}]},
                    "Deadline": {"date": {"start": deadline}} if deadline else None,
                    "Status": {"status": {"name": "Todo"}},
                    "Category": {"select": {"name": category}} if category else None,
                    "Daily Target": {"rich_text": [{"text": {"content": target}}]} if target else None
                }
            )
            logger.info(f"Successfully created task page in Notion DB: {title}")
            return new_page.get("id")
        except Exception as e:
            logger.error(f"Notion API error creating task in database: {e}")
            return None

    def update_task_status(self, task_name: str, new_status: str = "Done") -> bool:
        """
        Queries the Notion Tasks DB for a task matching the name and updates its status.
        """
        if not self.client or not self.tasks_db_id or not self.is_database_id(self.tasks_db_id):
            logger.warning("Cannot update task: Notion DB not available or offline.")
            return False
            
        try:
            res = self.client.databases.query(
                database_id=self.tasks_db_id,
                filter={
                    "property": "Task Name",
                    "title": {
                        "contains": task_name
                    }
                },
                page_size=1
            )
            
            results = res.get("results", [])
            if not results:
                logger.warning(f"Task '{task_name}' not found in Notion DB.")
                return False
                
            page_id = results[0]["id"]
            self.client.pages.update(
                page_id=page_id,
                properties={
                    "Status": {"status": {"name": new_status}}
                }
            )
            logger.info(f"Successfully updated task '{task_name}' to '{new_status}' in Notion.")
            return True
        except Exception as e:
            logger.error(f"Notion API error updating task '{task_name}': {e}")
            return False

    def update_brain_file(self, file_key: str, new_content: str) -> bool:
        """
        Overwrites a Notion sub-page with new content from the LLM.
        """
        if not self.client or not self.brain_page_id:
            logger.error("Notion client or brain page missing. Cannot update brain.")
            return False

        try:
            # 1. Find child page ID by partial title match
            blocks = self.client.blocks.children.list(block_id=self.brain_page_id).get("results", [])
            target_page_id = None
            for block in blocks:
                if block.get("type") == "child_page":
                    title = block["child_page"].get("title", "").lower()
                    if file_key == "master_profile" and ("profile" in title or "who" in title or "story" in title):
                        target_page_id = block["id"]
                        break
                    elif file_key == "current_goals" and ("goal" in title or "career" in title or "plan" in title):
                        target_page_id = block["id"]
                        break
                    elif file_key == "mental_patterns" and ("pattern" in title or "interaction" in title):
                        target_page_id = block["id"]
                        break
                    elif file_key == "people_in_my_life" and ("people" in title or "social" in title):
                        target_page_id = block["id"]
                        break

            if not target_page_id:
                logger.error(f"Could not find a Notion sub-page matching file_key: {file_key}")
                return False

            # 2. Delete all existing blocks inside that page
            page_blocks = self.client.blocks.children.list(block_id=target_page_id).get("results", [])
            for block in page_blocks:
                self.client.blocks.delete(block_id=block["id"])

            # 3. Append new content in chunks
            paragraphs = new_content.split("\n\n")
            children = []
            for p in paragraphs:
                p = p.strip()
                if not p: continue
                # Chunk into 2000 char pieces (Notion API limits text objects to 2000 chars)
                for i in range(0, len(p), 2000):
                    chunk = p[i:i+2000]
                    children.append({
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [{"type": "text", "text": {"content": chunk}}]
                        }
                    })

            # Append all blocks at once (max 100 children per request)
            for i in range(0, len(children), 100):
                self.client.blocks.children.append(
                    block_id=target_page_id,
                    children=children[i:i+100]
                )

            logger.info(f"Successfully updated Notion brain page for {file_key}")
            return True
        except Exception as e:
            logger.error(f"Notion API error updating brain file {file_key}: {e}")
            return False

    # ── read/write helpers for the dashboard diary/to-do panels ───────────────
    # notion-client 3.x dropped databases.query (new API uses data sources), and
    # its pages.create fails validation against these DBs. The rest of the app
    # already uses raw REST with Notion-Version 2022-06-28, which works — so do
    # the same here for consistency.
    def _http(self):
        import httpx
        headers = {
            "Authorization": f"Bearer {self.notion_token}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        }
        return httpx, headers

    def _query_db(self, db_id: str, payload: dict) -> list:
        httpx, headers = self._http()
        r = httpx.post(f"https://api.notion.com/v1/databases/{db_id}/query",
                       headers=headers, json=payload, timeout=15)
        r.raise_for_status()
        return r.json().get("results", [])

    def list_tasks(self, limit: int = 50) -> List[dict]:
        """List tasks from the Notion Tasks DB (title, status, category, page id)."""
        if not self.client or not self.tasks_db_id or not self.is_database_id(self.tasks_db_id):
            return []
        try:
            results = self._query_db(self.tasks_db_id, {"page_size": limit})
            out = []
            for p in results:
                props = p.get("properties", {})
                title = "Untitled"
                for field in ("Task Name", "Name", "Task", "Title"):
                    tp = props.get(field, {}).get("title")
                    if tp:
                        title = tp[0].get("plain_text", "Untitled")
                        break
                status = "Todo"
                if props.get("Status", {}).get("status"):
                    status = props["Status"]["status"]["name"]
                category = None
                if props.get("Category", {}).get("select"):
                    category = props["Category"]["select"]["name"]
                deadline = None
                for df in ("Deadline", "Due", "Date", "Due Date"):
                    if props.get(df, {}).get("date"):
                        deadline = props[df]["date"].get("start")
                        if deadline:
                            deadline = deadline[:10]
                        break
                out.append({
                    "id": p["id"], "title": title, "status": status,
                    "category": category, "deadline": deadline,
                    "done": status.lower() in ("done", "completed"),
                })
            # open tasks first
            out.sort(key=lambda t: t["done"])
            return out
        except Exception as e:
            logger.error(f"Notion list_tasks error: {e}")
            return []

    def create_task_http(self, title: str, category: str = "",
                         due_date: Optional[str] = None) -> Optional[str]:
        """Create a task page via REST (2022-06-28). Returns the new page id.
        due_date is ISO 'YYYY-MM-DD' and sets the Deadline property."""
        if not self.client or not self.tasks_db_id or not self.is_database_id(self.tasks_db_id):
            return None
        httpx, headers = self._http()
        # Don't set Status on create — option names vary per DB (e.g. "Not started"),
        # and "Todo" often doesn't exist. Let Notion assign the default status.
        props = {
            "Task Name": {"title": [{"text": {"content": title}}]},
        }
        if category:
            props["Category"] = {"select": {"name": category}}
        if due_date:
            props["Deadline"] = {"date": {"start": due_date}}

        def _post(p):
            return httpx.post("https://api.notion.com/v1/pages", headers=headers,
                              json={"parent": {"database_id": self.tasks_db_id}, "properties": p}, timeout=15)
        try:
            r = _post(props)
            if r.status_code != 200 and due_date:
                # 'Deadline' property may not exist — retry without it.
                props.pop("Deadline", None)
                r = _post(props)
            r.raise_for_status()
            return r.json().get("id")
        except Exception as e:
            logger.error(f"Notion create_task_http error: {e}")
            return None

    def set_task_done(self, page_id: str, done: bool = True) -> bool:
        httpx, headers = self._http()
        # "Not started" is Notion's default To-do option; "Done" is the default
        # Complete option. Try that, then fall back to other common names.
        candidates = ["Done"] if done else ["Not started", "To Do", "Todo"]
        for name in candidates:
            try:
                r = httpx.patch(f"https://api.notion.com/v1/pages/{page_id}", headers=headers,
                                json={"properties": {"Status": {"status": {"name": name}}}}, timeout=15)
                if r.status_code == 200:
                    return True
            except Exception as e:
                logger.error(f"Notion set_task_done error: {e}")
                return False
        logger.error("Notion set_task_done: no matching status option found")
        return False

    def archive_task(self, page_id: str) -> bool:
        httpx, headers = self._http()
        try:
            r = httpx.patch(f"https://api.notion.com/v1/pages/{page_id}", headers=headers,
                            json={"archived": True}, timeout=15)
            r.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Notion archive_task error: {e}")
            return False

    def create_diary_http(self, summary: str, mood: str = "Stable",
                          activities: Optional[List[str]] = None,
                          date: Optional[str] = None) -> Optional[str]:
        """Create a diary page via REST. Stores summary as a 'Summary' rich_text
        property so it lists cleanly, plus in the page body. `date` is ISO."""
        if not self.client or not self.diary_db_id or not self.is_database_id(self.diary_db_id):
            return None
        httpx, headers = self._http()
        if date:
            try:
                title_date = datetime.strptime(date, "%Y-%m-%d").strftime("%B %d, %Y")
            except ValueError:
                title_date = datetime.now().strftime("%B %d, %Y")
        else:
            title_date = datetime.now().strftime("%B %d, %Y")
        acts = activities or []
        props = {
            "Date": {"title": [{"text": {"content": title_date}}]},
            "Summary": {"rich_text": [{"text": {"content": summary[:1990]}}]},
        }
        if mood:
            props["Mood"] = {"select": {"name": mood}}
        if acts:
            props["Activities Logged"] = {"multi_select": [{"name": a} for a in acts]}
        body = {
            "parent": {"database_id": self.diary_db_id},
            "properties": props,
            "children": [{"object": "block", "type": "paragraph",
                          "paragraph": {"rich_text": [{"text": {"content": summary}}]}}],
        }
        try:
            r = httpx.post("https://api.notion.com/v1/pages", headers=headers, json=body, timeout=15)
            r.raise_for_status()
            return r.json().get("id")
        except Exception as e:
            # 'Summary' property may not exist on the user's DB — retry without it.
            logger.warning(f"Notion create_diary_http (with Summary) failed: {e}; retrying minimal.")
            props.pop("Summary", None)
            body["properties"] = props
            try:
                r = httpx.post("https://api.notion.com/v1/pages", headers=headers, json=body, timeout=15)
                r.raise_for_status()
                return r.json().get("id")
            except Exception as e2:
                logger.error(f"Notion create_diary_http error: {e2}")
                return None

    def list_diary(self, limit: int = 60) -> List[dict]:
        """List recent diary entries. Summary comes from the Summary/Entry/Notes
        property, falling back to the first paragraph block of the page body."""
        if not self.client or not self.diary_db_id or not self.is_database_id(self.diary_db_id):
            return []
        try:
            results = self._query_db(self.diary_db_id, {
                "page_size": limit,
                "sorts": [{"timestamp": "created_time", "direction": "descending"}],
            })
            httpx, headers = self._http()
            out = []
            for p in results:
                props = p.get("properties", {})
                created = p.get("created_time", "")[:10]
                date = created
                dprop = props.get("Date", {})
                if dprop.get("title"):
                    date = dprop["title"][0].get("plain_text", date) if dprop["title"] else date
                elif dprop.get("date"):
                    date = dprop["date"].get("start", date)
                date = _to_iso(date, created)
                mood = None
                for mf in ("Mood", "Mood Signal"):
                    if props.get(mf, {}).get("select"):
                        mood = props[mf]["select"]["name"]
                        break
                acts = []
                for af in ("Activities Logged", "Activities"):
                    if props.get(af, {}).get("multi_select"):
                        acts = [a["name"] for a in props[af]["multi_select"]]
                        break
                summary = ""
                for sf in ("Summary", "Entry", "Notes"):
                    rt = props.get(sf, {}).get("rich_text")
                    if rt:
                        summary = rt[0].get("plain_text", "")
                        break
                if not summary:
                    try:
                        br = httpx.get(f"https://api.notion.com/v1/blocks/{p['id']}/children?page_size=5",
                                       headers=headers, timeout=10)
                        for b in br.json().get("results", []):
                            if b.get("type") == "paragraph":
                                txt = "".join(r.get("plain_text", "") for r in b["paragraph"].get("rich_text", []))
                                if txt:
                                    summary = txt
                                    break
                    except Exception:
                        pass
                out.append({"date": date, "mood": mood, "summary": summary, "activities": acts})
            return out
        except Exception as e:
            logger.error(f"Notion list_diary error: {e}")
            return []

# Global single instance
notion_writer = NotionWriter()
