# IntelliMeet AI - Database Schema

## Overview

IntelliMeet AI uses **SQLite** with **SQLAlchemy ORM** for data persistence.

Database file: `backend/intellimeet.db`

---

## Tables

### 1. **jobs** - Job Postings

Stores job configurations and requirements.

| Column | Type | Description |
|--------|------|-------------|
| `id` | String (PK) | Job ID (e.g., `job_1234567890`) |
| `title` | String | Job title |
| `description` | Text | Job requirements/skills for AI scoring |
| `form_url` | String | Google Form URL |
| `sheet_id` | String | Google Sheet ID |
| `status` | String | `active`, `paused`, `closed` |
| `min_score` | Float | Minimum score to schedule interview (default: 70.0) |
| `download_existing` | Boolean | Download existing responses on connect |
| `created_at` | DateTime | When job was created |
| `updated_at` | DateTime | Last update timestamp |

**Relationships:**
- One-to-Many with `candidates`
- One-to-One with `form_watchers`

---

### 2. **candidates** - Applicants

Stores candidate information and application details.

| Column | Type | Description |
|--------|------|-------------|
| `id` | Integer (PK) | Auto-increment ID |
| `job_id` | String (FK) | References `jobs.id` |
| `name` | String | Candidate name |
| `email` | String | Email address (indexed) |
| `phone` | String | Phone number |
| `applied_at` | DateTime | Application timestamp |
| `response_id` | String | Unique form response ID |
| `resume_file_id` | String | Google Drive file ID |
| `resume_filename` | String | Original filename |
| `resume_path` | String | Local file path |
| `resume_text` | Text | Extracted resume text |
| `score` | Float | AI-generated score (0-100) |
| `score_reason` | Text | AI explanation for score |
| `scored_at` | DateTime | When scoring was done |
| `status` | String | `new`, `scored`, `interview_scheduled`, `accepted`, `declined`, `hired`, `rejected` |

**Relationships:**
- Many-to-One with `jobs`
- One-to-Many with `interviews`

---

### 3. **interviews** - Scheduled Interviews

Stores interview scheduling information.

| Column | Type | Description |
|--------|------|-------------|
| `id` | Integer (PK) | Auto-increment ID |
| `candidate_id` | Integer (FK) | References `candidates.id` |
| `calendar_event_id` | String | Google Calendar event ID |
| `meeting_link` | String | Google Meet/Calendar link |
| `scheduled_start` | DateTime | Interview start time |
| `scheduled_end` | DateTime | Interview end time |
| `duration_minutes` | Integer | Duration (default: 30) |
| `status` | String | `scheduled`, `accepted`, `declined`, `completed`, `cancelled` |
| `response_status` | String | Calendar response: `accepted`, `declined`, `tentative`, `needsAction` |
| `created_at` | DateTime | When interview was created |
| `updated_at` | DateTime | Last update timestamp |

**Relationships:**
- Many-to-One with `candidates`

---

### 4. **form_watchers** - Active Form Connections

Tracks active Google Form watchers.

| Column | Type | Description |
|--------|------|-------------|
| `id` | Integer (PK) | Auto-increment ID |
| `job_id` | String (FK) | References `jobs.id` (unique) |
| `form_id` | String | Google Form ID |
| `form_title` | String | Form title |
| `sheet_id` | String | Google Sheet ID |
| `sheet_range` | String | Sheet range (default: "Form Responses 1") |
| `field_mapping` | JSON | Column mapping: `{"name": "A", "email": "B", "resume": "C"}` |
| `is_active` | Boolean | Whether watcher is active |
| `last_checked` | DateTime | Last poll timestamp |
| `last_row_processed` | Integer | Last processed row number |
| `total_responses` | Integer | Total responses processed |
| `total_scheduled` | Integer | Total interviews scheduled |
| `created_at` | DateTime | When watcher was created |
| `updated_at` | DateTime | Last update timestamp |

**Relationships:**
- One-to-One with `jobs`

---

### 5. **activity_logs** - Audit Trail

Stores activity history for auditing.

| Column | Type | Description |
|--------|------|-------------|
| `id` | Integer (PK) | Auto-increment ID |
| `job_id` | String (FK) | References `jobs.id` (optional) |
| `candidate_id` | Integer (FK) | References `candidates.id` (optional) |
| `action` | String | Action type (e.g., `form_connected`, `resume_scored`, `interview_scheduled`) |
| `description` | Text | Human-readable description |
| `metadata` | JSON | Additional data |
| `created_at` | DateTime | When action occurred (indexed) |

**Relationships:**
- Many-to-One with `jobs` (optional)
- Many-to-One with `candidates` (optional)

