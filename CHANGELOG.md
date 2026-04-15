# IntelliMeet AI - Changelog

## Latest Updates (April 14, 2026)

### ✅ Database Integration Complete
- **SQLite database** storing all jobs, candidates, interviews, and form watchers
- **Persistent storage** across browser refreshes and server restarts
- **Cross-browser support** - data syncs across all browsers

### ✅ Job Management Improvements
- Jobs now created in database when you click "+ Add Job"
- **Job title preserved** - no longer overwritten by Google Form title
- Form title stored separately in `form_watchers` table
- Delete functionality integrated with database

### ✅ Real-time Status Updates
- Status refreshes every **5 seconds** (not 10 seconds)
- **Immediate status update** when connecting a form (no more "pending...")
- `last_checked` timestamp updates automatically

### ✅ Meeting Scheduling Logic
- **Business hours**: 10:00 AM to 7:30 PM IST
- **Latest meeting start**: 6:30 PM (for 60-min meetings)
- **5-minute buffer** between consecutive meetings
  - If meeting ends at 11:00 AM, next meeting starts at 11:05 AM
  - Prevents back-to-back interviews

### ✅ Auto-restart Watchers
- Active watchers automatically restart when backend restarts
- No need to reconnect forms after server restart

### 🗄️ Database Schema
- **jobs** - Job postings
- **candidates** - Applicant information  
- **interviews** - Scheduled interviews
- **form_watchers** - Active form polling configuration
- **activity_logs** - Audit trail

### 🔄 Data Flow
1. Create job → Saved to database with user's title
2. Connect Google Form → Watcher starts, marked active in DB
3. Form polling → Every 60 seconds for new responses
4. Status updates → Every 5 seconds in frontend
5. Meeting scheduling → Respects business hours + 5-min buffer
6. Refresh browser → Loads from database, watchers auto-restart

### 📝 Known Configuration
- **Backend**: http://localhost:8000
- **Frontend**: http://localhost:3000 (via Vite)
- **Database**: backend/intellimeet.db (SQLite)
- **Timezone**: Asia/Kolkata (IST)
- **Meeting buffer**: 5 minutes
