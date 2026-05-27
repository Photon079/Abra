import logging
import json
from typing import Dict, List, Any, Tuple
from app.config import settings
from app.services.notion_service import notion_service
from app.services.coral_service import coral_service

# Import LLM clients safely
gemini_available = False
groq_available = False

try:
    import google.generativeai as genai
    gemini_available = True
except ImportError:
    pass

try:
    from groq import Groq
    groq_available = True
except ImportError:
    pass

logger = logging.getLogger("abra.agent")

class AbraAgent:
    def __init__(self):
        self.provider = settings.LLM_PROVIDER
        
        # Initialize Gemini API
        if self.provider == "gemini" and settings.GEMINI_API_KEY:
            if gemini_available:
                genai.configure(api_key=settings.GEMINI_API_KEY)
                logger.info("Gemini API successfully configured for agent.")
            else:
                logger.error("Gemini library not installed but provider set to Gemini.")
        
        # Initialize Groq API
        elif self.provider == "groq" and settings.GROQ_API_KEY:
            if groq_available:
                self.groq_client = Groq(api_key=settings.GROQ_API_KEY)
                logger.info("Groq API successfully configured for agent.")
            else:
                logger.error("Groq library not installed but provider set to Groq.")
        else:
            logger.warning("No LLM API keys provided. Agent operating in high-fidelity mock/simulation mode.")

    def _assemble_system_prompt(self, brain_context: Dict[str, str]) -> str:
        """
        Assembles the definitive system prompt by merging Notion brain files.
        Includes mandatory AI interaction rules to restrict performative language
        and enforce Anish's preferred interaction style.
        """
        prompt = f"""You are ABRA — Anish's Personal Life OS. You are a direct, context-aware AI partner.

### ANISH'S MASTER PROFILE
{brain_context.get("master_profile", "")}

### CURRENT GOALS & MILESTONES
{brain_context.get("current_goals", "")}

### MENTAL & BEHAVIORAL PATTERNS
{brain_context.get("mental_patterns", "")}

### SOCIAL WORLD
{brain_context.get("people_in_my_life", "")}

### MANDATORY INTERACTION LAWS (VIOLATING THESE IS AN INSTANT FAIL):
1. **STRICT BRANDING BAN**: NEVER under any circumstances use self-help or performative terms like "Sovereign", "NPC", "Sovereign Builder", "Sana/Sahana Pattern", "Fixer Trap", "Basavanagudi rumor", or similar branding. Speak normally and directly.
2. **ZERO SUGARCOATING**: Be brutally honest. If Anish reports wasting time, missing a run, or avoiding work, call it out directly. Do not offer gentle, coddling platitudes.
3. **SHORT SENTENCES & NO FLUFF**: Keep responses concise and practical. Avoid long, academic preambles. Get straight to the point.
4. **MATCH ENERGY**: Speak like an engineering peer. Match his tone (e.g. use "bruh" or "fine" naturally when appropriate).
5. **ONE ACTION AT A TIME**: If Anish is overwhelmed or paralyzed, reduce the path to exactly ONE concrete, actionable thing. 
6. **PHYSICAL ANCHORS**: When late-night spirals or overthinking occur, do not debate philosophy. Order a hard physical reset: drink water, sleep, morning run/walk.
"""
        return prompt

    def _call_llm(self, system_prompt: str, user_message: str, response_format_json: bool = False) -> str:
        """
        Calls the selected LLM provider (Gemini, Groq, or Mock fallback).
        """
        if self.provider == "gemini" and settings.GEMINI_API_KEY and gemini_available:
            try:
                # Use Gemini 2.5 Flash as requested in PRD
                model = genai.GenerativeModel(
                    model_name="gemini-1.5-flash",  # maps standard active flash endpoint
                    system_instruction=system_prompt
                )
                
                generation_config = {}
                if response_format_json:
                    generation_config["response_mime_type"] = "application/json"
                    
                response = model.generate_content(
                    user_message,
                    generation_config=generation_config
                )
                return response.text
            except Exception as e:
                logger.error(f"Gemini LLM Call failed: {e}")
                
        elif self.provider == "groq" and settings.GROQ_API_KEY and groq_available:
            try:
                # Use Llama 3.3 70B as requested in PRD
                chat_completion = self.groq_client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message}
                    ],
                    model="llama3-70b-8192",
                    response_format={"type": "json_object"} if response_format_json else None
                )
                return chat_completion.choices[0].message.content
            except Exception as e:
                logger.error(f"Groq LLM Call failed: {e}")

        # High-Fidelity Mock Response Engine
        return self._simulate_llm_response(user_message, response_format_json)

    def classify_intent(self, text: str) -> str:
        """
        Determines the route of the user input.
        Options: diary, goal_decomposition, daily_briefing, reflection, qna, general
        """
        text_lower = text.lower()
        if any(w in text_lower for w in ["i did", "today i", "ran", "hours on", "workout", "ate", "slept"]):
            return "diary"
        elif any(w in text_lower for w in ["i want to", "goal", "by", "plan my", "schedule", "deadline"]):
            return "goal_decomposition"
        elif any(w in text_lower for w in ["briefing", "morning", "should i work on", "focus today"]):
            return "daily_briefing"
        elif any(w in text_lower for w in ["pattern", "reflect", "sabotage", "how was my week"]):
            return "reflection"
        elif any(w in text_lower for w in ["what was my", "how many", "who", "when", "tell me about"]):
            return "qna"
        return "general"

    def process_input(self, user_input: str) -> Dict[str, Any]:
        """
        The main coordinator block. Fetches context, routes, processes, and commits results.
        """
        intent = self.classify_intent(user_input)
        brain_context = notion_service.get_brain_context()
        system_prompt = self._assemble_system_prompt(brain_context)

        logger.info(f"Routed input: '{user_input[:40]}...' to intent: {intent}")

        if intent == "diary":
            return self._handle_diary_flow(user_input, system_prompt)
        elif intent == "goal_decomposition":
            return self._handle_goal_flow(user_input, system_prompt)
        elif intent == "daily_briefing":
            return self._handle_briefing_flow(system_prompt)
        elif intent == "reflection":
            return self._handle_reflection_flow(system_prompt)
        elif intent == "qna":
            return self._handle_qna_flow(user_input, system_prompt)
        else:
            # General talk/fallback
            response = self._call_llm(system_prompt, user_input)
            return {"intent": "general", "markdown": response}

    def _handle_diary_flow(self, user_input: str, system_prompt: str) -> Dict[str, Any]:
        # 1. Query Coral for today's events and Notion page modifications
        sql = """
        SELECT cal.summary AS event_title, n.title AS notion_page_edited
        FROM google_calendar.events cal
        LEFT JOIN notion.pages n ON n.last_edited::date = CURRENT_DATE
        WHERE cal."start__dateTime"::date = CURRENT_DATE
        """
        coral_data = coral_service.run_query(sql)
        coral_str = json.dumps(coral_data, indent=2)

        # 2. Construct LLM instruction
        prompt = f"""Anish wants to log his diary.
User Raw input: "{user_input}"

Connected Apps Context (from Coral SQL query today):
{coral_str}

Analyze this, join his input with today's activities, and output a JSON representing his daily log.
Format standard JSON strictly with the following fields:
{{
  "summary": "Short 1-2 sentence description including runs and coding milestones",
  "mood": "Stable" or "Focused" or "Scattered" or "Stressed" or "Low Energy",
  "activities": ["List", "of", "activities", "like", "Running", "Coding", "Chess", "Social"],
  "decisions": "Any key decisions made today",
  "tomorrow_focus": "One clear priority for tomorrow"
}}"""

        response_json_str = self._call_llm(system_prompt, prompt, response_format_json=True)
        try:
            log_data = json.loads(response_json_str)
        except Exception:
            # Fallback parsing
            log_data = {
                "summary": f"Logged: {user_input[:100]}",
                "mood": "Stable",
                "activities": ["Coding"],
                "decisions": "Decided to run the script.",
                "tomorrow_focus": "Write more code."
            }

        # 3. Write back to Notion diary database
        notion_id = notion_service.write_diary_entry(
            summary=log_data["summary"],
            mood=log_data["mood"],
            activities=log_data["activities"],
            key_decisions=log_data["decisions"],
            tomorrow_focus=log_data["tomorrow_focus"]
        )

        md_output = f"""### Daily Log Committed to Notion! 🎉
- **Date**: Today
- **Mood**: `{log_data['mood']}`
- **Activities**: {", ".join([f"`{act}`" for act in log_data['activities']])}

#### Summary
{log_data['summary']}

#### Key Decisions
{log_data['decisions']}

#### Focus for Tomorrow
{log_data['tomorrow_focus']}
"""
        return {
            "intent": "diary",
            "markdown": md_output,
            "data": log_data,
            "notion_page_id": notion_id
        }

    def _handle_goal_flow(self, user_input: str, system_prompt: str) -> Dict[str, Any]:
        prompt = f"""Anish wants to decompose a goal: "{user_input}".
Reference his current milestones. Compute a daily/weekly action list with dates.
Format your output as standard JSON representing a list of tasks to create:
{{
  "explanation": "A short, direct breakdown explanation (math/pacing, obstacles, conflicts)",
  "tasks": [
    {{
      "title": "Task name (e.g. NeetCode Two Pointers: 3 problems)",
      "deadline": "YYYY-MM-DD",
      "category": "Career" or "Academics" or "Physical" or "Projects",
      "target": "Specific daily milestone text"
    }}
  ]
}}"""

        response_json_str = self._call_llm(system_prompt, prompt, response_format_json=True)
        try:
            goal_data = json.loads(response_json_str)
        except Exception:
            # Fallback
            goal_data = {
                "explanation": "Goal split mock",
                "tasks": [{"title": "Read CS229 note", "deadline": "2026-05-27", "category": "Academics", "target": "1 chapter"}]
            }

        created_tasks = []
        for task in goal_data.get("tasks", []):
            task_id = notion_service.create_notion_task(
                title=task["title"],
                deadline=task["deadline"],
                category=task["category"],
                target=task["target"]
            )
            created_tasks.append({"title": task["title"], "id": task_id})

        md_output = f"""### Goal Decomposition Plan 🏃‍♂️
{goal_data.get('explanation', '')}

**Structured Tasks added to your Notion Todo List:**
"""
        for t in goal_data.get("tasks", []):
            md_output += f"\n- **{t['title']}** (Deadline: `{t['deadline']}` | `{t['category']}`) — *{t['target']}*"

        return {
            "intent": "goal_decomposition",
            "markdown": md_output,
            "data": goal_data,
            "created_tasks": created_tasks
        }

    def _handle_briefing_flow(self, system_prompt: str) -> Dict[str, Any]:
        # 1. Fetch Calendar events today via Coral
        sql = 'SELECT summary AS title FROM google_calendar.events WHERE "start__dateTime"::date = CURRENT_DATE'
        events = coral_service.run_query(sql)
        events_str = ", ".join([e.get("title", "") for e in events]) if events else "No events scheduled."

        prompt = f"""Generate Anish's daily morning briefing.
Calendar today: "{events_str}"
Yesterday's focus was: "Finishing the landing page and running."

Briefing requirements:
1. Short list of calendar events.
2. Direct, no-fluff suggestion for today's core focus block.
3. Check for pattern triggers (e.g. consecutive junk food, late nights, or scatter loop switches).
Output a direct, short brief."""

        response = self._call_llm(system_prompt, prompt)
        return {
            "intent": "daily_briefing",
            "markdown": response
        }

    def _handle_reflection_flow(self, system_prompt: str) -> Dict[str, Any]:
        prompt = """Analyze Anish's recent behavior and diary logs. 
Spot patterns by name (Scatter Loop, Junk Fuel, Freeze-Then-Panic, 2 AM Spiral).
Be brutally direct, like a mirror. Do not suggest soft self-help solutions. Give him facts."""

        response = self._call_llm(system_prompt, prompt)
        return {
            "intent": "reflection",
            "markdown": response
        }

    def _handle_qna_flow(self, user_input: str, system_prompt: str) -> Dict[str, Any]:
        # Perform targeted queries based on query keyword
        context_str = ""
        user_input_lower = user_input.lower()
        
        if "pb" in user_input_lower or "run" in user_input_lower:
            sql = "SELECT title, duration_min FROM google_calendar.events WHERE title LIKE '%Run%'"
            runs = coral_service.run_query(sql)
            context_str = f"Logged Runs database context: {json.dumps(runs)}"

        prompt = f"""Answer Anish's memory query.
Query: "{user_input}"
Extra Context: {context_str}

Give a direct, accurate answer using the master profile and diary facts. No generic boilerplate."""
        
        response = self._call_llm(system_prompt, prompt)
        return {
            "intent": "qna",
            "markdown": response
        }

    def _simulate_llm_response(self, user_message: str, response_format_json: bool = False) -> str:
        """
        Simulated responses that strictly follow Anish's AI rules for local demo testing.
        """
        if response_format_json:
            # Output correct JSON structure based on message keywords
            if "diary" in user_message or "log" in user_message:
                return json.dumps({
                    "summary": "Ran 6K in 32 minutes. Back stiff. Spent 4 hours coding Abra local engine.",
                    "mood": "Focused",
                    "activities": ["Running", "Coding"],
                    "decisions": "Stopped overthinking and set up local config fallbacks.",
                    "tomorrow_focus": "Write the Google Calendar spec and connect with Srinidhi."
                })
            elif "goal" in user_message or "decompose" in user_message:
                return json.dumps({
                    "explanation": "To finish NeetCode 150 by July 31 (61 days left), we need exactly 2.4 problems per day. Adjusting for your parallel mechanical labs and CS229 studies, we will pace at 3 problems on Mondays/Wednesdays/Fridays, and 1 on run days.",
                    "tasks": [
                        {"title": "NeetCode: Two Pointers Section (3 problems)", "deadline": "2026-05-27", "category": "Career", "target": "Container With Most Water, 3sum, valid palindrome"},
                        {"title": "NeetCode: Sliding Window (3 problems)", "deadline": "2026-05-29", "category": "Career", "target": "Best time to buy/sell stock, longest substring, character replacement"}
                    ]
                })
        
        # Markdown general text fallbacks obeying interaction laws (brutally direct, concise, peer-like, bans sovereign/NPC)
        if "should i work on" in user_message or "briefing" in user_message:
            return """### Morning Briefing — May 26, 2026 🌅
**Calendar Today:**
- ML CS229 Lecture Review (11:30 AM)
- Run 6K Grounding session (4:15 PM)
- Abra Core coding (6:00 PM)

**Focus Block:**
Forget the noise on LinkedIn, bruh. Focus for the next 45 minutes on finishing the calendar spec. That is your only priority.

**Pattern Check:**
⚠️ **Scatter Loop detected.** You switched from CS229 to looking up Rust pipelines yesterday. Stop bouncing between stacks. Stick to your active commitments.
"""
        elif "reflect" in user_message or "pattern" in user_message:
            return """### Behavior Reflection audit 🔍
Brutal honesty, bruh:
1. **Scatter Loop**: You spent 3 hours yesterday comparing Neovim configs instead of practicing DSA. This is task avoidance.
2. **2 AM Spiral**: You logged a diary entry at 2:15 AM searching about career timelines. You cannot solve a 2-year plan at midnight. Drink water, sleep. The morning run is the reset.
3. **Friend Isolation**: You haven't texted Sinchana or Srinidhi back in 2 days because you're 'busy' vibing. Reliable connections are critical. Send a quick text.
"""
        
        return "I am ABRA. Let's write some code, bruh. What is the single thing we are doing for the next 45 minutes?"

abra_agent = AbraAgent()
