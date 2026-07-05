from dotenv import load_dotenv
load_dotenv()  # Must run BEFORE any module imports that read os.getenv()

from app.coral.startup import bootstrap
bootstrap()

import logging
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any

from app import PROJECT_ROOT

from app.llm import llm_service
from app.memory.notion_loader import memory_loader
from app.intent_router import classify_intent
from app.features.diary import process_diary_entry
from app.features.briefing import generate_morning_briefing
from app.features.goals import decompose_goal
from app.features.qa import answer_memory_query
from app.features.patterns import scan_self_sabotage_patterns
from app.integrations.notion import notion_writer
from app.integrations.local_store import local_store
from app.memory.graph_memory import (
    graph_memory,
    NODE_DIARY,
    NODE_FITNESS,
    NODE_CHESS,
)

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


@app.middleware("http")
async def no_cache_html(request, call_next):
    """Never let the browser serve stale HTML (esp. via the back/forward cache),
    so nav changes like new pages show up immediately without a hard refresh."""
    response = await call_next(request)
    if response.headers.get("content-type", "").startswith("text/html"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return response


@app.on_event("startup")
def _verify_graph_memory():
    """Verify Cognee Cloud connectivity at startup without blocking boot (G4)."""
    if graph_memory.enabled:
        import threading
        threading.Thread(target=graph_memory.connect_check, daemon=True).start()


# Pydantic schemas
class PromptRequest(BaseModel):
    message: str

class DiaryRequest(BaseModel):
    transcription: str

class TextRequest(BaseModel):
    text: str

class LocalDiaryRequest(BaseModel):
    summary: str
    mood: Optional[str] = None
    activities: Optional[list] = None
    date: Optional[str] = None  # ISO YYYY-MM-DD

class LocalTaskRequest(BaseModel):
    title: str
    category: Optional[str] = None
    due_date: Optional[str] = None  # ISO YYYY-MM-DD

class TaskStatusRequest(BaseModel):
    status: str  # "done" | "todo"

class MemoryAskRequest(BaseModel):
    query: str

class TaskDoneRequest(BaseModel):
    done: bool = True

@app.get("/api/status")
@app.get("/status")
def get_status():
    """
    Returns connection statuses of Notion, Coral SQL, and LLM Providers.
    """
    from app.integrations.notion import notion_writer
    from app.coral.query import coral_query_service
    
    return {
        "status": "active",
        "notion": "connected" if notion_writer.client else "local_fallback",
        "llm_provider": llm_service.provider,
        "llm_configured": bool(llm_service.gemini_key if llm_service.provider == "gemini" else llm_service.groq_key),
        "coral_cli": "connected" if coral_query_service.coral_path else "simulated",
        "graph_memory": graph_memory.status(),
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
            from app.coral.query import coral_query_service, chess_where
            import json
            
            msg_lower = request.message.lower()
            live_context = ""
            
            # Auto-inject chess data if chess-related question
            if any(kw in msg_lower for kw in ["chess", "game", "rating", "blitz", "rapid", "opening", "mistake", "win", "loss", "opponent", "analyze", "analyse"]):
                try:
                    # Fetch stats
                    stats = coral_query_service.run_query(
                        f'SELECT chess_blitz__last__rating, chess_rapid__last__rating, chess_rapid__record__win, chess_rapid__record__loss FROM chesscom.stats WHERE {chess_where()}'
                    )
                    # Fetch recent games with PGN
                    games = coral_query_service.run_query(
                        f"SELECT pgn, time_class, white__username, white__rating, white__result, black__username, black__rating, black__result, accuracies__white, accuracies__black FROM chesscom.games WHERE {chess_where(include_archive=True)} ORDER BY end_time DESC LIMIT 2"
                    )
                    live_context += f"\n\n--- LIVE CHESS.COM DATA (fetched via Coral SQL) ---\nStats: {json.dumps(stats, indent=2)}\n\nRecent Games (newest first):\n{json.dumps(games, indent=2)}\n--- END LIVE DATA ---\n"
                    logger.info(f"Injected {len(games)} chess games as context for chat.")
                except Exception as e:
                    logger.warning(f"Failed to fetch chess context: {e}")
                    
            # Auto-inject strava data if running-related question
            if any(kw in msg_lower for kw in ["run", "running", "strava", "pace", "distance", "marathon", "km", "cardio", "jog"]):
                try:
                    runs = coral_query_service.run_query(
                        "SELECT name, distance, elapsed_time, average_speed, start_date, type FROM strava.activities ORDER BY start_date DESC LIMIT 10"
                    )
                    live_context += f"\n\n--- LIVE STRAVA DATA (fetched via Coral SQL) ---\nRecent Runs (newest first):\n{json.dumps(runs, indent=2)}\n--- END LIVE DATA ---\n"
                    logger.info(f"Injected {len(runs)} strava runs as context for chat.")
                except Exception as e:
                    logger.warning(f"Failed to fetch strava context: {e}")
            
            # Auto-inject Notion data if notion-related question
            if any(kw in msg_lower for kw in ["notion", "task", "diary", "schedule", "goal", "plan", "todo"]):
                try:
                    import httpx
                    if notion_writer.client and notion_writer.tasks_db_id and notion_writer.diary_db_id:
                        headers = {
                            "Authorization": f"Bearer {notion_writer.client.auth}",
                            "Notion-Version": "2022-06-28",
                            "Content-Type": "application/json"
                        }
                        
                        # Safe property extraction helpers
                        def extract_task(p):
                            try:
                                return {
                                    "title": p.get("properties", {}).get("Task Name", {}).get("title", [{"plain_text": "Untitled"}])[0].get("plain_text", "Untitled"),
                                    "status": p.get("properties", {}).get("Status", {}).get("status", {}).get("name", "Todo"),
                                    "category": p.get("properties", {}).get("Category", {}).get("select", {}).get("name", "General")
                                }
                            except:
                                return {"title": "Error parsing task"}
                                
                        def extract_diary(p):
                            try:
                                r_text = p.get("properties", {}).get("Summary", {}).get("rich_text", [])
                                summary = r_text[0].get("plain_text", "") if r_text else ""
                                return {
                                    "date": p.get("properties", {}).get("Date", {}).get("date", {}).get("start", ""),
                                    "mood": p.get("properties", {}).get("Mood Signal", {}).get("select", {}).get("name", ""),
                                    "summary": summary
                                }
                            except:
                                return {"summary": "Error parsing diary entry"}

                        # Fetch tasks
                        if notion_writer.is_database_id(notion_writer.tasks_db_id):
                            tasks_res = httpx.post(f"https://api.notion.com/v1/databases/{notion_writer.tasks_db_id}/query", headers=headers, json={"page_size": 10})
                            tasks = [extract_task(p) for p in tasks_res.json().get("results", [])]
                        else:
                            tasks = []
                        
                        # Fetch diary
                        diary = []
                        if notion_writer.is_database_id(notion_writer.diary_db_id):
                            try:
                                diary_res = httpx.post(f"https://api.notion.com/v1/databases/{notion_writer.diary_db_id}/query", headers=headers, json={"page_size": 5})
                                if diary_res.status_code == 200:
                                    diary = [extract_diary(p) for p in diary_res.json().get("results", [])]
                            except:
                                pass
                        
                        live_context += f"\n\n--- LIVE NOTION DATA ---\nRecent Tasks:\n{json.dumps(tasks, indent=2)}\n\nRecent Diary Entries:\n{json.dumps(diary, indent=2)}\n--- END LIVE DATA ---\n"
                        logger.info(f"Injected notion tasks and diary as context for chat.")
                except Exception as e:
                    logger.warning(f"Failed to fetch notion context: {e}")

            # Graph memory retrieval (v2) — relationship / temporal context from
            # the Cognee knowledge graph. No-op when USE_GRAPH_MEMORY is off.
            try:
                graph_ctx = graph_memory.retrieve(request.message)
                if graph_ctx:
                    live_context += f"\n\n--- GRAPH MEMORY (Cognee knowledge graph) ---\n{graph_ctx}\n--- END GRAPH MEMORY ---\n"
                    logger.info("Injected graph memory context into chat.")
            except Exception as e:
                logger.warning(f"Graph memory retrieve failed in chat: {e}")

            enriched_message = request.message + live_context
            response = llm_service.call(system_prompt, enriched_message)
            
            # --- INTERCEPT LLM COMMANDS ---
            import re
            
            task_match = re.search(r'\[UPDATE_TASK:\s*(.+?)\]', response)
            if task_match:
                task_name = task_match.group(1).strip()
                success = notion_writer.update_task_status(task_name, "Done")
                if success:
                    response = response.replace(task_match.group(0), "") + f"\n\n*(System Note: Task '{task_name}' successfully marked as Done in Notion)*"
                else:
                    response = response.replace(task_match.group(0), "") + f"\n\n*(System Note: Failed to update task '{task_name}'. It might not exist.)*"
                    
            brain_match = re.search(r'\[UPDATE_BRAIN:\s*(.+?)\](.*?)\[END_UPDATE\]', response, re.DOTALL)
            if brain_match:
                file_key = brain_match.group(1).strip()
                content = brain_match.group(2).strip()
                success = notion_writer.update_brain_file(file_key, content)
                if success:
                    response = response.replace(brain_match.group(0), "") + f"\n\n*(System Note: Brain file '{file_key}' successfully overwritten)*"
            # ------------------------------
            
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
    from app.coral.query import coral_query_service, chess_where
    from app.integrations.notion import notion_writer
    from app.llm import llm_service
    import os

    try:
        # 1. Fetch Chess Stats via Coral SQL
        chess_stats_sql = f'SELECT chess_blitz__last__rating, chess_rapid__last__rating FROM chesscom.stats WHERE {chess_where()}'
        chess_stats_data = coral_query_service.run_query(chess_stats_sql)
        chess_res = chess_stats_data[0] if chess_stats_data else {}

        # Chess volume & results for the current monthly archive
        chess_games_sql = f'SELECT white__username, black__username, white__result, black__result FROM chesscom.games WHERE {chess_where(include_archive=True)}'
        chess_games_data = coral_query_service.run_query(chess_games_sql)
        
        chess_user = os.getenv("CHESSCOM_USERNAME", "Unknown").lower()
        wins = 0
        losses = 0
        draws = 0
        loss_types = {}
        total_games = len(chess_games_data)
        
        for g in chess_games_data:
            w_user = str(g.get("white__username", "")).lower()
            b_user = str(g.get("black__username", "")).lower()
            w_res = str(g.get("white__result", "")).lower()
            b_res = str(g.get("black__result", "")).lower()
            
            if w_user == chess_user:
                my_res = w_res
            elif b_user == chess_user:
                my_res = b_res
            else:
                continue
                
            if my_res == "win":
                wins += 1
            elif my_res in ["agreed", "repetition", "stalemate", "insufficient", "timevsinsufficient"]:
                draws += 1
            else:
                losses += 1
                loss_types[my_res] = loss_types.get(my_res, 0) + 1
                
        win_rate = round((wins / total_games) * 100) if total_games > 0 else 0
        
        # Chess Predictive AI Insight
        chess_insight = "Keep playing to generate insights."
        if total_games > 0:
            prompt = f"I played {total_games} games recently. {wins} wins, {losses} losses, {draws} draws. My loss reasons: {loss_types}. Provide a 1-sentence tactical or psychological advice for me to improve."
            try:
                chess_insight = llm_service.call(
                    "You are a chess coach.",
                    prompt
                ).strip()
            except:
                pass

        # 2. Fetch Strava running telemetry dynamically (30 Days and 7 Days)
        strava_sql_30 = "SELECT sum(distance)/1000 AS total_km, sum(moving_time)/3600.0 AS total_hours, avg(average_speed) as avg_speed, count(*) as total_runs FROM strava.activities WHERE type = 'Run' AND start_date_local >= current_date() - interval '30 days'"
        strava_sql_7 = "SELECT sum(distance)/1000 AS total_km, sum(moving_time)/3600.0 AS total_hours FROM strava.activities WHERE type = 'Run' AND start_date_local >= current_date() - interval '7 days'"
        
        strava_data_30 = coral_query_service.run_query(strava_sql_30)
        strava_data_7 = coral_query_service.run_query(strava_sql_7)
        
        monthly_distance = 0.0
        monthly_hours = 0.0
        monthly_runs = 0
        weekly_distance = 0.0
        weekly_hours = 0.0
        recent_pace = "N/A"
        
        if strava_data_30 and len(strava_data_30) > 0:
            row = strava_data_30[0]
            monthly_distance = float(row.get("total_km") or 0.0)
            monthly_hours = float(row.get("total_hours") or 0.0)
            monthly_runs = int(row.get("total_runs") or 0)
            avg_speed = float(row.get("avg_speed") or 0.0)
            if avg_speed > 0:
                pace_sec = 1000.0 / avg_speed
                recent_pace = f"{int(pace_sec // 60)}:{int(pace_sec % 60):02d}/km"
                
        if strava_data_7 and len(strava_data_7) > 0:
            row_7 = strava_data_7[0]
            weekly_distance = float(row_7.get("total_km") or 0.0)
            weekly_hours = float(row_7.get("total_hours") or 0.0)
                
        # Strava Predictive AI Insight
        strava_insight = "Log more runs to generate a training plan."
        if monthly_runs > 0:
            prompt = f"In the last 30 days I ran {monthly_distance:.1f}km over {monthly_runs} runs. Average pace: {recent_pace}. Suggest my next run type (e.g. Zone 2, Intervals) and a target pace in 1 sentence."
            try:
                strava_insight = llm_service.call(
                    "You are an elite running coach.",
                    prompt
                ).strip()
            except:
                pass

        # 3. Compile Notion Goals dynamically
        notion_goals = []
        if notion_writer.client and notion_writer.tasks_db_id:
            try:
                if notion_writer.is_database_id(notion_writer.tasks_db_id):
                    import httpx
                    res_raw = httpx.post(
                        f"https://api.notion.com/v1/databases/{notion_writer.tasks_db_id}/query",
                        headers={"Authorization": f"Bearer {os.getenv('NOTION_TOKEN')}", "Notion-Version": "2022-06-28"},
                        json={}
                    )
                    res_raw.raise_for_status()
                    res = res_raw.json()
                    pages = res.get("results", [])
                    
                    from datetime import datetime, timezone, timedelta
                    today_dt = datetime.now(timezone.utc)
                    thirty_days_ago = today_dt - timedelta(days=30)
                    
                    categories = {}
                    for page in pages:
                        created_time_str = page.get("created_time")
                        if created_time_str:
                            try:
                                created_time = datetime.strptime(created_time_str[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
                                if created_time < thirty_days_ago:
                                    continue
                            except: pass
                                
                        props = page.get("properties", {})
                        cat_prop = props.get("Category", {})
                        cat = "General"
                        if cat_prop and cat_prop.get("type") == "select" and cat_prop.get("select"):
                            cat = cat_prop.get("select", {}).get("name", "General")
                            
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
                pass
        goals_res = notion_goals

        # Life & Goals Predictive AI Insight
        life_insight = "Keep progressing on your active tasks."
        if goals_res:
            prompt = f"Here are my current goals pacing: {goals_res}. I also ran {monthly_distance}km and played {total_games} chess games this month. Give me a 1-sentence holistic life or productivity insight."
            try:
                life_insight = llm_service.call("You are a holistic life coach.", prompt).strip()
            except:
                pass

        # Persist a compact daily insight snapshot into the graph (F4). Throttled
        # to once/hour so the frontend's dashboard polling doesn't flood cognify.
        import time as _t
        now_ts = _t.time()
        if now_ts - getattr(app, "_dash_insight_at", 0) > 3600:
            app._dash_insight_at = now_ts
            graph_memory.ingest_insight(
                f"Daily snapshot: chess {chess_res.get('chess_blitz__last__rating', 0)} blitz "
                f"({wins}W-{losses}L, {win_rate}% win rate) — {chess_insight} "
                f"Running {round(monthly_distance, 1)}km/30d — {strava_insight} "
                f"Holistic: {life_insight}",
                background=True,
            )

        # 4. Patterns
        return {
            "chess": {
                "username": chess_user,
                "rapid": chess_res.get("chess_rapid__last__rating", 0),
                "blitz": chess_res.get("chess_blitz__last__rating", 0),
                "wins": wins,
                "losses": losses,
                "draws": draws,
                "win_rate": win_rate,
                "total_games": total_games,
                "insight": chess_insight
            },
            "running": {
                "weekly_km": round(weekly_distance, 1),
                "weekly_target": float(os.getenv("STRAVA_WEEKLY_KM_TARGET", 30.0)),
                "weekly_hours": round(weekly_hours, 1),
                "monthly_km": round(monthly_distance, 1),
                "monthly_target": float(os.getenv("STRAVA_WEEKLY_KM_TARGET", 30.0)) * 4,
                "monthly_hours": round(monthly_hours, 1),
                "average_pace": recent_pace,
                "monthly_runs": monthly_runs,
                "insight": strava_insight
            },
            "goals": goals_res,
            "patterns": { "scatter_loop": "inactive", "two_am_spiral": "inactive", "momentum_day": "active" },
            "life_insight": life_insight
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
        
        from app.llm import llm_service
        
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

@app.get("/api/memory")
def get_memory_status():
    """Graph memory (Cognee Cloud) status for the dashboard / debugging."""
    return graph_memory.status()


@app.post("/memory/backfill")
@app.post("/api/memory/backfill")
def backfill_memory():
    """
    One-time backfill: populate the Cognee knowledge graph with existing Notion
    diary history + a 30-day Coral telemetry snapshot, so the graph has real
    history to reason over before demo recording. Compact summaries only
    (PRD risk #4: avoid dumping raw SQL rows into the graph).
    """
    if not graph_memory.enabled:
        raise HTTPException(
            status_code=400,
            detail="Graph memory disabled. Set USE_GRAPH_MEMORY=true and COGNEE_API_KEY, then restart.",
        )

    from app.coral.query import coral_query_service, chess_where
    import datetime as _dt
    import httpx

    today = _dt.date.today().isoformat()
    items = []

    # 1. Coral telemetry — one compact 30-day snapshot blob (fitness + chess).
    try:
        strava = coral_query_service.run_query(
            "SELECT sum(distance)/1000 AS total_km, sum(moving_time)/3600.0 AS total_hours, "
            "count(*) AS runs FROM strava.activities WHERE type = 'Run' "
            "AND start_date_local >= current_date() - interval '30 days'"
        )
        chess = coral_query_service.run_query(
            f"SELECT chess_blitz__last__rating, chess_rapid__last__rating FROM chesscom.stats WHERE {chess_where()}"
        )
        s = strava[0] if strava else {}
        c = chess[0] if chess else {}
        telemetry_summary = (
            f"30-day telemetry snapshot as of {today}: running "
            f"{round(float(s.get('total_km') or 0), 1)} km over {int(s.get('runs') or 0)} runs "
            f"({round(float(s.get('total_hours') or 0), 1)} hours). Chess ratings — blitz "
            f"{c.get('chess_blitz__last__rating')}, rapid {c.get('chess_rapid__last__rating')}."
        )
        items.append((telemetry_summary, [NODE_FITNESS, NODE_CHESS]))
    except Exception as e:
        logger.warning(f"Backfill telemetry step failed: {e}")

    # 2. Notion diary history (database-backed diary only).
    diary_found = 0
    try:
        if (
            notion_writer.client
            and notion_writer.diary_db_id
            and notion_writer.is_database_id(notion_writer.diary_db_id)
        ):
            headers = {
                "Authorization": f"Bearer {notion_writer.client.auth}",
                "Notion-Version": "2022-06-28",
                "Content-Type": "application/json",
            }
            res = httpx.post(
                f"https://api.notion.com/v1/databases/{notion_writer.diary_db_id}/query",
                headers=headers,
                json={"page_size": 100},
                timeout=15,
            )
            for p in res.json().get("results", []):
                props = p.get("properties", {})
                date_val = p.get("created_time", "")[:10]
                if props.get("Date", {}).get("date"):
                    date_val = props["Date"]["date"].get("start", date_val)
                mood = None
                if props.get("Mood", {}).get("select"):
                    mood = props["Mood"]["select"]["name"]
                summary = ""
                for field in ["Summary", "Entry", "Notes"]:
                    rt = props.get(field, {}).get("rich_text")
                    if rt:
                        summary = rt[0].get("plain_text", "")
                        break
                acts = []
                if props.get("Activities Logged", {}).get("multi_select"):
                    acts = [a["name"] for a in props["Activities Logged"]["multi_select"]]
                entry = {"summary": summary, "mood": mood, "activities": acts}
                from app.memory.graph_memory import _diary_to_text
                items.append((_diary_to_text(entry, date_val), [NODE_DIARY]))
                diary_found += 1
    except Exception as e:
        logger.warning(f"Backfill diary step failed: {e}")

    ingested = graph_memory.ingest_batch(items)
    return {
        "status": "backfilled",
        "diary_entries_found": diary_found,
        "items_ingested": ingested,
        "memory": graph_memory.status(),
    }


# ── Local-first "Second Brain": diary + tasks stored in SQLite, zero setup ────

@app.get("/api/local/diary")
def local_diary_list():
    return {"entries": local_store.list_diary()}


@app.post("/api/local/diary")
def local_diary_add(req: LocalDiaryRequest):
    if not req.summary.strip():
        raise HTTPException(status_code=400, detail="Diary summary cannot be empty")
    entry = local_store.add_diary(req.summary.strip(), req.mood, req.activities)
    # Feed the memory plane: typed diary entries become graph nodes too (F1).
    graph_memory.ingest_diary(
        {"summary": entry["summary"], "mood": entry["mood"], "activities": entry["activities"]},
        date=entry["date"],
        background=True,
    )
    return entry


@app.get("/api/local/tasks")
def local_tasks_list():
    return {"tasks": local_store.list_tasks()}


@app.post("/api/local/tasks")
def local_task_add(req: LocalTaskRequest):
    if not req.title.strip():
        raise HTTPException(status_code=400, detail="Task title cannot be empty")
    return local_store.add_task(req.title.strip(), req.category)


@app.patch("/api/local/tasks/{task_id}")
def local_task_status(task_id: int, req: TaskStatusRequest):
    task = local_store.set_task_status(task_id, req.status)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.delete("/api/local/tasks/{task_id}")
def local_task_delete(task_id: int):
    if not local_store.delete_task(task_id):
        raise HTTPException(status_code=404, detail="Task not found")
    return {"deleted": task_id}


@app.post("/api/memory/ask")
def memory_ask(req: MemoryAskRequest):
    """Ask the knowledge graph directly (powers the Memory panel's ask box)."""
    if not graph_memory.enabled:
        return {"answer": "", "enabled": False}
    answer = graph_memory.retrieve(req.query)
    return {"answer": answer, "enabled": True}


# ── Notion-backed diary + to-do for the dashboard panels ──────────────────────

@app.get("/api/notion/tasks")
def notion_tasks_list():
    return {"tasks": notion_writer.list_tasks()}


@app.post("/api/notion/tasks")
def notion_task_add(req: LocalTaskRequest):
    if not req.title.strip():
        raise HTTPException(status_code=400, detail="Task title cannot be empty")
    page_id = notion_writer.create_task_http(req.title.strip(), category=req.category or "", due_date=req.due_date)
    if not page_id:
        raise HTTPException(status_code=500, detail="Failed to create task in Notion")
    return {"id": page_id, "title": req.title.strip(), "status": "Todo", "done": False,
            "category": req.category, "deadline": req.due_date}


@app.patch("/api/notion/tasks/{page_id}")
def notion_task_toggle(page_id: str, req: TaskDoneRequest):
    if not notion_writer.set_task_done(page_id, req.done):
        raise HTTPException(status_code=500, detail="Failed to update task in Notion")
    return {"id": page_id, "done": req.done}


@app.delete("/api/notion/tasks/{page_id}")
def notion_task_delete(page_id: str):
    if not notion_writer.archive_task(page_id):
        raise HTTPException(status_code=500, detail="Failed to archive task in Notion")
    return {"deleted": page_id}


@app.get("/api/notion/diary")
def notion_diary_list():
    return {"entries": notion_writer.list_diary()}


@app.post("/api/notion/diary")
def notion_diary_add(req: LocalDiaryRequest):
    if not req.summary.strip():
        raise HTTPException(status_code=400, detail="Diary summary cannot be empty")
    page_id = notion_writer.create_diary_http(
        summary=req.summary.strip(),
        mood=req.mood or "Stable",
        activities=req.activities or [],
        date=req.date,
    )
    # feed the memory graph too (F1)
    graph_memory.ingest_diary(
        {"summary": req.summary.strip(), "mood": req.mood, "activities": req.activities or []},
        date=req.date,
        background=True,
    )
    return {"notion_page_id": page_id, "summary": req.summary.strip(), "mood": req.mood,
            "activities": req.activities or [], "date": req.date}


# Serve the frontend directory statically at root path
app.mount("/", StaticFiles(directory=str(PROJECT_ROOT / "frontend"), html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
