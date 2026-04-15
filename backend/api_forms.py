"""
backend/api_forms.py
====================
The API endpoint HR hits when they paste a Google Form link.
When a new response arrives, resume is auto-downloaded from the form and saved.
"""
import logging
from pathlib import Path
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from form_watcher import watcher_registry
from database import get_db
import crud
from datetime import datetime

_log = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parent
UPLOADS_DIR = BACKEND_DIR / "uploads"
RESULTS_DIR = BACKEND_DIR / "upload_results"  # Parse + score results per resume

# Per-job config: job_id -> { "job_description", "keywords", "threshold", "calendar_id", "meeting_duration_minutes" }
job_config: dict = {}

router = APIRouter(prefix="/api/forms", tags=["Forms"])


@router.get("", summary="Forms API check", responses={200: {"content": {"application/json": {}, "text/html": {}}}})
async def forms_api_root(request: Request):
    """Confirm Forms API is mounted. Returns HTML in browser, JSON for API clients."""
    # Browser address bar sends Accept: text/html; fetch() sends */* — show HTML only for browser
    accept = (request.headers.get("accept") or "").strip().lower()
    want_json = request.query_params.get("json") == "1"
    if not want_json and accept.startswith("text/html"):
        html = """
        <!DOCTYPE html>
        <html><head><meta charset="utf-8"><title>Forms API</title>
        <style>body{font-family:system-ui;max-width:600px;margin:40px auto;padding:20px;background:#0f0f1a;color:#e2e8f0;}
        a{color:#818cf8;} h1{color:#a5b4fc;} .box{background:rgba(255,255,255,0.05);border-radius:12px;padding:16px;margin:12px 0;}
        code{background:rgba(0,0,0,0.3);padding:2px 6px;border-radius:4px;}</style></head>
        <body>
        <h1>Forms API is running</h1>
        <p>Use this API to connect Google Forms, score resumes, and schedule interviews from the HR calendar.</p>
        <div class="box">
        <strong>Step 1 — Main app</strong><br>
        <a href="/">Open the FormWatcher app</a> (add job, paste form link, connect).
        </div>
        <div class="box">
        <strong>Step 2 — API docs</strong><br>
        <a href="/docs">Open Swagger docs</a> to see all endpoints (watch, watchers, check-interview-responses, etc.).
        </div>
        <div class="box">
        <strong>Step 3 — HR calendar & candidate invite</strong><br>
        When a candidate scores above threshold, the system finds a free slot on <b>your (HR) Google Calendar</b>,
        creates the meeting there (with Google Meet), and <b>sends a calendar invite by email to the candidate</b> using the <b>email from your Google Form</b>. The meeting is visible in your calendar; the candidate gets an email and, when they accept, the event appears on their calendar (no access to their calendar needed). Ensure your form has a question titled e.g. <b>Email</b> or <b>Email address</b> so we can detect it and invite them. Open the event link in <code>backend/upload_results/*_result.json</code> (scheduled_event.event_link) or the link printed in the terminal.         If the <b>candidate or the interviewer</b> declines, use
        <code>POST /api/forms/check-interview-responses</code> to reschedule and send a new invite. Optionally set <code>interviewer_email</code> in job config (or in the watch body) so the interviewer is added as an attendee and can trigger reschedule if they decline.
        </div>
        <p><a href="/api/forms?json=1">View as JSON</a></p>
        </body></html>
        """
        return HTMLResponse(html)
    return JSONResponse({"ok": True, "api": "forms", "message": "Forms API is running. Use POST /api/forms/watch to connect a form."})


class WatchRequest(BaseModel):
    form_url: str                # HR pastes this
    job_id: str                  # Which job this form is for
    poll_every: int = 60
    download_existing: bool = False
    job_description: str = ""    # HR's job description; resume is scored against this (LLM or keyword fallback)
    job_keywords: list[str] = []  # Optional: explicit keywords; if job_description set, LLM uses it
    score_threshold: float = 50   # Min score 0-100 to pass
    interviewer_email: str = ""  # Optional: add as attendee so if interviewer declines we reschedule too


