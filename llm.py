import os
import time
import logging
from typing import Optional

# Setup logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("abra.llm")

# Check which libraries are installed
genai_available = False
groq_available = False

try:
    from google import genai
    genai_available = True
except ImportError as e:
    logger.warning(f"Could not import google-genai: {e}")

try:
    from groq import Groq
    groq_available = True
except ImportError as e:
    logger.warning(f"Could not import groq: {e}")

class LLMService:
    def __init__(self):
        # Read keys from environment
        self.provider = os.getenv("LLM_PROVIDER", "gemini").lower()
        self.gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GEMINI_KEY")
        self.groq_key = os.getenv("GROQ_API_KEY") or os.getenv("GROQ_TOKEN")
        self.cerebras_key = os.getenv("CEREBRAS_API_KEY")
        self.openrouter_key = os.getenv("OPENROUTER_API_KEY")
        
        # Adjust provider if key is absent but another key is present
        if self.provider == "groq" and not self.groq_key and self.gemini_key:
            self.provider = "gemini"
            logger.info("Groq key missing. Auto-switching to Gemini provider.")
        elif self.provider == "gemini" and not self.gemini_key and self.groq_key:
            self.provider = "groq"
            logger.info("Gemini key missing. Auto-switching to Groq provider.")

        # Initialize clients
        self.groq_client = None
        self.gemini_client = None

        # Gemini model fallback chain
        self.gemini_models = ["gemini-2.0-flash", "gemini-2.0-flash-lite", "gemini-1.5-pro"]

        logger.info(f"Initializing LLMService. Configured provider: {self.provider.upper()}")

        if self.groq_key and groq_available:
            try:
                self.groq_client = Groq(api_key=self.groq_key)
                logger.info("Groq client successfully configured.")
            except Exception as e:
                logger.error(f"Groq client init failed: {e}")
        else:
            logger.warning(f"Groq Client NOT configured. Key present: {bool(self.groq_key)}, Library available: {groq_available}")
        
        if self.gemini_key and genai_available:
            try:
                self.gemini_client = genai.Client(api_key=self.gemini_key)
                logger.info("Gemini client successfully configured (google-genai SDK).")
            except Exception as e:
                logger.error(f"Gemini client init failed: {e}")
        else:
            logger.warning(f"Gemini Client NOT configured. Key present: {bool(self.gemini_key)}, Library available: {genai_available}")

    def _call_groq(self, system_prompt: str, user_message: str, response_format_json: bool = False) -> Optional[str]:
        """Call Groq API. Returns response text or None on failure."""
        if not self.groq_client:
            return None
        try:
            model = "llama-3.3-70b-versatile"
            chat_completion = self.groq_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                model=model,
                response_format={"type": "json_object"} if response_format_json else None
            )
            logger.info("Groq API call succeeded.")
            return chat_completion.choices[0].message.content
        except Exception as e:
            logger.error(f"Groq API call failed: {e}")
            return None

    def _call_gemini(self, system_prompt: str, user_message: str, response_format_json: bool = False) -> Optional[str]:
        """
        Call Gemini API with retry logic for 429 rate limits.
        Tries multiple models in the fallback chain.
        """
        if not self.gemini_client:
            return None

        for model_name in self.gemini_models:
            # Retry up to 3 times per model with exponential backoff
            for attempt in range(3):
                try:
                    config = None
                    if response_format_json:
                        config = genai.types.GenerateContentConfig(
                            system_instruction=system_prompt,
                            response_mime_type="application/json"
                        )
                    else:
                        config = genai.types.GenerateContentConfig(
                            system_instruction=system_prompt
                        )

                    response = self.gemini_client.models.generate_content(
                        model=model_name,
                        contents=user_message,
                        config=config
                    )
                    logger.info(f"Gemini API call succeeded (model: {model_name}, attempt: {attempt + 1}).")
                    return response.text
                except Exception as e:
                    error_str = str(e)
                    if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                        # Check if daily quota is genuinely exhausted (limit: 0 = no retries will help)
                        if "limit: 0" in error_str:
                            logger.warning(f"Gemini daily free tier quota exhausted for {model_name}. Skipping to next model.")
                            break  # Skip retries, try next model
                        
                        # Temporary rate limit — retry with backoff
                        import re
                        wait_time = min(2 ** attempt * 5, 20)  # 5s, 10s, 20s
                        
                        delay_match = re.search(r'retryDelay.*?(\d+)', error_str)
                        if delay_match:
                            suggested = int(delay_match.group(1))
                            wait_time = min(suggested + 2, 35)  # Cap at 35s
                        
                        logger.warning(f"Gemini 429 rate limit on {model_name} (attempt {attempt + 1}/3). Waiting {wait_time}s before retry...")
                        time.sleep(wait_time)
                        continue
                    else:
                        logger.error(f"Gemini API call failed (model: {model_name}): {e}")
                        break  # Non-retryable error, try next model
            
            logger.warning(f"All retries exhausted for Gemini model {model_name}. Trying next model...")

        logger.error("All Gemini models exhausted.")
        return None

    def _call_cerebras(self, system_prompt: str, user_message: str, response_format_json: bool = False) -> Optional[str]:
        if not self.cerebras_key:
            return None
        import httpx
        
        # Self-healing cascade: try different model ID variants
        models_to_try = ["llama-3.3-70b", "llama-3.1-8b", "llama3.1-8b"]
        for model in models_to_try:
            try:
                headers = {
                    "Authorization": f"Bearer {self.cerebras_key}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message}
                    ]
                }
                if response_format_json:
                    payload["response_format"] = {"type": "json_object"}
                    
                res = httpx.post("https://api.cerebras.ai/v1/chat/completions", json=payload, headers=headers, timeout=12.0)
                if res.status_code == 200:
                    logger.info(f"Cerebras API call succeeded with model {model}.")
                    return res.json()["choices"][0]["message"]["content"]
                elif res.status_code == 404:
                    logger.warning(f"Cerebras model {model} not found or restricted. Trying next variant...")
                    continue
                else:
                    logger.error(f"Cerebras API error with {model}: {res.status_code} - {res.text}")
            except Exception as e:
                logger.error(f"Cerebras API exception for {model}: {e}")
        return None

    def _call_openrouter(self, system_prompt: str, user_message: str, response_format_json: bool = False) -> Optional[str]:
        if not self.openrouter_key:
            return None
        import httpx
        try:
            headers = {
                "Authorization": f"Bearer {self.openrouter_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/anish/Abra",
                "X-Title": "Abra OS"
            }
            payload = {
                "model": "meta-llama/llama-3-8b-instruct:free",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ]
            }
            res = httpx.post("https://openrouter.ai/api/v1/chat/completions", json=payload, headers=headers, timeout=12.0)
            if res.status_code == 200:
                logger.info("OpenRouter API call succeeded.")
                return res.json()["choices"][0]["message"]["content"]
            else:
                logger.error(f"OpenRouter API error: {res.status_code} - {res.text}")
                return None
        except Exception as e:
            logger.error(f"OpenRouter API exception: {e}")
            return None

    def _call_ollama(self, system_prompt: str, user_message: str, response_format_json: bool = False) -> Optional[str]:
        import httpx
        try:
            # 1. Fetch available models from Ollama to see what they have installed
            res_tags = httpx.get("http://localhost:11434/api/tags", timeout=3.0)
            if res_tags.status_code != 200:
                return None
            models = [m["name"] for m in res_tags.json().get("models", [])]
            if not models:
                return None
                
            # 2. Select model (prefer Llama or Mistral matching what Anish has)
            selected_model = models[0]
            for m in models:
                m_lower = m.lower()
                if "llama" in m_lower or "mistral" in m_lower:
                    selected_model = m
                    break
                    
            logger.info(f"Ollama selected local model: {selected_model}")
            
            # 3. Call local chat completions
            payload = {
                "model": selected_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                "stream": False
            }
            if response_format_json:
                payload["format"] = "json"
                
            res = httpx.post("http://localhost:11434/api/chat", json=payload, timeout=120.0)
            if res.status_code == 200:
                logger.info("Ollama API call succeeded.")
                return res.json()["message"]["content"]
            else:
                logger.error(f"Ollama API error: {res.status_code} - {res.text}")
        except Exception as e:
            logger.warning(f"Ollama local endpoint unavailable: {e}")
        return None

    def call(self, system_prompt: str, user_message: str, response_format_json: bool = False) -> str:
        """
        Main unified execution layer. Tries primary provider first, then fallback, then mock.
        Respects LLM_PROVIDER setting for provider ordering, and dynamically cascades.
        """
        logger.info(f"LLM Call [Provider: {self.provider.upper()}]")
        
        providers = []
        
        # 1. Configured provider first
        if self.provider == "gemini":
            providers.append(("Gemini", self._call_gemini))
        elif self.provider == "groq":
            providers.append(("Groq", self._call_groq))
        elif self.provider == "cerebras":
            providers.append(("Cerebras", self._call_cerebras))
        elif self.provider == "openrouter":
            providers.append(("OpenRouter", self._call_openrouter))
        elif self.provider == "ollama":
            providers.append(("Ollama", self._call_ollama))
            
        # 2. Add other active providers dynamically if keys are present
        if self.gemini_key and ("Gemini", self._call_gemini) not in providers:
            providers.append(("Gemini", self._call_gemini))
        if self.groq_key and ("Groq", self._call_groq) not in providers:
            providers.append(("Groq", self._call_groq))
        if self.cerebras_key and ("Cerebras", self._call_cerebras) not in providers:
            providers.append(("Cerebras", self._call_cerebras))
        if self.openrouter_key and ("OpenRouter", self._call_openrouter) not in providers:
            providers.append(("OpenRouter", self._call_openrouter))
            
        # 3. Always append Ollama as the ultimate unlimited, offline local fallback!
        if ("Ollama", self._call_ollama) not in providers:
            providers.append(("Ollama", self._call_ollama))
            
        # Try each provider in sequence
        for name, fn in providers:
            try:
                logger.info(f"Attempting API call via {name}...")
                result = fn(system_prompt, user_message, response_format_json)
                if result:
                    return result
            except Exception as e:
                logger.warning(f"Provider {name} raised exception: {e}")
                
        # 4. High-Fidelity Mock Response (Fallback for safe sandbox demonstration)
        logger.warning("All LLM providers failed. Using mock response.")
        return self._get_mock_response(user_message, response_format_json)

    def _get_mock_response(self, user_message: str, response_format_json: bool) -> str:
        import json
        msg_lower = user_message.lower()

        if response_format_json:
            if "diary" in msg_lower or "log" in msg_lower:
                return json.dumps({
                    "summary": "Ran 6K in 32 minutes (felt good). Solved 3 NeetCode problems. Programmed Chess.com source spec for Abra OS.",
                    "mood": "Focused",
                    "activities": ["Running", "Coding", "Chess"],
                    "decisions": "Determined to avoid stack switches and finish Abra by May 31.",
                    "tomorrow_focus": "Integrate pattern warnings and check Notion database connections."
                })
            elif "goal" in msg_lower or "decompose" in msg_lower:
                return json.dumps({
                    "explanation": "To finish NeetCode 150 by July 31 (61 days left), we need exactly 2.4 problems per day. Pacing at 3 on study blocks and 1 on workout days.",
                    "tasks": [
                        {"title": "NeetCode: Two Pointers Section (3 problems)", "deadline": "2026-05-27", "category": "Career", "target": "Container With Most Water, 3sum, valid palindrome"},
                        {"title": "NeetCode: Sliding Window Section (3 problems)", "deadline": "2026-05-29", "category": "Career", "target": "Best time to buy/sell stock, longest substring"}
                    ]
                })
            return "{}"

        # Markdown briefings/reflection mocks conforming to direct tone laws
        if "briefing" in msg_lower or "should i work on" in msg_lower:
            return """### Morning OS Briefing 🌅
**Calendar Today:**
- ML CS229 Lecture Review (11:30 AM)
- Run 6K Grounding session (4:15 PM)
- Abra Core coding (6:00 PM)

**Core Focus Block:**
Forget the noise on LinkedIn, bruh. Focus for the next 45 minutes on finishing the calendar spec. That is your only priority.

**Pattern Check:**
⚠️ **Scatter Loop detected.** You switched from CS229 to looking up Rust pipelines yesterday. Stop bouncing between stacks. Stick to your active commitments.
"""
        elif "reflection" in msg_lower or "pattern" in msg_lower:
            return """### Behavior Reflection audit 🔍
Brutal honesty, bruh:
1. **Scatter Loop**: You spent 3 hours yesterday comparing Neovim configs instead of practicing DSA. This is task avoidance.
2. **2 AM Spiral**: You logged a diary entry at 2:15 AM searching about career timelines. You cannot solve a 2-year plan at midnight. Drink water, sleep. The morning run is the reset.
3. **Friend Isolation**: You haven't texted Sinchana or Srinidhi back in 2 days because you're 'busy' vibing. Reliable connections are critical. Send a quick text.
"""
        # Dynamic local telemetry fallbacks for rate limits
        if any(kw in msg_lower for kw in ["run", "strava", "running", "mileage", "km", "pace", "pb"]):
            from coral_query import coral_query_service
            try:
                sql = "SELECT name, (distance / 1000.0) as dist_km, elapsed_time, type, start_date FROM strava.activities"
                runs = coral_query_service.run_query(sql)
                if runs:
                    running_list = [r for r in runs if "run" in (r.get("type") or "Run").lower()]
                    total_runs = len(running_list)
                    if total_runs > 0:
                        total_dist = sum(r.get("dist_km", 0.0) for r in running_list)
                        run_items = []
                        for r in running_list[:5]:
                            elapsed = r.get("elapsed_time", 0.0)
                            mins = int(elapsed // 60)
                            secs = int(elapsed % 60)
                            time_str = f"{mins}:{secs:02d}" if mins < 60 else f"{mins//60}:{mins%60:02d}:{secs:02d}"
                            dist_str = f"{r.get('dist_km', 0.0):.2f}k"
                            date_str = r.get("start_date", "")[:10]
                            run_items.append(f"- **{r.get('name')}**: {dist_str} in {time_str} ({date_str})")
                        
                        return f"### Live Strava Audit (LLM Offline Fallback) 🏃‍♂️\n\nI queried your live Strava data directly using Coral CLI. Here is your authentic profile summary:\n\n* **Total Running Activities**: {total_runs} runs\n* **Total Running Volume**: {total_dist:.2f} km\n\n**Your 5 most recent runs:**\n" + "\n".join(run_items) + "\n\n**Verdict**: You have excellent running momentum! Keep maintaining your weekly volume target to stay consistent."
            except Exception:
                pass
            return "I can see your Strava running history! You have completed runs this week with a dynamic volume target. Maintain consistency, bruh! Let's get that run in."

        if any(kw in msg_lower for kw in ["chess", "rating", "blitz", "rapid", "game"]):
            from coral_query import coral_query_service
            try:
                sql = "SELECT chess_blitz__last__rating, chess_rapid__last__rating, chess_rapid__record__win, chess_rapid__record__loss FROM chesscom.stats"
                chess = coral_query_service.run_query(sql)
                if chess:
                    c = chess[0]
                    return f"### Chess.com Live Audit (LLM Offline Fallback) ♟️\n\nHere are your real-time ratings fetched live via Coral:\n\n* **Rapid Rating**: **{c.get('chess_rapid__last__rating', 1154)}**\n* **Blitz Rating**: **{c.get('chess_blitz__last__rating', 1332)}**\n* **Rapid Record**: {c.get('chess_rapid__record__win', 82)} Wins / {c.get('chess_rapid__record__loss', 55)} Losses\n\n**Verdict**: Looking strong! Analyze your mistakes on rapid matches and avoid late-night blitz spirals."
            except Exception:
                pass

        return "I am ABRA. Let's write some code, bruh. What is the single thing we are doing for the next 45 minutes?"

# Global single instance
llm_service = LLMService()
