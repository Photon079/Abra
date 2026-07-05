"""Abra — Personal Life OS backend package.

Layout:
    app/llm.py               unified LLM cascade (Gemini / Groq / Cerebras / OpenRouter)
    app/intent_router.py     routes explicit commands vs. general chat
    app/coral/               Coral SQL live-data plane (query + startup registration)
    app/memory/              memory plane — Cognee graph memory + legacy Notion loader
    app/integrations/        external write surfaces (Notion)
    app/features/            request handlers (diary, briefing, goals, qa, patterns)
    app/main.py              FastAPI app + routes
"""
from pathlib import Path

# Repository root — used for locating sources/, frontend/, .env, local_data/
PROJECT_ROOT = Path(__file__).resolve().parent.parent
