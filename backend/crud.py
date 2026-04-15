"""
CRUD operations for database models
"""
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime
import models


# ==================== JOB OPERATIONS ====================

def create_job(db: Session, job_id: str, title: str, description: str = None) -> models.Job:
    """Create a new job"""
    db_job = models.Job(
        id=job_id,
        title=title,
        description=description,
        status="active"
    )
    db.add(db_job)
    db.commit()
    db.refresh(db_job)
    return db_job


def get_job(db: Session, job_id: str) -> Optional[models.Job]:
    """Get job by ID"""
    return db.query(models.Job).filter(models.Job.id == job_id).first()


def get_all_jobs(db: Session, status: str = None) -> List[models.Job]:
    """Get all jobs, optionally filtered by status"""
    query = db.query(models.Job)
    if status:
        query = query.filter(models.Job.status == status)
    return query.order_by(models.Job.created_at.desc()).all()


def update_job(db: Session, job_id: str, **kwargs) -> Optional[models.Job]:
    """Update job fields"""
    job = get_job(db, job_id)
    if job:
        for key, value in kwargs.items():
            setattr(job, key, value)
        job.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(job)
    return job


def delete_job(db: Session, job_id: str) -> bool:
    """Delete a job and all related data"""
    job = get_job(db, job_id)
    if job:
        db.delete(job)
        db.commit()
        return True
    return False


# ==================== CANDIDATE OPERATIONS ====================

def create_candidate(
    db: Session,
    job_id: str,
    name: str,
    email: str,
    response_id: str = None,
    **kwargs
) -> models.Candidate:
    """Create a new candidate"""
    db_candidate = models.Candidate(
        job_id=job_id,
        name=name,
        email=email,
        response_id=response_id,
        **kwargs
    )
    db.add(db_candidate)
    db.commit()
    db.refresh(db_candidate)
    return db_candidate


def get_candidate(db: Session, candidate_id: int) -> Optional[models.Candidate]:
    """Get candidate by ID"""
    return db.query(models.Candidate).filter(models.Candidate.id == candidate_id).first()


def get_candidate_by_email(db: Session, job_id: str, email: str) -> Optional[models.Candidate]:
    """Get candidate by email for a specific job"""
    return db.query(models.Candidate).filter(
        models.Candidate.job_id == job_id,
        models.Candidate.email == email
    ).first()


def get_candidates_by_job(db: Session, job_id: str) -> List[models.Candidate]:
    """Get all candidates for a job"""
    return db.query(models.Candidate).filter(
        models.Candidate.job_id == job_id
    ).order_by(models.Candidate.applied_at.desc()).all()


def update_candidate(db: Session, candidate_id: int, **kwargs) -> Optional[models.Candidate]:
    """Update candidate fields"""
    candidate = get_candidate(db, candidate_id)
    if candidate:
        for key, value in kwargs.items():
            setattr(candidate, key, value)
        db.commit()
        db.refresh(candidate)
    return candidate


# ==================== INTERVIEW OPERATIONS ====================

def create_interview(
    db: Session,
    candidate_id: int,
    calendar_event_id: str,
    scheduled_start: datetime,
    scheduled_end: datetime,
    **kwargs
) -> models.Interview:
    """Create a new interview"""
    db_interview = models.Interview(
        candidate_id=candidate_id,
        calendar_event_id=calendar_event_id,
        scheduled_start=scheduled_start,
        scheduled_end=scheduled_end,
        **kwargs
    )
    db.add(db_interview)
    db.commit()
    db.refresh(db_interview)
    return db_interview


def get_interview(db: Session, interview_id: int) -> Optional[models.Interview]:
    """Get interview by ID"""
    return db.query(models.Interview).filter(models.Interview.id == interview_id).first()


def get_interview_by_event_id(db: Session, calendar_event_id: str) -> Optional[models.Interview]:
    """Get interview by calendar event ID"""
    return db.query(models.Interview).filter(
        models.Interview.calendar_event_id == calendar_event_id
    ).first()


