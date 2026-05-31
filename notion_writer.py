import os
import logging
from typing import List, Optional
from datetime import datetime
from notion_client import Client

logger = logging.getLogger("abra.notion_writer")

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
            diary_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "local_data")
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
            todo_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "local_data")
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

# Global single instance
notion_writer = NotionWriter()
