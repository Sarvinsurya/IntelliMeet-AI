"""
Database models for IntelliMeet AI
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey, Boolean, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base


class Job(Base):
    """Job posting with requirements and configuration"""
    __tablename__ = "jobs"

    id = Column(String, primary_key=True, index=True)  # job_xxxxx
    title = Column(String, nullable=False)
    description = Column(Text)  # Job requirements/skills
    form_url = Column(String)  # Google Form URL
    sheet_id = Column(String)  # Google Sheet ID
    status = Column(String, default="active")  # active, paused, closed
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Configuration
    min_score = Column(Float, default=70.0)  # Minimum score to schedule interview
    download_existing = Column(Boolean, default=False)
    
    # Relationships
    candidates = relationship("Candidate", back_populates="job", cascade="all, delete-orphan")
    form_watcher = relationship("FormWatcher", back_populates="job", uselist=False, cascade="all, delete-orphan")


class Candidate(Base):
    """Candidate/applicant information"""
    __tablename__ = "candidates"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    job_id = Column(String, ForeignKey("jobs.id"), nullable=False)
    
    # Personal info
    name = Column(String, nullable=False)
    email = Column(String, nullable=False, index=True)
    phone = Column(String)
    
    # Application details
    applied_at = Column(DateTime, default=datetime.utcnow)
    response_id = Column(String, unique=True)  # Unique ID from form response
    
    # Resume
    resume_file_id = Column(String)  # Google Drive file ID
    resume_filename = Column(String)
    resume_path = Column(String)  # Local path to downloaded resume
    resume_text = Column(Text)  # Extracted text from resume
    
    # Scoring
    score = Column(Float)
    score_reason = Column(Text)  # AI explanation
    scored_at = Column(DateTime)
    
    # Status tracking
    status = Column(String, default="new")  # new, scored, interview_scheduled, accepted, declined, hired, rejected
    
    # Relationships
    job = relationship("Job", back_populates="candidates")
    interviews = relationship("Interview", back_populates="candidate", cascade="all, delete-orphan")


class Interview(Base):
    """Scheduled interview information"""
    __tablename__ = "interviews"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False)
    
    # Calendar event details
    calendar_event_id = Column(String, unique=True, index=True)
    meeting_link = Column(String)
    
    # Schedule
    scheduled_start = Column(DateTime, nullable=False)
    scheduled_end = Column(DateTime, nullable=False)
    duration_minutes = Column(Integer, default=30)
    
    # Status
    status = Column(String, default="scheduled")  # scheduled, accepted, declined, completed, cancelled
    response_status = Column(String)  # accepted, declined, tentative, needsAction
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    candidate = relationship("Candidate", back_populates="interviews")


class FormWatcher(Base):
    """Active form watcher configuration"""
    __tablename__ = "form_watchers"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    job_id = Column(String, ForeignKey("jobs.id"), unique=True, nullable=False)
    
    # Form details
    form_id = Column(String, nullable=False)
    form_title = Column(String)
    sheet_id = Column(String, nullable=False)
    sheet_range = Column(String, default="Form Responses 1")
    
    # Field mapping (stored as JSON)
    field_mapping = Column(JSON)  # {"name": "A", "email": "B", "resume": "C"}
    
    # Status
    is_active = Column(Boolean, default=True)
    last_checked = Column(DateTime)
    last_row_processed = Column(Integer, default=1)  # Track last processed row
    
    # Stats
    total_responses = Column(Integer, default=0)
    total_scheduled = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    job = relationship("Job", back_populates="form_watcher")


class ActivityLog(Base):
    """Activity log for audit trail"""
    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    job_id = Column(String, ForeignKey("jobs.id"))
    candidate_id = Column(Integer, ForeignKey("candidates.id"))
    
    # Log details
    action = Column(String, nullable=False)  # form_connected, resume_scored, interview_scheduled, etc.
    description = Column(Text)
    meta_data = Column(JSON)  # Additional data (renamed from metadata to avoid reserved word)
    
    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
