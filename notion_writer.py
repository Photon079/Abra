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
        self.client = None

        if self.notion_token:
            try:
                self.client = Client(auth=self.notion_token)
                logger.info("Notion Client initialized inside NotionWriter.")
            except Exception as e:
                logger.error(f"Failed to initialize Notion Client inside NotionWriter: {e}")
        else:
            logger.warning("No Notion API configurations provided. Operating in local write-back simulation.")

    def is_database_id(self, target_id: str) -> bool:
        """
        Helper to check whether a given Notion ID belongs to a Database or a simple Page.
        """
        if not self.client or not target_id:
            return False
        try:
            self.client.databases.retrieve(database_id=target_id)
            return True
        except Exception:
            return False

    def write_diary(self, summary: str, mood: str, activities: List[str], key_decisions: str, tomorrow_focus: str) -> Optional[str]:
        """
        Appends a diary entry to a Notion Diary Database OR a simple Page block stream.
        If offline, falls back to logging locally in `/home/anish/Documents/Anish/Daily/Diary`.
        """
        today_str = datetime.now().strftime("%B %d, %Y")
        
        if not self.client or not self.diary_db_id:
            logger.warning("Notion offline fallback. Simulating diary write.")
            diary_dir = "/home/anish/Documents/Anish/Daily"
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
                
                self.client.blocks.children.append(block_id=self.diary_db_id, children=blocks)
                logger.info("Successfully appended structured log to simple Notion diary page.")
                return "page_append_success"
            except Exception as e:
                logger.error(f"Notion API error appending blocks to simple page: {e}")
                return None

        # Database standard structure fallback
        try:
            new_page = self.client.pages.create(
                parent={"database_id": self.diary_db_id},
                properties={
                    "Date": {"title": [{"text": {"content": today_str}}]},
                    "Mood": {"select": {"name": mood}},
                    "Activities Logged": {"multi_select": [{"name": act} for act in activities]}
                },
                children=[
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
            todo_dir = "/home/anish/Documents/Anish/Daily"
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

# Global single instance
notion_writer = NotionWriter()
