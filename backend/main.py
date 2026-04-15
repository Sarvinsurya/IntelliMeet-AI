"""
backend/main.py
===============
FastAPI entry point.
Run:  python main.py
  or: uvicorn main:app --reload --port 8000

Loads .env from this directory (e.g. GROQ_API_KEY for resume scoring).
NOTE: Route registration order matters in FastAPI.
  - API router must be included BEFORE app.mount()
  - app.mount() creates a sub-application that captures ALL unmatched paths
"""

import logging
import os
from pathlib import Path

# Load .env so GROQ_API_KEY (and others) are available
try:
    from dotenv import load_dotenv
    _env = Path(__file__).resolve().parent / ".env"
    if _env.exists():
        load_dotenv(_env)
except ImportError:
    pass

# Log whether Groq LLM will be available (so user sees it in terminal)
_key = os.environ.get("GROQ_API_KEY", "")
if _key:
    _mask = f"{_key[:7]}...{_key[-4:]}" if len(_key) > 12 else "***"
    print(f"  GROQ_API_KEY loaded ({_mask}) — resume scoring will use LLM when job skills are set.")
else:
    print("  GROQ_API_KEY not set — resume scoring will use keyword fallback only.")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from api_forms import router as forms_router
from api_analytics import router as analytics_router
from database import init_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-7s | %(name)s - %(message)s")
logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(exist_ok=True)

app = FastAPI(
    title="IntelliMeet AI",
    description="AI-powered HR automation: watches Google Forms, scores resumes with AI, schedules interviews automatically.",
    version="1.0.0",
    openapi_tags=[
        {"name": "Forms", "description": "**Forms API** — Connect form, list watchers, check interview responses, job config. Start with `GET /api/forms` to verify, then `POST /api/forms/watch` to connect a Google Form."},
        {"name": "Analytics", "description": "**Analytics API** — Get statistics, reports, and insights about jobs and candidates."},
    ],
)

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    """Initialize database and restart active watchers when server starts"""
    from database import SessionLocal
    import crud
    from form_watcher import watcher_registry
    from api_forms import on_new_response, job_config
    
    init_db()
    logger.info("✅ Database initialized successfully")
    
    # Restart active watchers from database
    db = SessionLocal()
    try:
        active_watchers = crud.get_all_active_watchers(db)
        logger.info(f"Found {len(active_watchers)} active watchers to restart")
        
        for watcher in active_watchers:
            try:
                job = crud.get_job(db, watcher.job_id)
                if not job or not watcher.form_id:
                    logger.warning(f"Skipping watcher {watcher.job_id} - missing job or form_id")
                    continue
                
                # Reconstruct the form URL from form_id
                form_url = f"https://docs.google.com/forms/d/{watcher.form_id}/edit"
                
                # Restore job config from database
                job_config[watcher.job_id] = {
                    "job_description": job.description or "",
                    "keywords": [],
                    "threshold": job.min_score or 70.0,
                    "calendar_id": "primary",
                    "meeting_duration_minutes": 30,
                    "interviewer_email": None,
                }
                
                # Restart the watcher
                logger.info(f"Restarting watcher for job {watcher.job_id} ({watcher.form_title})")
                await watcher_registry.add(
                    form_url=form_url,
                    job_id=watcher.job_id,
                    callback=on_new_response,
                    poll_every=60,
                    download_existing=False
                )
                logger.info(f"✅ Watcher restarted: {watcher.job_id}")
            except Exception as e:
                logger.error(f"Failed to restart watcher {watcher.job_id}: {e}")
                # Mark as inactive if restart fails
                crud.update_form_watcher(db, watcher.job_id, is_active=False)
        
        logger.info(f"✅ Restarted {len([w for w in active_watchers])} watchers")
    except Exception as e:
        logger.error(f"Error restarting watchers: {e}")
    finally:
        db.close()

# ── CORS (allow all origins) ──────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 1. API routes FIRST (before any mount) ────────────────────────────────
app.include_router(forms_router)
app.include_router(analytics_router)

# ── 2. Health / root endpoints BEFORE mount ───────────────────────────────
@app.get("/health")
async def health():
    return {"ok": True}


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the frontend UI."""
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return HTMLResponse(index_file.read_text(encoding="utf-8"))
    return HTMLResponse(
        "<h1>IntelliMeet AI is running</h1>"
        "<p>Visit <a href='/docs'>/docs</a> for API docs.</p>"
    )


# ── 3. Static file mount LAST ─────────────────────────────────────────────
# IMPORTANT: mount() must come after all @app.get/@app.post routes
# because it acts as a catch-all sub-application.
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


if __name__ == "__main__":
    import uvicorn
    # Disable reload on Windows to avoid subprocess KeyboardInterrupt tracebacks during file watch
    use_reload = os.name != "nt"
    logger.info("Starting server -> http://localhost:8000")
    logger.info("  Frontend : http://localhost:8000")
    logger.info("  API docs : http://localhost:8000/docs")
    logger.info("  Uploads  : backend/uploads/")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=use_reload)

