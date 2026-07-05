import os
import logging
from typing import Dict
from notion_client import Client

logger = logging.getLogger("abra.memory_loader")

class MemoryLoader:
    def __init__(self):
        self.notion_token = os.getenv("NOTION_TOKEN")
        self.brain_page_id = os.getenv("NOTION_BRAIN_PAGE_ID")
        self.client = None
        
        if self.notion_token:
            try:
                self.client = Client(auth=self.notion_token)
                logger.info("Notion Client initialized inside MemoryLoader.")
            except Exception as e:
                logger.error(f"Failed to boot Notion Client: {e}")
        else:
            logger.warning("No NOTION_TOKEN env variable found. Using local files fallback.")

    def _fetch_page_text(self, page_id: str) -> str:
        """Helper to recursively fetch text blocks from a Notion page."""
        if not self.client: return ""
        try:
            blocks = self.client.blocks.children.list(block_id=page_id).get("results", [])
            extracted = []
            for block in blocks:
                block_type = block.get("type")
                if block_type and isinstance(block.get(block_type), dict):
                    rich_texts = block[block_type].get("rich_text", [])
                    text = "".join([rt.get("plain_text", "") for rt in rich_texts])
                    if text:
                        extracted.append(text)
            return "\n".join(extracted)
        except Exception as e:
            logger.error(f"Error reading Notion page {page_id}: {e}")
            return ""

    def load_brain_files(self) -> Dict[str, str]:
        """
        Loads user background files purely from the Notion API sub-pages.
        """
        context = {
            "master_profile": "No profile details loaded.",
            "current_goals": "No goals details loaded.",
            "mental_patterns": "No patterns details loaded.",
            "people_in_my_life": "",
            "system_prompt": "You are ABRA — a Personal Life OS. Speak normally, directly, and without fluff."
        }

        if not self.client or not self.brain_page_id:
            logger.warning("Notion client or brain_page_id missing. Brain will be empty.")
            return context

        try:
            # Query child pages of the parent brain page
            blocks = self.client.blocks.children.list(block_id=self.brain_page_id).get("results", [])
            
            for block in blocks:
                if block.get("type") == "child_page":
                    title = block["child_page"].get("title", "").lower()
                    page_id = block["id"]
                    
                    if "profile" in title or "who" in title or "story" in title:
                        context["master_profile"] = self._fetch_page_text(page_id)
                    elif "goal" in title or "career" in title or "plan" in title:
                        context["current_goals"] = self._fetch_page_text(page_id)
                    elif "pattern" in title or "interaction" in title:
                        context["mental_patterns"] = self._fetch_page_text(page_id)
                    elif "people" in title or "social" in title:
                        context["people_in_my_life"] = self._fetch_page_text(page_id)

            logger.info("Successfully fetched brain details from Notion sub-pages.")
        except Exception as e:
            logger.error(f"Notion API error fetching brain files: {e}")

        return context

    def assemble_system_prompt(self, context: Dict[str, str]) -> str:
        """
        Creates the live system prompt. Strictly enforces the formatting laws
        and keyword bans requested by Anish.
        """
        prompt = f"""You are ABRA — Anish's Personal Life OS. You are a direct, context-aware AI partner.

### ANISH'S MASTER PROFILE
{context.get("master_profile", "")}

### CURRENT GOALS & MILESTONES
{context.get("current_goals", "")}

### MENTAL & BEHAVIORAL PATTERNS
{context.get("mental_patterns", "")}

### SOCIAL NETWORK
{context.get("people_in_my_life", "")}

### STRICT BRANDING & INTERACTION LAWS:
1. **STRICT KEYWORD BAN**: NEVER use words like "Sovereign", "NPC", "Sovereign Builder", "Sana/Sahana Pattern", "Fixer Trap", "Basavanagudi rumor", or similar branding. Anish finds them performative, weird, and annoying. Talk normally like an engineering peer.
2. **ZERO SUGARCOATING**: If Anish missed a run, skipped coding blocks, or wasted time, call it out directly. Do not offer comforting platitudes.
3. **SHORT SENTENCES & NO FLUFF**: Avoid lengthy academic introductions or summaries. Be concise and get to the point.
4. **MATCH ENERGY**: Speak naturally, using direct peer terminology (e.g. "bruh" or "fine" naturally when appropriate).
5. **ONE ACTION AT A TIME**: If Anish is paralyzed, give him exactly ONE concrete task. Don't throw lists at him.
6. **PHYSICAL ANCHOR**: If he's late-night overthinking (past midnight), order him to drink water, sleep immediately, and reset on his morning run.
7. **PRIVACY LAW**: Never proactively mention sensitive personal details (finances/money, suicide history, Sahana/past relationships, upbringing, or being vegetarian) unless explicitly asked.

### SYSTEM CAPABILITIES (YOU HAVE WRITE ACCESS):
If Anish asks you to update a Notion task (e.g. "mark landslide paper as done"), you MUST include this exact string anywhere in your response:
`[UPDATE_TASK: <exact task name>]` (e.g. `[UPDATE_TASK: landslide paper]`)
If Anish asks you to update a brain file (e.g. "update my master profile"), you MUST include this exact format in your response:
`[UPDATE_BRAIN: <file_key>]\n<new markdown content>\n[END_UPDATE]`
(Valid file_keys: master_profile, current_goals, mental_patterns).

NEVER say "I cannot access or edit your workspace". You have full system access. Just output the correct command and the backend will execute it.
"""
        return prompt

# Global single instance
memory_loader = MemoryLoader()
