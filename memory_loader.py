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

    def load_brain_files(self) -> Dict[str, str]:
        """
        Loads user background files from Notion or falls back to local markdown files
        located in '/home/anish/Documents/Anish/files/' to build the live agent memory.
        """
        context = {
            "master_profile": "No profile details loaded.",
            "current_goals": "No goals details loaded.",
            "mental_patterns": "No patterns details loaded.",
            "people_in_my_life": "Srinidhi Shetty (Best Friend since Class 8), Sinchana (College Friend), Vedanth (Hometown Friend), Ajay (Project Collaborator), Darshini (Distant Friend).",
            "system_prompt": "You are ABRA — Anish's Personal Life OS. Speak normally, directly, and without fluff."
        }

        # 1. Attempt Local Files Load (highly reliable sandbox fallback)
        local_dir = "/home/anish/Documents/Anish/files"
        local_mappings = {
            "master_profile": "master_profile_anish_2026.md",
            "current_goals": "career_plan.md",
            "mental_patterns": "patterns_for_ai_interaction.md"
        }

        loaded_locally = False
        if os.path.exists(local_dir):
            try:
                for key, filename in local_mappings.items():
                    filepath = os.path.join(local_dir, filename)
                    if os.path.exists(filepath):
                        with open(filepath, 'r', encoding='utf-8') as f:
                            context[key] = f.read()
                loaded_locally = True
                logger.info("Successfully populated brain files from local documents path.")
            except Exception as e:
                logger.error(f"Error loading from local documents path: {e}")

        # 2. Attempt Notion API (if token and parent page are present)
        if self.client and self.brain_page_id and not loaded_locally:
            try:
                # We query sub-pages under the parent brain page ID
                blocks = self.client.blocks.children.list(block_id=self.brain_page_id)
                extracted_text = []
                for block in blocks.get("results", []):
                    block_type = block.get("type")
                    if block_type and isinstance(block.get(block_type), dict):
                        rich_texts = block[block_type].get("rich_text", [])
                        text = "".join([rt.get("plain_text", "") for rt in rich_texts])
                        if text:
                            extracted_text.append(text)
                
                if extracted_text:
                    context["master_profile"] = "\n".join(extracted_text)
                logger.info("Successfully fetched brain details from Notion workspace.")
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
"""
        return prompt

# Global single instance
memory_loader = MemoryLoader()
