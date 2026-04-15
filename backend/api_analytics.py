"""
Analytics and Reporting API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from datetime import datetime, timedelta

from database import get_db
import crud
import models

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])


@router.get("/jobs/{job_id}/stats")
def get_job_stats(job_id: str, db: Session = Depends(get_db)):
    """
    Get comprehensive statistics for a job
    
    Returns:
    - Total candidates
    - Scored candidates
    - Interviews scheduled
    - Acceptance rate
    - Average score
    - Status breakdown
    """
    job = crud.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    stats = crud.get_job_statistics(db, job_id)
    candidates = crud.get_candidates_by_job(db, job_id)
    
    # Status breakdown
    status_breakdown = {}
    for candidate in candidates:
        status = candidate.status or "new"
        status_breakdown[status] = status_breakdown.get(status, 0) + 1
    
    # Calculate acceptance rate
    total_interviews = stats["interviews_scheduled"]
    accepted = stats["accepted"]
    acceptance_rate = (accepted / total_interviews * 100) if total_interviews > 0 else 0
    
    # Score distribution
    scores = [c.score for c in candidates if c.score is not None]
    score_distribution = {
        "90-100": sum(1 for s in scores if s >= 90),
        "80-89": sum(1 for s in scores if 80 <= s < 90),
        "70-79": sum(1 for s in scores if 70 <= s < 80),
        "60-69": sum(1 for s in scores if 60 <= s < 70),
        "0-59": sum(1 for s in scores if s < 60),
    }
    
    return {
        "job": {
            "id": job.id,
            "title": job.title,
            "status": job.status,
            "created_at": job.created_at.isoformat(),
        },
        "stats": {
            **stats,
            "acceptance_rate": round(acceptance_rate, 2),
            "status_breakdown": status_breakdown,
            "score_distribution": score_distribution,
        }
    }


@router.get("/jobs/{job_id}/candidates")
def get_job_candidates(
    job_id: str,
    status: str = None,
    min_score: float = None,
    db: Session = Depends(get_db)
):
    """
    Get all candidates for a job with optional filters
    
    Query params:
    - status: Filter by candidate status
    - min_score: Filter by minimum score
    """
    job = crud.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    candidates = crud.get_candidates_by_job(db, job_id)
    
    # Apply filters
    if status:
        candidates = [c for c in candidates if c.status == status]
    if min_score is not None:
        candidates = [c for c in candidates if c.score and c.score >= min_score]
    
    return {
        "job_id": job_id,
        "total": len(candidates),
        "candidates": [
            {
                "id": c.id,
                "name": c.name,
                "email": c.email,
                "applied_at": c.applied_at.isoformat() if c.applied_at else None,
                "score": c.score,
                "status": c.status,
                "resume_filename": c.resume_filename,
            }
            for c in candidates
        ]
    }


@router.get("/jobs/{job_id}/candidate/{candidate_id}")
def get_candidate_details(
    job_id: str,
    candidate_id: int,
    db: Session = Depends(get_db)
):
    """
    Get detailed information about a specific candidate
    """
    candidate = crud.get_candidate(db, candidate_id)
    if not candidate or candidate.job_id != job_id:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    # Get interviews
    interviews = crud.get_interviews_by_candidate(db, candidate_id)
    
    return {
        "candidate": {
            "id": candidate.id,
            "name": candidate.name,
            "email": candidate.email,
            "phone": candidate.phone,
            "applied_at": candidate.applied_at.isoformat() if candidate.applied_at else None,
            "status": candidate.status,
        },
        "resume": {
            "filename": candidate.resume_filename,
            "file_id": candidate.resume_file_id,
            "path": candidate.resume_path,
            "text_preview": candidate.resume_text[:500] if candidate.resume_text else None,
        },
        "scoring": {
            "score": candidate.score,
            "reason": candidate.score_reason,
            "scored_at": candidate.scored_at.isoformat() if candidate.scored_at else None,
        },
        "interviews": [
            {
                "id": i.id,
                "scheduled_start": i.scheduled_start.isoformat(),
                "scheduled_end": i.scheduled_end.isoformat(),
                "duration_minutes": i.duration_minutes,
                "status": i.status,
                "response_status": i.response_status,
                "meeting_link": i.meeting_link,
                "calendar_event_id": i.calendar_event_id,
            }
            for i in interviews
        ]
    }


@router.get("/jobs/{job_id}/timeline")
def get_job_timeline(job_id: str, limit: int = 50, db: Session = Depends(get_db)):
    """
    Get activity timeline for a job
    """
    job = crud.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    logs = crud.get_activity_logs(db, job_id=job_id, limit=limit)
    
    return {
        "job_id": job_id,
        "total": len(logs),
        "activities": [
            {
                "id": log.id,
                "action": log.action,
                "description": log.description,
                "candidate_id": log.candidate_id,
                "created_at": log.created_at.isoformat(),
                "metadata": log.meta_data,
            }
            for log in logs
        ]
    }


@router.get("/dashboard")
def get_dashboard_stats(db: Session = Depends(get_db)):
    """
    Get overall dashboard statistics across all jobs
    """
    jobs = crud.get_all_jobs(db, status="active")
    
    total_candidates = 0
    total_interviews = 0
    total_accepted = 0
    all_scores = []
    
    for job in jobs:
        stats = crud.get_job_statistics(db, job.id)
        total_candidates += stats["total_candidates"]
        total_interviews += stats["interviews_scheduled"]
        total_accepted += stats["accepted"]
        
        # Collect scores
        candidates = crud.get_candidates_by_job(db, job.id)
        for c in candidates:
            if c.score is not None:
                all_scores.append(c.score)
    
    avg_score = sum(all_scores) / len(all_scores) if all_scores else 0
    acceptance_rate = (total_accepted / total_interviews * 100) if total_interviews > 0 else 0
    
    # Recent activity
    recent_logs = crud.get_activity_logs(db, limit=20)
    
    return {
        "summary": {
            "total_jobs": len(jobs),
            "total_candidates": total_candidates,
            "total_interviews": total_interviews,
            "total_accepted": total_accepted,
            "average_score": round(avg_score, 2),
            "acceptance_rate": round(acceptance_rate, 2),
        },
        "jobs": [
            {
                "id": job.id,
                "title": job.title,
                "created_at": job.created_at.isoformat(),
                "stats": crud.get_job_statistics(db, job.id),
            }
            for job in jobs
        ],
        "recent_activity": [
            {
                "action": log.action,
                "description": log.description,
                "job_id": log.job_id,
                "created_at": log.created_at.isoformat(),
            }
            for log in recent_logs[:10]
        ]
    }


@router.get("/reports/daily")
def get_daily_report(days: int = 7, db: Session = Depends(get_db)):
    """
    Get daily report for the last N days
    
    Returns applications, scores, and interviews per day
    """
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    # Get all candidates in date range
    all_candidates = db.query(models.Candidate).filter(
        models.Candidate.applied_at >= start_date
    ).all()
    
    # Group by day
    daily_data = {}
    for candidate in all_candidates:
        day = candidate.applied_at.date().isoformat()
        if day not in daily_data:
            daily_data[day] = {
                "date": day,
                "applications": 0,
                "scored": 0,
                "interviews_scheduled": 0,
                "total_score": 0,
                "score_count": 0,
            }
        
        daily_data[day]["applications"] += 1
        if candidate.score is not None:
            daily_data[day]["scored"] += 1
            daily_data[day]["total_score"] += candidate.score
            daily_data[day]["score_count"] += 1
        if candidate.status == "interview_scheduled":
            daily_data[day]["interviews_scheduled"] += 1
    
    # Calculate averages
    report = []
    for day, data in sorted(daily_data.items()):
        avg_score = (data["total_score"] / data["score_count"]) if data["score_count"] > 0 else 0
        report.append({
            "date": data["date"],
            "applications": data["applications"],
            "scored": data["scored"],
            "interviews_scheduled": data["interviews_scheduled"],
            "average_score": round(avg_score, 2),
        })
    
    return {
        "period": {
            "start_date": start_date.date().isoformat(),
            "end_date": end_date.date().isoformat(),
            "days": days,
        },
        "daily_report": report,
        "totals": {
            "applications": sum(d["applications"] for d in report),
            "scored": sum(d["scored"] for d in report),
            "interviews_scheduled": sum(d["interviews_scheduled"] for d in report),
        }
    }


@router.get("/reports/top-candidates")
def get_top_candidates(limit: int = 10, job_id: str = None, db: Session = Depends(get_db)):
    """
    Get top scoring candidates
    
    Query params:
    - limit: Number of candidates to return (default: 10)
    - job_id: Filter by specific job (optional)
    """
    query = db.query(models.Candidate).filter(
        models.Candidate.score.isnot(None)
    )
    
    if job_id:
        query = query.filter(models.Candidate.job_id == job_id)
    
    top_candidates = query.order_by(
        models.Candidate.score.desc()
    ).limit(limit).all()
    
    return {
        "total": len(top_candidates),
        "job_id": job_id,
        "candidates": [
            {
                "id": c.id,
                "name": c.name,
                "email": c.email,
                "job_id": c.job_id,
                "score": c.score,
                "status": c.status,
                "applied_at": c.applied_at.isoformat() if c.applied_at else None,
                "resume_filename": c.resume_filename,
            }
            for c in top_candidates
        ]
    }