def get_interviews_by_candidate(db: Session, candidate_id: int) -> List[models.Interview]:
    """Get all interviews for a candidate"""
    return db.query(models.Interview).filter(
        models.Interview.candidate_id == candidate_id
    ).order_by(models.Interview.scheduled_start.desc()).all()


def update_interview(db: Session, interview_id: int, **kwargs) -> Optional[models.Interview]:
    """Update interview fields"""
    interview = get_interview(db, interview_id)
    if interview:
        for key, value in kwargs.items():
            setattr(interview, key, value)
        interview.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(interview)
    return interview


# ==================== FORM WATCHER OPERATIONS ====================

def create_form_watcher(
    db: Session,
    job_id: str,
    form_id: str,
    sheet_id: str,
    field_mapping: dict,
    **kwargs
) -> models.FormWatcher:
    """Create a new form watcher"""
    db_watcher = models.FormWatcher(
        job_id=job_id,
        form_id=form_id,
        sheet_id=sheet_id,
        field_mapping=field_mapping,
        **kwargs
    )
    db.add(db_watcher)
    db.commit()
    db.refresh(db_watcher)
    return db_watcher


def get_form_watcher(db: Session, job_id: str) -> Optional[models.FormWatcher]:
    """Get form watcher by job ID"""
    return db.query(models.FormWatcher).filter(
        models.FormWatcher.job_id == job_id
    ).first()


def get_all_active_watchers(db: Session) -> List[models.FormWatcher]:
    """Get all active form watchers"""
    return db.query(models.FormWatcher).filter(
        models.FormWatcher.is_active == True
    ).all()


def update_form_watcher(db: Session, job_id: str, **kwargs) -> Optional[models.FormWatcher]:
    """Update form watcher fields"""
    watcher = get_form_watcher(db, job_id)
    if watcher:
        for key, value in kwargs.items():
            setattr(watcher, key, value)
        watcher.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(watcher)
    return watcher


def deactivate_form_watcher(db: Session, job_id: str) -> bool:
    """Deactivate a form watcher"""
    watcher = get_form_watcher(db, job_id)
    if watcher:
        watcher.is_active = False
        watcher.updated_at = datetime.utcnow()
        db.commit()
        return True
    return False


# ==================== ACTIVITY LOG OPERATIONS ====================

def create_activity_log(
    db: Session,
    action: str,
    description: str = None,
    job_id: str = None,
    candidate_id: int = None,
    meta_data: dict = None
) -> models.ActivityLog:
    """Create an activity log entry"""
    db_log = models.ActivityLog(
        job_id=job_id,
        candidate_id=candidate_id,
        action=action,
        description=description,
        meta_data=meta_data
    )
    db.add(db_log)
    db.commit()
    db.refresh(db_log)
    return db_log


def get_activity_logs(
    db: Session,
    job_id: str = None,
    candidate_id: int = None,
    limit: int = 100
) -> List[models.ActivityLog]:
    """Get activity logs with optional filters"""
    query = db.query(models.ActivityLog)
    
    if job_id:
        query = query.filter(models.ActivityLog.job_id == job_id)
    if candidate_id:
        query = query.filter(models.ActivityLog.candidate_id == candidate_id)
    
    return query.order_by(models.ActivityLog.created_at.desc()).limit(limit).all()


# ==================== STATISTICS ====================

def get_job_statistics(db: Session, job_id: str) -> dict:
    """Get statistics for a job"""
    job = get_job(db, job_id)
    if not job:
        return None
    
    candidates = get_candidates_by_job(db, job_id)
    
    stats = {
        "total_candidates": len(candidates),
        "scored_candidates": sum(1 for c in candidates if c.score is not None),
        "interviews_scheduled": sum(1 for c in candidates if c.status == "interview_scheduled"),
        "accepted": sum(1 for c in candidates if c.status == "accepted"),
        "declined": sum(1 for c in candidates if c.status == "declined"),
        "average_score": None,
    }
    
    # Calculate average score
    scored = [c.score for c in candidates if c.score is not None]
    if scored:
        stats["average_score"] = sum(scored) / len(scored)
    
    return stats
