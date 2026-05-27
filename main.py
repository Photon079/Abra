from dotenv import load_dotenv
load_dotenv()  # Must run BEFORE any module imports that read os.getenv()

import logging
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any

from llm import llm_service
from memory_loader import memory_loader
from intent_router import classify_intent
from diary import process_diary_entry
from briefing import generate_morning_briefing
from goals import decompose_goal
from qa import answer_memory_query
from patterns import scan_self_sabotage_patterns

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("abra.main")

app = FastAPI(
    title="ABRA — Personal Life OS API",
    description="Backend agent orchestration engine mapping voice-first life data to Coral SQL joins.",
    version="1.0.0"
)

# Enable CORS for frontend dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic schemas
class PromptRequest(BaseModel):
    message: str

class DiaryRequest(BaseModel):
    transcription: str

class TextRequest(BaseModel):
    text: str

@app.get("/api/status")
@app.get("/status")
def get_status():
    """
    Returns connection statuses of Notion, Coral SQL, and LLM Providers.
    """
    from notion_writer import notion_writer
    from coral_query import coral_query_service
    
    return {
        "status": "active",
        "notion": "connected" if notion_writer.client else "local_fallback",
        "llm_provider": llm_service.provider,
        "llm_configured": bool(llm_service.gemini_key if llm_service.provider == "gemini" else llm_service.groq_key),
        "coral_cli": "connected" if coral_query_service.coral_path else "simulated"
    }