def _sanitize_filename(name: str) -> str:
    """Safe filename from candidate name."""
    if not name or not name.strip():
        return "candidate"
    return "".join(c if c.isalnum() or c in " -_." else "_" for c in name.strip())[:50].strip() or "candidate"


def _sanitize_resume_filename(name: str) -> str:
    """Safe filename for uploaded resume (allow dots for extension)."""
    if not name or not name.strip():
        return ""
    # Strip path if present, keep only base name
    base = name.strip().replace("\\", "/").split("/")[-1]
    # Allow letters, digits, spaces, hyphen, underscore, dot
    safe = "".join(c if c.isalnum() or c in " ._-" else "_" for c in base)[:120].strip()
    return safe if safe else ""


# ── what happens when a new response arrives ──────────────────────────────
async def on_new_response(response, resume_bytes, resume_filename, job_id):
    """
    Fires for every form response. Saves resume, then parses it and scores against threshold.
    Now also saves candidate and interview to database.
    Returns: True if processed successfully, False if skipped (duplicate)
    """
    import json
    import uuid
    from database import SessionLocal
    import crud

    name = response.get("name") or response.get("email") or "candidate"
    row = response.get("row_number", "")
    email = response.get("email", "")

    # Check if this candidate was already processed (prevent duplicates)
    db = SessionLocal()
    try:
        existing_candidate = crud.get_candidate_by_email(db, job_id, email) if email else None
        if existing_candidate:
            _log.info(f"SKIP: Candidate {name} ({email}) already processed for job {job_id}")
            return False  # Return False to indicate duplicate was skipped
    finally:
        db.close()

    sheet_filename = _sanitize_resume_filename(response.get("resume_filename_from_sheet") or "")
    file_to_save = sheet_filename or resume_filename

    _log.info(
        "FORM RESPONSE (row #%s) Name=%s Email=%s Job=%s Resume=%s (%s)",
        row, response.get("name", ""), response.get("email", ""), job_id, file_to_save,
        "downloaded" if resume_bytes else "missing",
    )

    saved_path = None
    if resume_bytes:
        UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        safe_name = _sanitize_filename(name)
        short_id = uuid.uuid4().hex[:8]
        saved_path = UPLOADS_DIR / f"{safe_name}_{row}_{short_id}_{file_to_save}"
        with open(saved_path, "wb") as f:
            f.write(resume_bytes)
        _log.info("Resume saved -> %s", saved_path)

        # Parse resume and score against job description (LLM) or keywords + threshold
        try:
            from resume_parser import parse_resume, evaluate_resume
            config = job_config.get(job_id, {})
            job_description = (config.get("job_description") or "").strip()
            keywords = config.get("keywords", [])
            threshold = config.get("threshold", 50)

            parsed = parse_resume(resume_bytes, file_to_save)
            response["resume_parse"] = parsed

            if job_description:
                # Score using LLM (or keyword fallback from JD) against job description
                from llm_scorer import score_resume_with_llm
                llm_result = score_resume_with_llm(job_description, parsed["text"], threshold=threshold)
                response["resume_score"] = {
                    "score": llm_result["score"],
                    "above_threshold": llm_result["above_threshold"],
                    "reasoning": llm_result.get("reasoning", ""),
                    "source": llm_result.get("source", "llm"),
                    "matched": llm_result.get("matched_keywords", []),
                    "missing": llm_result.get("missing_keywords", []),
                }
                response["above_threshold"] = llm_result["above_threshold"]
                response["score_threshold"] = threshold
                _log.info(
                    "Resume (job-description): score=%s threshold=%s above=%s source=%s",
                    llm_result["score"], threshold, llm_result["above_threshold"], llm_result.get("source"),
                )
            else:
                result = evaluate_resume(resume_bytes, file_to_save, keywords=keywords, threshold=threshold)
                parsed = result["parse"]
                response["resume_parse"] = parsed
                response["resume_score"] = {**result["score"], "reasoning": "", "source": "keywords"}
                response["above_threshold"] = result["above_threshold"]
                response["score_threshold"] = result["threshold"]
                _log.info(
                    "Resume (keywords): score=%s threshold=%s above=%s matched=%s",
                    result["score"]["score"], threshold, result["above_threshold"], result["score"].get("matched", []),
                )

            # Save result JSON
            RESULTS_DIR.mkdir(parents=True, exist_ok=True)
            result_path = RESULTS_DIR / f"{safe_name}_{row}_{short_id}_result.json"
            scr = response["resume_score"]
            save_obj = {
                "name": name,
                "email": response.get("email"),
                "row": row,
                "job_id": job_id,
                "resume_file": str(saved_path),
                "parse_ok": parsed["parse_ok"],
                "word_count": parsed["word_count"],
                "score": scr.get("score"),
                "threshold": threshold,
                "above_threshold": response["above_threshold"],
                "reasoning": scr.get("reasoning", ""),
                "source": scr.get("source", "keywords"),
                "matched_keywords": scr.get("matched", scr.get("matched_keywords", [])),
                "missing_keywords": scr.get("missing", scr.get("missing_keywords", [])),
            }

            # If above threshold: find free slot on HR calendar and schedule interview
            if response["above_threshold"]:
                calendar_id = config.get("calendar_id") or "primary"
                meeting_mins = config.get("meeting_duration_minutes", 30)
                candidate_email = (response.get("email") or "").strip()
                calendar_event_id = None
                scheduled_time = None
                
                try:
                    from form_watcher import get_google_creds
                    from calendar_scheduler import schedule_interview
                    creds = get_google_creds()
                    schedule_result = schedule_interview(
                        creds, calendar_id=calendar_id,
                        candidate_name=name, candidate_email=candidate_email, job_id=job_id,
                        duration_minutes=meeting_mins,
                        interviewer_email=config.get("interviewer_email"),
                    )
                    save_obj["scheduled_event"] = schedule_result
                    if schedule_result.get("ok"):
                        save_obj["reschedule_count"] = 0
                        calendar_event_id = schedule_result.get("event_id")
                        scheduled_time = schedule_result.get("start")
                    if schedule_result.get("ok") and schedule_result.get("event_link"):
                        print(f"  In HR calendar: {schedule_result['event_link']}")
                        if schedule_result.get("meet_link"):
                            print(f"  Google Meet : {schedule_result['meet_link']}")
                        print(f"  Time: {schedule_result.get('start')} – {schedule_result.get('end')}")
                        if candidate_email:
                            print(f"  Candidate invite sent to: {candidate_email} (they get email; no access to their calendar needed)")
                    else:
                        _log.warning("Could not schedule interview: %s", schedule_result.get("error"))
                except Exception as cal_e:
                    _log.warning("Calendar schedule failed: %s", cal_e)
                    save_obj["scheduled_event"] = {"ok": False, "error": str(cal_e)}
                
                # Save candidate and interview to database
                db = SessionLocal()
                try:
                    from datetime import datetime
                    
                    # Create candidate record
                    candidate = crud.create_candidate(
                        db=db,
                        job_id=job_id,
                        name=name,
                        email=email,
                        phone=response.get("phone", ""),
                        resume_path=str(saved_path) if saved_path else None,
                        score=scr.get("score"),
                        resume_text=parsed.get("text", "") if parsed else None,
                        score_reason=scr.get("reasoning", ""),
                    )
                    _log.info(f"✅ Candidate saved to DB: {name} (ID: {candidate.id})")
                    
                    # Create interview record if scheduled
                    if calendar_event_id and scheduled_time:
                        try:
                            scheduled_dt = datetime.fromisoformat(scheduled_time.replace('Z', '+00:00'))
                            # Calculate end time (add meeting duration)
                            from datetime import timedelta
                            scheduled_end_dt = scheduled_dt + timedelta(minutes=meeting_mins)
                        except:
                            scheduled_dt = datetime.utcnow()
                            from datetime import timedelta
                            scheduled_end_dt = scheduled_dt + timedelta(minutes=meeting_mins)
                        
                        interview = crud.create_interview(
                            db=db,
                            candidate_id=candidate.id,
                            calendar_event_id=calendar_event_id,
                            scheduled_start=scheduled_dt,
                            scheduled_end=scheduled_end_dt,
                            status="scheduled",
                        )
                        _log.info(f"✅ Interview saved to DB: {name} at {scheduled_time}")
                    
                    # Log activity
                    crud.create_activity_log(
                        db=db,
                        action="candidate_processed",
                        description=f"Processed {name} - Score: {scr.get('score')}",
                        job_id=job_id,
                        candidate_id=candidate.id,
                    )
                except Exception as db_e:
                    _log.error(f"Failed to save candidate/interview to DB: {db_e}")
                finally:
                    db.close()

            with open(result_path, "w", encoding="utf-8") as f:
                json.dump(save_obj, f, indent=2, ensure_ascii=False)
            
            # Save candidate to database (even if below threshold or no interview scheduled)
            if not response.get("above_threshold"):
                db = SessionLocal()
                try:
                    # Create candidate record
                    candidate = crud.create_candidate(
                        db=db,
                        job_id=job_id,
                        name=name,
                        email=email,
                        phone=response.get("phone", ""),
                        resume_path=str(saved_path) if saved_path else None,
                        score=scr.get("score"),
                        resume_text=parsed.get("text", "") if parsed else None,
                        score_reason=scr.get("reasoning", ""),
                    )
                    _log.info(f"✅ Candidate saved to DB (below threshold): {name} (ID: {candidate.id})")
                    
                    # Log activity
                    crud.create_activity_log(
                        db=db,
                        action="candidate_processed",
                        description=f"Processed {name} - Score: {scr.get('score')} (below threshold)",
                        job_id=job_id,
                        candidate_id=candidate.id,
                    )
                except Exception as db_e:
                    _log.error(f"Failed to save candidate to DB: {db_e}")
                finally:
                    db.close()

            # Show parse + score in terminal
            scr = response["resume_score"]
            sep = "─" * 60
            print()
            print(sep)
            print("  RESUME PARSE & SCORE")
            print(sep)
            print(f"  Name       : {name}")
            print(f"  Row        : {row}  |  Job ID : {job_id}")
            print(f"  Parse OK   : {parsed['parse_ok']}  |  Word count : {parsed.get('word_count', 0)}")
            print(f"  Score      : {scr.get('score')} / 100  (threshold: {threshold})")
            print(f"  Pass       : {'YES' if response['above_threshold'] else 'NO'}")
            print(f"  Source     : {scr.get('source', 'keywords')}")
            if scr.get("reasoning"):
                print(f"  Reasoning  : {scr['reasoning'][:200]}{'...' if len(scr.get('reasoning', '')) > 200 else ''}")
            matched = scr.get("matched", scr.get("matched_keywords", []))
            missing = scr.get("missing", scr.get("missing_keywords", []))
            if matched:
                print(f"  Matched    : {matched[:12]}{' ...' if len(matched) > 12 else ''}")
            if missing:
                print(f"  Missing    : {missing[:12]}{' ...' if len(missing) > 12 else ''}")
            print(f"  Result file: {result_path.name}")
            if save_obj.get("scheduled_event", {}).get("ok"):
                ev = save_obj["scheduled_event"]
                print(f"  In HR calendar : {ev.get('event_link', '')}")
                print(f"  Time           : {ev.get('start', '')}")
                if ev.get("meet_link"):
                    print(f"  Meet link      : {ev.get('meet_link')}")
            elif save_obj.get("scheduled_event") and not save_obj["scheduled_event"].get("ok"):
                print(f"  Scheduled   : failed — {save_obj['scheduled_event'].get('error', '')}")
            print(sep)
            print()
        except Exception as e:
            _log.warning("Resume parse/score failed: %s", e)
            print(f"  [RESUME ERROR] {name} (row {row}): {e}")
            response["above_threshold"] = None
            response["resume_score"] = None
    
    return True  # Return True to indicate response was processed successfully