---

## Database Operations

### CRUD Functions (in `crud.py`)

#### Jobs
- `create_job(db, job_id, title, description)`
- `get_job(db, job_id)`
- `get_all_jobs(db, status=None)`
- `update_job(db, job_id, **kwargs)`
- `delete_job(db, job_id)`

#### Candidates
- `create_candidate(db, job_id, name, email, response_id, **kwargs)`
- `get_candidate(db, candidate_id)`
- `get_candidate_by_email(db, job_id, email)`
- `get_candidates_by_job(db, job_id)`
- `update_candidate(db, candidate_id, **kwargs)`

#### Interviews
- `create_interview(db, candidate_id, calendar_event_id, scheduled_start, scheduled_end, **kwargs)`
- `get_interview(db, interview_id)`
- `get_interview_by_event_id(db, calendar_event_id)`
- `get_interviews_by_candidate(db, candidate_id)`
- `update_interview(db, interview_id, **kwargs)`

#### Form Watchers
- `create_form_watcher(db, job_id, form_id, sheet_id, field_mapping, **kwargs)`
- `get_form_watcher(db, job_id)`
- `get_all_active_watchers(db)`
- `update_form_watcher(db, job_id, **kwargs)`
- `deactivate_form_watcher(db, job_id)`

#### Activity Logs
- `create_activity_log(db, action, description, job_id, candidate_id, metadata)`
- `get_activity_logs(db, job_id, candidate_id, limit=100)`

#### Statistics
- `get_job_statistics(db, job_id)` - Returns candidate and interview stats

---

## Example Usage

### Creating a Job

```python
from database import SessionLocal
import crud

db = SessionLocal()

job = crud.create_job(
    db=db,
    job_id="job_1234567890",
    title="Senior Data Scientist",
    description="Python, ML, 5+ years experience"
)

db.close()
```

### Recording a Candidate

```python
candidate = crud.create_candidate(
    db=db,
    job_id="job_1234567890",
    name="John Doe",
    email="john@example.com",
    response_id="resp_123",
    resume_file_id="drive_file_123"
)
```

### Scheduling an Interview

```python
from datetime import datetime, timedelta

interview = crud.create_interview(
    db=db,
    candidate_id=candidate.id,
    calendar_event_id="cal_event_123",
    scheduled_start=datetime.now() + timedelta(days=2),
    scheduled_end=datetime.now() + timedelta(days=2, minutes=30),
    meeting_link="https://meet.google.com/abc-defg-hij"
)
```

### Logging Activity

```python
crud.create_activity_log(
    db=db,
    action="interview_scheduled",
    description=f"Interview scheduled for {candidate.name}",
    job_id=job.id,
    candidate_id=candidate.id,
    metadata={"event_id": interview.calendar_event_id}
)
```

---

## Indexes

- `jobs.id` - Primary key index
- `candidates.id` - Primary key index
- `candidates.email` - For fast email lookups
- `candidates.job_id` - For job filtering
- `interviews.calendar_event_id` - For calendar sync
- `form_watchers.job_id` - Unique constraint
- `activity_logs.created_at` - For time-based queries

---

## Database Initialization

Run once to create all tables:

```bash
cd backend
python init_database.py
```

Or programmatically:

```python
from database import init_db
init_db()
```

---

## Migration Strategy

For future schema changes, use **Alembic**:

```bash
# Initialize Alembic (one-time)
alembic init alembic

# Create migration
alembic revision --autogenerate -m "Add new column"

# Apply migration
alembic upgrade head
```

---

## Backup & Restore

### Backup
```bash
cp backend/intellimeet.db backend/intellimeet_backup_$(date +%Y%m%d).db
```

### Restore
```bash
cp backend/intellimeet_backup_20260414.db backend/intellimeet.db
```

---

## SQLite Browser

To view/edit the database visually:

1. Install DB Browser for SQLite: https://sqlitebrowser.org/
2. Open `backend/intellimeet.db`
3. Browse tables, run queries, export data

---

## Performance Tips

1. **Indexes** - Already created on frequently queried columns
2. **Batch Operations** - Use `db.bulk_insert_mappings()` for multiple inserts
3. **Connection Pooling** - Handled automatically by SQLAlchemy
4. **Query Optimization** - Use `joinedload()` for eager loading relationships

---

## Future Enhancements

- [ ] Add full-text search on resume_text
- [ ] Implement soft deletes (is_deleted flag)
- [ ] Add created_by/updated_by user tracking
- [ ] Store email templates and history
- [ ] Add candidate notes/comments
- [ ] Track interview feedback/ratings