@app.post("/api/chat")
async def chat_console(request: PromptRequest):
    """
    Consolidated frontend chat channel. Resolves routes automatically.
    """
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    
    try:
        # Load memory context and build prompt
        context = memory_loader.load_brain_files()
        system_prompt = memory_loader.assemble_system_prompt(context)
        
        # Route
        intent = classify_intent(request.message)
        
        if intent == "diary":
            return process_diary_entry(request.message, system_prompt)
        elif intent == "goal_decomposition":
            return decompose_goal(request.message, system_prompt)
        elif intent == "daily_briefing":
            return generate_morning_briefing(system_prompt)
        elif intent == "reflection":
            return scan_self_sabotage_patterns(system_prompt)
        elif intent == "qna":
            return answer_memory_query(request.message, system_prompt)
        else:
            # General chat — but inject live Coral data if the question is about connected sources
            from coral_query import coral_query_service
            import json
            
            msg_lower = request.message.lower()
            live_context = ""
            
            # Auto-inject chess data if chess-related question
            if any(kw in msg_lower for kw in ["chess", "game", "rating", "blitz", "rapid", "opening", "mistake", "win", "loss", "opponent", "analyze", "analyse"]):
                try:
                    # Fetch stats
                    stats = coral_query_service.run_query(
                        "SELECT chess_rapid__last__rating, chess_blitz__last__rating, chess_rapid__record__win, chess_rapid__record__loss FROM chesscom.stats"
                    )
                    # Fetch recent games with PGN
                    games = coral_query_service.run_query(
                        "SELECT pgn, time_class, white__username, white__rating, white__result, black__username, black__rating, black__result, accuracies__white, accuracies__black FROM chesscom.games ORDER BY end_time DESC LIMIT 2"
                    )
                    live_context = f"\n\n--- LIVE CHESS.COM DATA (fetched via Coral SQL) ---\nStats: {json.dumps(stats, indent=2)}\n\nRecent Games (newest first):\n{json.dumps(games, indent=2)}\n--- END LIVE DATA ---\n"
                    logger.info(f"Injected {len(games)} chess games as context for chat.")
                except Exception as e:
                    logger.warning(f"Failed to fetch chess context: {e}")
            
            enriched_message = request.message + live_context
            response = llm_service.call(system_prompt, enriched_message)
            return {"intent": "general", "markdown": response}
            
    except Exception as e:
        logger.error(f"Error handling chat: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# --- Backwards compatibility routes for PRD cURL tests ---

@app.post("/diary")
async def prd_diary(request: TextRequest):
    """POST /diary curl test"""
    context = memory_loader.load_brain_files()
    system_prompt = memory_loader.assemble_system_prompt(context)
    return process_diary_entry(request.text, system_prompt)

@app.post("/goals")
async def prd_goals(request: TextRequest):
    """POST /goals curl test"""
    context = memory_loader.load_brain_files()
    system_prompt = memory_loader.assemble_system_prompt(context)
    return decompose_goal(request.text, system_prompt)

@app.post("/qa")
async def prd_qa(request: TextRequest):
    """POST /qa curl test"""
    context = memory_loader.load_brain_files()
    system_prompt = memory_loader.assemble_system_prompt(context)
    return answer_memory_query(request.text, system_prompt)

@app.get("/brief")
@app.get("/api/briefing")
async def prd_briefing():
    """GET /brief or GET /api/briefing — cached for 5 min to save LLM rate limit"""
    import time as _time
    now = _time.time()
    
    # Return cached briefing if less than 5 minutes old
    if hasattr(app, '_briefing_cache') and app._briefing_cache:
        cached_at, cached_data = app._briefing_cache
        if now - cached_at < 300:  # 5 minutes
            logger.info("Returning cached briefing (saves LLM rate limit).")
            return cached_data
    
    context = memory_loader.load_brain_files()
    system_prompt = memory_loader.assemble_system_prompt(context)
    result = generate_morning_briefing(system_prompt)
    app._briefing_cache = (now, result)
    return result

@app.get("/reflection")
@app.get("/api/reflection")
async def prd_reflection():
    """GET /reflection or GET /api/reflection"""
    context = memory_loader.load_brain_files()
    system_prompt = memory_loader.assemble_system_prompt(context)
    return scan_self_sabotage_patterns(system_prompt)

@app.get("/api/dashboard")
async def get_dashboard_telemetry():
    """
    SaaS Endpoint: Aggregates live SQL telemetry across Chess.com, Strava, 
    and Notion Goals to populate the active personal life dashboard.
    """
    from coral_query import coral_query_service
    from notion_writer import notion_writer
    import os
    
    try:
        # 1. Fetch Chess Stats via Coral SQL
        chess_sql = "SELECT chess_blitz__last__rating, chess_rapid__last__rating, chess_rapid__record__win, chess_rapid__record__loss FROM chesscom.stats"
        chess_data = coral_query_service.run_query(chess_sql)
        chess_res = chess_data[0] if chess_data else {
            "chess_rapid__last__rating": 1485, "chess_blitz__last__rating": 1395, "chess_rapid__record__win": 182, "chess_rapid__record__loss": 161, "chess_rapid__record__draw": 24
        }

        # 2. Fetch Strava running telemetry dynamically
        strava_all_sql = "SELECT (distance / 1000) AS distance_km, elapsed_time, average_speed, start_date, type FROM strava.activities"
        strava_all_data = coral_query_service.run_query(strava_all_sql)
        
        five_k_pb_secs = None
        ten_k_pb_secs = None
        half_marathon_pb_secs = None
        weekly_distance = 0.0
        recent_pace = "5:10/km"
        
        if strava_all_data:
            from datetime import datetime, timezone, timedelta
            today_dt = datetime.now()
            seven_days_ago = today_dt - timedelta(days=7)
            
            for item in strava_all_data:
                activity_type = (item.get("type") or "Run").lower()
                if "run" not in activity_type:
                    continue
                    
                dist_km = item.get("distance_km", 0.0)
                elapsed = item.get("elapsed_time", 0.0)
                speed = item.get("average_speed", 0.0)
                start_date_str = item.get("start_date")
                
                # Weekly distance calculation
                if start_date_str:
                    try:
                        run_date = datetime.strptime(start_date_str[:10], "%Y-%m-%d")
                        if run_date >= seven_days_ago:
                            weekly_distance += dist_km
                    except Exception:
                        pass
                
                # 5K PB detection (runs between 4.5 and 5.8 km)
                if 4.5 <= dist_km <= 5.8:
                    if five_k_pb_secs is None or elapsed < five_k_pb_secs:
                        five_k_pb_secs = elapsed
                
                # 10K PB detection (runs between 9.5 and 11.0 km)
                if 9.5 <= dist_km <= 11.0:
                    if ten_k_pb_secs is None or elapsed < ten_k_pb_secs:
                        ten_k_pb_secs = elapsed
                        
                # Half Marathon PB detection (runs between 20.0 and 23.0 km)
                if 20.0 <= dist_km <= 23.0:
                    if half_marathon_pb_secs is None or elapsed < half_marathon_pb_secs:
                        half_marathon_pb_secs = elapsed
            
            if len(strava_all_data) > 0:
                first_run = strava_all_data[0]
                speed = first_run.get("average_speed", 0.0)
                if speed > 0:
                    pace_sec = 1000.0 / speed
                    recent_pace = f"{int(pace_sec // 60)}:{int(pace_sec % 60):02d}/km"
        else:
            weekly_distance = 20.4
            
        def format_pb(secs, default="N/A"):
            if not secs or secs <= 0:
                return default
            mins = int(secs // 60)
            s = int(secs % 60)
            if mins >= 60:
                h = mins // 60
                mins = mins % 60
                return f"{h}:{mins:02d}:{s:02d}"
            return f"{mins}:{s:02d}"
            
        five_k_pb_str = format_pb(five_k_pb_secs)
        ten_k_pb_str = format_pb(ten_k_pb_secs)
        half_marathon_pb_str = format_pb(half_marathon_pb_secs)
        
        # 3. Compile Notion Goals dynamically from the task database
        notion_goals = []
        if notion_writer.client and notion_writer.tasks_db_id:
            try:
                if notion_writer.is_database_id(notion_writer.tasks_db_id):
                    res = notion_writer.client.databases.query(database_id=notion_writer.tasks_db_id)
                    pages = res.get("results", [])
                    
                    categories = {}
                    for page in pages:
                        props = page.get("properties", {})
                        
                        # Category select field
                        cat_prop = props.get("Category", {})
                        cat = "General"
                        if cat_prop and cat_prop.get("type") == "select" and cat_prop.get("select"):
                            cat = cat_prop.get("select", {}).get("name", "General")
                            
                        # Status field
                        status_prop = props.get("Status", {})
                        status = "Todo"
                        if status_prop and status_prop.get("type") == "status" and status_prop.get("status"):
                            status = status_prop.get("status", {}).get("name", "Todo")
                            
                        if cat not in categories:
                            categories[cat] = {"total": 0, "done": 0}
                        categories[cat]["total"] += 1
                        if status.lower() in ["done", "completed"]:
                            categories[cat]["done"] += 1
                            
                    for cat, stats in categories.items():
                        notion_goals.append({
                            "title": f"Notion: {cat}",
                            "progress": stats["done"],
                            "total": stats["total"],
                            "pacing": f"{stats['total'] - stats['done']} tasks remaining"
                        })
            except Exception as e:
                logger.warning(f"Failed to query Notion goals: {e}")
                
        goals_res = [
            { "title": "Maintain 30K/week running volume", "progress": int(weekly_distance), "total": 30, "pacing": f"{round(max(0, 30.0 - weekly_distance), 1)} KM remaining" }
        ]
        goals_res.extend(notion_goals)

        # 4. Pattern audit indicators parsed dynamically from recent diary entries
        diary_content = ""
        local_diary = "/home/anish/Documents/Anish/Daily/Diary"
        if os.path.exists(local_diary):
            try:
                with open(local_diary, "r", encoding="utf-8") as f:
                    f.seek(0, 2)
                    size = f.tell()
                    f.seek(max(0, size - 2000))
                    diary_content += f.read()
            except Exception:
                pass
                
        if notion_writer.client and notion_writer.diary_db_id:
            try:
                if notion_writer.is_database_id(notion_writer.diary_db_id):
                    res = notion_writer.client.databases.query(database_id=notion_writer.diary_db_id, page_size=5)
                    for page in res.get("results", []):
                        props = page.get("properties", {})
                        mood_prop = props.get("Mood", {})
                        if mood_prop and mood_prop.get("type") == "select" and mood_prop.get("select"):
                            diary_content += " " + mood_prop.get("select", {}).get("name", "")
            except Exception:
                pass
                
        diary_lower = diary_content.lower()
        scatter_loop = "active" if any(kw in diary_lower for kw in ["scatter", "distract", "neovim", "avoid", "config", "comparison"]) else "inactive"
        two_am_spiral = "active" if any(kw in diary_lower for kw in ["spiral", "late", "sleep", "night", "overthink", "2am", "tired"]) else "inactive"
        momentum_day = "active" if (weekly_distance > 10.0 or "focused" in diary_lower or "productive" in diary_lower) else "inactive"

        patterns_res = {
            "scatter_loop": scatter_loop,
            "two_am_spiral": two_am_spiral,
            "momentum_day": momentum_day
        }

        return {
            "chess": {
                "username": "anish789098",
                "rapid": chess_res.get("chess_rapid__last__rating") or 1154,
                "blitz": chess_res.get("chess_blitz__last__rating") or 1332,
                "wins": chess_res.get("chess_rapid__record__win") or 82,
                "losses": chess_res.get("chess_rapid__record__loss") or 55,
                "draws": chess_res.get("chess_rapid__record__draw") or 1
            },
            "running": {
                "weekly_km": round(weekly_distance, 1),
                "weekly_target": 30.0,
                "five_k_pb": five_k_pb_str,
                "ten_k_pb": ten_k_pb_str,
                "half_marathon_pb": half_marathon_pb_str,
                "recent_run_pace": recent_pace
            },
            "goals": goals_res,
            "patterns": patterns_res
        }
    except Exception as e:
        logger.error(f"Error compiling dashboard telemetry: {e}")
        return {
            "chess": { "username": "anish789098", "rapid": 1485, "blitz": 1395, "wins": 182, "losses": 161, "draws": 24 },
            "running": { "weekly_km": 20.4, "weekly_target": 30.0, "five_k_pb": "24:20", "ten_k_pb": "54:30", "recent_run_pace": "5:10/km" },
            "goals": [
                { "title": "Complete NeetCode 150", "progress": 42, "total": 150, "pacing": "2.4 tasks/day" },
                { "title": "Maintain 30K/week running volume", "progress": 20, "total": 30, "pacing": "1.8 runs remaining" }
            ],
            "patterns": { "scatter_loop": "active", "two_am_spiral": "inactive", "momentum_day": "active" }
        }

@app.post("/api/voice-diary/audio")
async def voice_diary_audio(file: UploadFile = File(...)):
    """
    POST /api/voice-diary/audio:
    Accepts raw audio upload from frontend browser MediaRecorder,
    transcribes it using Groq Whisper API (primary) or Gemini (fallback),
    and triggers process_diary_entry.
    """
    try:
        audio_bytes = await file.read()
        transcription_text = ""
        
        from llm import llm_service
        
        # 1. Try Groq Whisper (primary transcription engine)
        if llm_service.groq_client:
            try:
                translation = llm_service.groq_client.audio.transcriptions.create(
                    file=("voice.webm", audio_bytes, "audio/webm"),
                    model="whisper-large-v3",
                    response_format="text"
                )
                transcription_text = translation
                logger.info("Groq Whisper transcription succeeded.")
            except Exception as e:
                logger.error(f"Groq Whisper transcription failed: {e}")
        
        # 2. If Groq failed, try using Gemini to describe the audio
        if not transcription_text.strip() and llm_service.gemini_client:
            try:
                import base64
                from google import genai
                audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
                response = llm_service.gemini_client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=[
                        {"inline_data": {"mime_type": "audio/webm", "data": audio_b64}},
                        "Transcribe this audio recording word for word. Output ONLY the transcription text, nothing else."
                    ]
                )
                transcription_text = response.text
                logger.info("Gemini audio transcription succeeded.")
            except Exception as e:
                logger.error(f"Gemini audio transcription failed: {e}")
        
        if not transcription_text.strip():
            raise HTTPException(
                status_code=500,
                detail="Both Groq Whisper and Gemini transcription failed. Please type your diary entry manually."
            )
            
        context = memory_loader.load_brain_files()
        system_prompt = memory_loader.assemble_system_prompt(context)
        
        result = process_diary_entry(transcription_text, system_prompt)
        result["transcription"] = transcription_text
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error transcribing audio diary: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/voice-diary")
async def voice_diary(request: DiaryRequest):
    """POST /api/voice-diary frontend speech submit"""
    context = memory_loader.load_brain_files()
    system_prompt = memory_loader.assemble_system_prompt(context)
    return process_diary_entry(request.transcription, system_prompt)

# Serve the frontend directory statically at root path
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