@router.post("/watch")
async def start_watching(body: WatchRequest, db: Session = Depends(get_db)):
    """
    HR pastes Google Form link here. Optionally set job_keywords and score_threshold
    to parse resumes and score them (candidate must score >= threshold).
    """
    try:
        # Save job config
        job_config[body.job_id] = {
            "job_description": (body.job_description or "").strip(),
            "keywords": list(body.job_keywords) if body.job_keywords else [],
            "threshold": float(body.score_threshold),
            "calendar_id": getattr(body, "calendar_id", None) or "primary",
            "meeting_duration_minutes": getattr(body, "meeting_duration_minutes", None) or 30,
            "interviewer_email": (getattr(body, "interviewer_email", None) or "").strip() or None,
        }
        
        # Start watching the form
        info = await watcher_registry.add(
            form_url=body.form_url,
            job_id=body.job_id,
            callback=on_new_response,
            poll_every=body.poll_every,
            download_existing=body.download_existing,
        )
        
        # Create or update job in database
        existing_job = crud.get_job(db, body.job_id)
        if not existing_job:
            # If job doesn't exist, create it (shouldn't happen as frontend creates job first)
            job_db = crud.create_job(
                db=db,
                job_id=body.job_id,
                title=info.get('form_title', body.job_id),
                description=body.job_description,
            )
            crud.create_activity_log(
                db=db,
                action="job_created",
                description=f"Job created: {job_db.title}",
                job_id=body.job_id
            )
        else:
            # Update job but KEEP the original title (don't overwrite with form title)
            crud.update_job(
                db=db,
                job_id=body.job_id,
                # title stays the same - we keep user's original job title
                description=body.job_description,
                form_url=body.form_url,
                sheet_id=info.get('sheet_id'),
            )
        
        # Create or update form watcher record in database
        existing_watcher = crud.get_form_watcher(db, body.job_id)
        if not existing_watcher:
            crud.create_form_watcher(
                db=db,
                job_id=body.job_id,
                form_id=info.get('form_id', ''),
                sheet_id=info.get('sheet_id', ''),
                form_title=info.get('form_title', ''),
                field_mapping=info.get('fields', {}),
                is_active=True,  # Mark as active when creating
            )
            crud.create_activity_log(
                db=db,
                action="form_connected",
                description=f"Connected Google Form: {info.get('form_title')}",
                job_id=body.job_id
            )
        else:
            # Update existing watcher to active
            crud.update_form_watcher(
                db=db,
                job_id=body.job_id,
                is_active=True,
                form_title=info.get('form_title', existing_watcher.form_title),
                field_mapping=info.get('fields', existing_watcher.field_mapping),
            )
            crud.create_activity_log(
                db=db,
                action="form_reconnected",
                description=f"Reconnected Google Form: {info.get('form_title')}",
                job_id=body.job_id
            )
        
        _log.info("✅ Job saved to database: %s", body.job_id)
        
        return {
            "status":  "watching",
            "message": f"Now watching '{info['form_title']}' for new responses",
            "job_description": job_config[body.job_id].get("job_description", ""),
            "job_keywords": job_config[body.job_id]["keywords"],
            "score_threshold": job_config[body.job_id]["threshold"],
            **info,
        }
    except FileNotFoundError as e:
        raise HTTPException(400, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Setup failed: {e}")


class CreateJobRequest(BaseModel):
    job_id: str
    title: str
    description: str = ""


@router.post("/jobs")
async def create_job_endpoint(req: CreateJobRequest, db: Session = Depends(get_db)):
    """Create a new job in the database"""
    try:
        # Check if job already exists
        existing = crud.get_job(db, req.job_id)
        if existing:
            return {"ok": True, "job_id": req.job_id, "message": "Job already exists"}
        
        # Create the job
        job = crud.create_job(db, req.job_id, req.title, req.description)
        crud.create_activity_log(
            db=db,
            action="job_created",
            description=f"Job created: {req.title}",
            job_id=req.job_id
        )
        
        _log.info(f"✅ Job created: {req.title} ({req.job_id})")
        
        return {
            "ok": True,
            "job_id": req.job_id,
            "title": req.title,
            "message": "Job created successfully"
        }
    except Exception as e:
        _log.error(f"Failed to create job: {e}")
        raise HTTPException(500, f"Failed to create job: {e}")


@router.get("/jobs")
async def get_all_jobs(db: Session = Depends(get_db)):
    """
    Get all jobs from database with their current status
    """
    jobs_db = crud.get_all_jobs(db)
    
    result = []
    for job_db in jobs_db:
        watcher = crud.get_form_watcher(db, job_db.id)
        stats = crud.get_job_statistics(db, job_db.id)
        
        # Get watcher info from registry if active (convert to dict to avoid serialization issues)
        watcher_info = None
        if job_db.id in watcher_registry._watchers:
            watcher_obj = watcher_registry._watchers[job_db.id]
            watcher_info = watcher_obj.status() if hasattr(watcher_obj, 'status') else None
        
        result.append({
            "job_id": job_db.id,
            "title": job_db.title,
            "description": job_db.description,
            "form_url": job_db.form_url,
            "status": job_db.status,
            "created_at": job_db.created_at.isoformat() if job_db.created_at else None,
            "is_watching": watcher.is_active if watcher else False,
            "form_title": watcher.form_title if watcher else None,
            "last_checked": watcher.last_checked.isoformat() if watcher and watcher.last_checked else None,
            "total_responses": watcher.total_responses if watcher else 0,
            "stats": stats,
            "watcher_info": watcher_info,
        })
    
    return {
        "ok": True,
        "total": len(result),
        "jobs": result
    }


@router.get("/watchers")
async def list_watchers():
    statuses = watcher_registry.all_status()
    for s in statuses:
        jid = s.get("job_id")
        if jid and jid in job_config:
            s["job_description"] = job_config[jid].get("job_description", "")
            s["job_keywords"] = job_config[jid].get("keywords", [])
            s["score_threshold"] = job_config[jid].get("threshold", 50)
    return statuses


@router.delete("/watch/{job_id}")
async def stop_watching(job_id: str, db: Session = Depends(get_db)):
    """Stop watching a form and optionally delete the job from database"""
    # Stop the watcher if it's running
    if watcher_registry.get(job_id):
        await watcher_registry.remove(job_id)
    
    # Remove from in-memory job config
    job_config.pop(job_id, None)
    
    # Deactivate the form watcher in database (don't delete, just mark inactive)
    watcher = crud.get_form_watcher(db, job_id)
    if watcher:
        crud.deactivate_form_watcher(db, job_id)
    
    # Optionally delete the job entirely from database
    # For now, we'll just stop watching but keep the job record
    # If you want to delete: crud.delete_job(db, job_id)
    
    crud.create_activity_log(
        db=db,
        action="watcher_stopped",
        description=f"Stopped watching job {job_id}",
        job_id=job_id
    )
    
    return {"stopped": True, "job_id": job_id}


@router.delete("/jobs/{job_id}")
async def delete_job_endpoint(job_id: str, db: Session = Depends(get_db)):
    """Completely delete a job and all its data from the database"""
    # Stop the watcher if it's running
    if watcher_registry.get(job_id):
        await watcher_registry.remove(job_id)
    
    # Remove from in-memory job config
    job_config.pop(job_id, None)
    
    # Delete from database (this will cascade delete watcher, candidates, interviews, etc.)
    deleted = crud.delete_job(db, job_id)
    
    if not deleted:
        raise HTTPException(404, f"Job {job_id} not found")
    
    crud.create_activity_log(
        db=db,
        action="job_deleted",
        description=f"Deleted job {job_id}",
        job_id=None  # Job is deleted, so no job_id reference
    )
    
    return {"deleted": True, "job_id": job_id}


@router.get("/job-config/{job_id}")
async def get_job_config(job_id: str):
    """Get job config including calendar and meeting duration."""
    c = job_config.get(job_id, {})
    return {
        "job_id": job_id,
        "job_description": c.get("job_description", ""),
        "keywords": c.get("keywords", []),
        "threshold": c.get("threshold", 50),
        "calendar_id": c.get("calendar_id", "primary"),
        "meeting_duration_minutes": c.get("meeting_duration_minutes", 30),
        "interviewer_email": c.get("interviewer_email"),
    }


class JobConfigUpdate(BaseModel):
    job_description: str = ""
    job_keywords: list[str] = []
    score_threshold: float = 50
    calendar_id: str = "primary"
    meeting_duration_minutes: int = 30
    interviewer_email: str | None = None


@router.patch("/job-config/{job_id}")
async def update_job_config(job_id: str, body: JobConfigUpdate):
    """Set job description, keywords and/or threshold for a job."""
    if job_id not in job_config:
        job_config[job_id] = {"job_description": "", "keywords": [], "threshold": 50, "calendar_id": "primary", "meeting_duration_minutes": 30, "interviewer_email": None}
    if body.job_description is not None:
        job_config[job_id]["job_description"] = (body.job_description or "").strip()
    if body.job_keywords is not None:
        job_config[job_id]["keywords"] = list(body.job_keywords)
    if body.score_threshold is not None:
        job_config[job_id]["threshold"] = float(body.score_threshold)
    if body.calendar_id is not None:
        job_config[job_id]["calendar_id"] = body.calendar_id or "primary"
    if body.meeting_duration_minutes is not None:
        job_config[job_id]["meeting_duration_minutes"] = int(body.meeting_duration_minutes)
    if body.interviewer_email is not None:
        job_config[job_id]["interviewer_email"] = (body.interviewer_email or "").strip() or None
    return job_config[job_id]


@router.post("/poll-now/{job_id}")
async def poll_now(job_id: str):
    """Manually trigger one poll (checks for new responses only)."""
    w = watcher_registry.get(job_id)
    if not w:
        raise HTTPException(404, "No watcher for this job")
    await w._poll_once()
    return {"polled": True, "total_processed": w.total_processed}


@router.get("/jobs/{job_id}/candidates")
async def get_job_candidates(job_id: str, db: Session = Depends(get_db)):
    """Get all candidates for a specific job with their interview status"""
    from datetime import datetime, timezone
    
    candidates_data = []
    candidates = crud.get_candidates_by_job(db, job_id)
    
    for candidate in candidates:
        # Get interview info if exists
        interview = None
        interview_status = "rejected"  # default: below threshold
        scheduled_time = None
        interview_time_status = None  # upcoming, starting_soon, completed
        
        if candidate.score and candidate.score >= 50:  # Assuming 50 is threshold
            # Get the latest interview for this candidate
            interviews = db.query(crud.models.Interview).filter(
                crud.models.Interview.candidate_id == candidate.id
            ).order_by(crud.models.Interview.created_at.desc()).all()
            
            if interviews:
                interview = interviews[0]
                interview_status = interview.status
                scheduled_time = interview.scheduled_start
                
                # Determine interview time status
                now = datetime.now(timezone.utc)
                time_diff = (interview.scheduled_start.replace(tzinfo=timezone.utc) - now).total_seconds() / 60
                
                if time_diff < 0:  # Interview time passed
                    interview_time_status = "completed"
                elif time_diff <= 30:  # Within 30 minutes
                    interview_time_status = "starting_soon"
                else:  # Future interview
                    interview_time_status = "upcoming"
        
        candidates_data.append({
            "id": candidate.id,
            "name": candidate.name,
            "email": candidate.email,
            "phone": candidate.phone,
            "score": candidate.score,
            "applied_at": candidate.applied_at.isoformat() if candidate.applied_at else None,
            "interview_status": interview_status,
            "interview_time_status": interview_time_status,
            "scheduled_time": scheduled_time.isoformat() if scheduled_time else None,
        })
    
    return {
        "ok": True,
        "job_id": job_id,
        "candidates": candidates_data
    }


@router.post("/download-existing/{job_id}")
async def download_existing_now(job_id: str):
    """Process all existing responses in the sheet (download their resumes). Use when you have existing rows that were never processed."""
    w = watcher_registry.get(job_id)
    if not w:
        raise HTTPException(404, "No watcher for this job")
    before = w.total_processed
    w.last_row = 1  # Process from first data row
    await w._poll_once()
    added = w.total_processed - before
    return {"ok": True, "processed": added, "total_processed": w.total_processed}


# Max times we reschedule when candidate declines (then stop and leave last invite pending)
MAX_RESCEDULE_ATTEMPTS = 3


@router.post("/check-interview-responses")
async def check_interview_responses():
    """
    Check all scheduled interviews: if the candidate or the interviewer declined,
    find a new slot on HR calendar, create a new event with Meet, send new invite, and cancel the old event.
    Call this periodically (e.g. daily) or from a "Check responses" button.
    """
    import json
    from form_watcher import get_google_creds
    from calendar_scheduler import (
        get_event_any_attendee_declined,
        cancel_event,
        schedule_interview,
    )
    try:
        creds = get_google_creds()
    except Exception as e:
        raise HTTPException(503, f"Calendar not available: {e}")
    checked = 0
    rescheduled = 0
    details = []
    if not RESULTS_DIR.exists():
        return {"checked": 0, "rescheduled": 0, "details": []}
    for path in RESULTS_DIR.glob("*_result.json"):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue
        se = data.get("scheduled_event") or {}
        if not se.get("ok") or not se.get("event_id"):
            continue
        email = (data.get("email") or "").strip()
        if not email:
            continue
        reschedule_count = data.get("reschedule_count", 0)
        if reschedule_count >= MAX_RESCEDULE_ATTEMPTS:
            continue
        job_id = data.get("job_id", "")
        config = job_config.get(job_id, {})
        calendar_id = config.get("calendar_id", "primary")
        meeting_mins = config.get("meeting_duration_minutes", 30)
        name = data.get("name", "Candidate")
        event_id = se["event_id"]
        checked += 1
        any_declined, declined_emails = get_event_any_attendee_declined(creds, calendar_id, event_id)
        if not any_declined:
            details.append({"file": path.name, "email": email, "status": "no_decline"})
            continue
        declined_who = ", ".join(declined_emails) if declined_emails else "attendee"
        # Candidate or interviewer declined: find new slot, create new event, cancel old
        new_result = schedule_interview(
            creds, calendar_id=calendar_id,
            candidate_name=name, candidate_email=email, job_id=job_id,
            duration_minutes=meeting_mins,
            interviewer_email=config.get("interviewer_email"),
        )
        if not new_result.get("ok"):
            details.append({"file": path.name, "email": email, "action": "reschedule_failed", "error": new_result.get("error"), "declined": declined_emails})
            continue
        cancel_event(creds, calendar_id, event_id)
        data["scheduled_event"] = new_result
        data["reschedule_count"] = reschedule_count + 1
        data.setdefault("rescheduled_events", []).append({
            "previous_event_id": event_id,
            "reason": "attendee_declined",
            "declined_emails": declined_emails,
        })
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        rescheduled += 1
        details.append({
            "file": path.name, "email": email, "action": "rescheduled",
            "declined": declined_emails,
            "new_start": new_result.get("start"), "new_meet_link": new_result.get("meet_link"),
        })
        _log.info("Rescheduled interview for %s (declined by: %s) -> %s", email, declined_who, new_result.get("start"))
    return {"checked": checked, "rescheduled": rescheduled, "details": details}
