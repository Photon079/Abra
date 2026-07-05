"""Abra entrypoint. Run from the repo root:  python run.py

Registers Coral sources + refreshes Strava token at import (via app.main),
then serves the FastAPI app and the frontend dashboard on :8000.
"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=False)
