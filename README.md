# IntelliMeet AI

AI-powered HR automation system that watches Google Forms, scores resumes using AI, and automatically schedules interviews.

## Quick Start

```bash
cd "/Users/sarvinsurya/Documents/CIT - College/SEM - 8/AI - laboratory/Project/mian"
./run_backend.sh
```

Open browser: **http://localhost:8000**

## What It Does

1. **Monitors Google Forms** - Watches for new job applications
2. **Downloads Resumes** - Automatically from Google Drive
3. **AI Scoring** - Uses Llama 3.3 70B to score resumes (0-100)
4. **Schedules Interviews** - Creates calendar events with Google Meet
5. **Sends Invites** - Emails calendar invites to qualified candidates

## Setup

### Prerequisites
- Python 3.10+
- Google Cloud account

### Google Cloud Setup
1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create project
3. Enable APIs: Forms, Sheets, Drive, Calendar
4. Create OAuth credentials (Desktop app)
5. Download as `credentials.json` → place in `backend/` folder

### First Run
```bash
./run_backend.sh
```
- Browser opens for Google authentication
- Sign in and grant permissions
- Server starts on http://localhost:8000

## How to Use

1. **Create Google Form** with Name, Email, Resume upload fields
2. **In Google Forms**: Responses tab → Click green Sheets icon
3. **In IntelliMeet AI**: 
   - Add job
   - Paste job description
   - Paste form EDIT URL
   - Click "Connect"
4. **Submit test response** to your form
5. **Watch it work** - Check terminal, calendar, and email

## Configuration

- **Groq API Key**: Set in `backend/.env` for AI scoring (free at https://console.groq.com)
- **Threshold**: Default 50 (candidates scoring ≥50 get interviews)
- **Meeting Duration**: Default 30 minutes

## Output

- **Resumes**: `backend/uploads/`
- **Results**: `backend/upload_results/*.json` (scores, event details)

## Troubleshooting

**"MISSING credentials.json"**
→ Create OAuth credentials in Google Cloud Console

**"Form has no linked response sheet"**
→ In Google Forms: Responses → green Sheets icon

**Port 8000 in use**
```bash
lsof -i :8000
kill -9 <PID>
```

## Tech Stack

- **Backend**: FastAPI, Python 3.10+
- **AI**: Groq (Llama 3.3 70B)
- **APIs**: Google Forms, Sheets, Drive, Calendar
- **Parsing**: pypdf, python-docx

---

**CIT College - Semester 8 - AI Laboratory Project**
