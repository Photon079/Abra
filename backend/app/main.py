import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from app.config import settings
from app.agent.agent import abra_agent
from app.services.notion_service import notion_service
from app.services.coral_service import coral_service

# Configure logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("abra.main")

app = FastAPI(
    title="ABRA — Personal Life OS API",
    description="Backend agent orchestration engine for voice-first personal memory assistant.",
    version="1.0.0"
)

# CORS middleware for local frontend connections
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str

class VoiceDiaryRequest(BaseModel):
    transcription: str

@app.get("/api/status")
def get_status():
    """
    Returns the status and health of the ABRA integration layers.
    """
    return {
        "status": "active",
        "notion": "connected" if notion_service.client else "local_fallback",
        "llm_provider": settings.LLM_PROVIDER,
        "llm_configured": bool(settings.GEMINI_API_KEY if settings.LLM_PROVIDER == "gemini" else settings.GROQ_API_KEY),
        "coral_cli": "connected" if coral_service.coral_path else "simulated"
    }

@app.post("/api/chat")
async def chat(request: ChatRequest):
    """
    Standard chat endpoint supporting memory Q&A, goal decomposition, and general assistance.
    """
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    try:
        response = abra_agent.process_input(request.message)
        return response
    except Exception as e:
        logger.error(f"Error processing chat: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/voice-diary")
async def voice_diary(request: VoiceDiaryRequest):
    """
    Takes voice note transcriptions, enriches with Coral SQL queries, 
    and saves structured entries to the Notion Diary database.
    """
    if not request.transcription.strip():
        raise HTTPException(status_code=400, detail="Transcription cannot be empty")
    try:
        response = abra_agent._handle_diary_flow(request.transcription, system_prompt="")
        return response
    except Exception as e:
        logger.error(f"Error processing voice diary: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/briefing")
async def get_briefing():
    """
    Triggers and returns the daily morning brief.
    """
    try:
        response = abra_agent.process_input("Generate briefing")
        return response
    except Exception as e:
        logger.error(f"Error getting briefing: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/reflection")
async def get_reflection():
    """
    Scans recent diaries for self-sabotage loops and outputs a direct mirror audit.
    """
    try:
        response = abra_agent.process_input("Run reflection")
        return response
    except Exception as e:
        logger.error(f"Error getting reflection: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.HOST, port=settings.PORT)
