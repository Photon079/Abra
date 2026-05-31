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
        self.gemini_models = ["gemini-2.0-flash", "gemini-2.0-flash-lite", "gemini-flash-latest", "gemini-pro-latest"]

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
            
        # Groq free tier is strictly 6000 TPM. 
        # Capping system_prompt to 10k chars (~2500 tokens) and user_message to 8k chars (~2000 tokens)
        if len(system_prompt) > 10000:
            logger.warning("Truncating system prompt for Groq...")
            system_prompt = system_prompt[:10000] + "\n...[TRUNCATED]"
            
        if len(user_message) > 8000:
            logger.warning("Truncating user message for Groq...")
            user_message = user_message[:8000] + "\n...[TRUNCATED]"
            
        try:
            # Fallback to model with larger free tier TPM limit
            model = "llama-3.1-8b-instant"
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
                        
                        logger.warning(f"Gemini 429 rate limit on {model_name} (attempt {attempt + 1}/3). Failing fast to avoid blocking UI...")
                        break  # Fail fast instead of sleeping
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


# 2. Add other active providers dynamically if keys are present
        if self.gemini_key and ("Gemini", self._call_gemini) not in providers:
            providers.append(("Gemini", self._call_gemini))
        if self.groq_key and ("Groq", self._call_groq) not in providers:
            providers.append(("Groq", self._call_groq))


            
# Try each provider in sequence
        for name, fn in providers:
            try:
                logger.info(f"Attempting API call via {name}...")
                result = fn(system_prompt, user_message, response_format_json)
                if result:
                    return result
            except Exception as e:
                logger.warning(f"Provider {name} raised exception: {e}")
                
        # 4. Fail Fast - No Simulation Policy
        logger.error("All LLM providers failed. Raising exception.")
        raise RuntimeError("All cloud LLMs hit rate limits and local Ollama timed out. Failing fast.")

# Global single instance
llm_service = LLMService()
