# IntelliMeet AI

**AI-powered HR Automation System for Smart Hiring**

IntelliMeet AI is an intelligent recruitment automation platform that streamlines the hiring process by automatically screening resumes, scoring candidates using AI, and scheduling interviews with qualified applicants.

![IntelliMeet AI](https://img.shields.io/badge/Version-1.0.0-blue)
![Python](https://img.shields.io/badge/Python-3.10+-green)
![React](https://img.shields.io/badge/React-18.3-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-teal)

---

## 🌟 Features

### Core Functionality
- **AI Resume Scoring** - Powered by Groq Cloud (Llama 3.3 70B) for intelligent candidate evaluation
- **Google Forms Integration** - Seamlessly connects to existing Google Forms for application collection
- **Automated Resume Parsing** - Supports PDF and DOCX formats with intelligent text extraction
- **Smart Interview Scheduling** - Automatic calendar integration with Google Calendar
- **Business Hours Logic** - Schedules meetings only during working hours (10 AM - 7:30 PM IST)
- **Real-time Status Updates** - Live polling of form responses and candidate status
- **Email Notifications** - Automatic email invites for scheduled interviews
- **Reschedule Management** - Handles declined interviews and reschedules automatically

### UI/UX
- **Modern Professional Design** - Clean, contemporary interface with Plus Jakarta Sans typography
- **Light/Dark Mode** - Seamless theme switching with user preference storage
- **Responsive Layout** - Works beautifully on desktop and mobile devices
- **Auto-growing Text Inputs** - Smart text areas that expand with content
- **Real-time Feedback** - Live status updates and visual indicators

---

## 🏗️ Architecture

```
IntelliMeet-AI/
├── backend/                 # FastAPI Python backend
│   ├── main.py             # FastAPI application entry point
│   ├── api_forms.py        # Forms API endpoints
│   ├── form_watcher.py     # Google Forms watcher service
│   ├── resume_parser.py    # PDF/DOCX resume parsing
│   ├── llm_scorer.py       # AI scoring with Groq Cloud
│   ├── calendar_scheduler.py # Google Calendar integration
│   ├── requirements.txt    # Python dependencies
│   └── .env               # Environment variables (not in git)
│
├── frontend/               # React + Vite frontend
│   ├── src/               # React components
│   ├── public/            # Static assets
│   ├── index.html         # Main HTML file
│   ├── package.json       # NPM dependencies
│   └── vite.config.js     # Vite configuration
│
├── run_backend.sh         # Backend startup script (Mac/Linux)
├── run_frontend.sh        # Frontend startup script
├── run_dev.sh            # Run both frontend & backend
└── README.md             # This file
```

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.10+** - For backend
- **Node.js 16+** - For frontend
- **Google Cloud Project** - With Forms, Sheets, Drive, and Calendar APIs enabled
- **Groq API Key** - For AI resume scoring

### 1. Clone the Repository

```bash
git clone https://github.com/Sarvinsurya/IntelliMeet-AI.git
cd IntelliMeet-AI
```

### 2. Backend Setup

```bash
cd backend

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Mac/Linux
# OR
.venv\Scripts\activate     # On Windows

# Install dependencies
pip install -r requirements.txt

# Create .env file
cat > .env << EOF
GROQ_API_KEY=your_groq_api_key_here
EOF
```

### 3. Google Cloud Setup

1. **Create Google Cloud Project**
   - Go to [Google Cloud Console](https://console.cloud.google.com)
   - Create a new project (e.g., "IntelliMeet-AI")

2. **Enable Required APIs**
   - Google Forms API
   - Google Sheets API
   - Google Drive API
   - Google Calendar API

3. **Configure OAuth Consent Screen**
   - Go to: APIs & Services → OAuth consent screen
   - Choose **External**
   - Fill in app details:
     - App name: "IntelliMeet AI"
     - User support email: your email
   - Add scopes:
     - `https://www.googleapis.com/auth/spreadsheets.readonly`
     - `https://www.googleapis.com/auth/drive.readonly`
     - `https://www.googleapis.com/auth/forms.responses.readonly`
     - `https://www.googleapis.com/auth/calendar.events`
     - `https://www.googleapis.com/auth/calendar.freebusy`
   - Add your email as a test user

4. **Create OAuth Credentials**
   - Go to: APIs & Services → Credentials
   - Click "+ Create Credentials" → "OAuth 2.0 Client ID"
   - Application type: **Desktop app**
   - Name: "IntelliMeet AI Desktop"
   - Download the JSON file
   - Save it as `backend/credentials.json`

### 4. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install
```

### 5. Run the Application

#### Option A: Run Both (Recommended for Development)
```bash
# From project root
./run_dev.sh
```

#### Option B: Run Separately

**Terminal 1 - Backend:**
```bash
./run_backend.sh
# Backend runs on http://localhost:8000
```

**Terminal 2 - Frontend:**
```bash
./run_frontend.sh
# Frontend runs on http://localhost:3000
```

### 6. Access the Application

- **Frontend:** http://localhost:3000
- **Backend API:** http://localhost:8000
- **API Documentation:** http://localhost:8000/docs

---

## 📖 Usage Guide

### Step 1: Create a Job

1. Click **"+ Add Job"** button
2. Enter job title (e.g., "Junior Data Scientist/Developer")
3. System creates a job card

### Step 2: Configure Job Requirements

1. **Job Skills & Requirements**
   - Describe key skills, qualifications, and experience needed
   - Be specific - AI will score resumes based on these criteria
   - Example: "Python, SQL, 3+ years experience, machine learning, data analysis"

2. **Google Form Link**
   - Create a Google Form for job applications
   - Ensure it has fields for:
     - Name (short answer)
     - Email (email field)
     - Resume Upload (file upload)
   - Open the form in Google Forms
   - Copy the **EDIT** link (ends with `/edit`)
   - Paste it into IntelliMeet AI

3. **Connect Form**
   - Click **"Connect →"** button
   - System automatically:
     - Connects to the response sheet
     - Sets up file watcher
     - Starts monitoring for submissions

### Step 3: Automatic Processing

When a candidate submits the form:

1. **Resume Download** - System automatically downloads the resume from Google Drive
2. **AI Scoring** - Resume is parsed and scored against job requirements using Llama 3.3 70B
3. **Interview Scheduling** - If score meets threshold:
   - Finds next available slot in your calendar
   - Only schedules during business hours (10 AM - 7:30 PM IST)
   - Creates Google Calendar event
   - Sends email invitation to candidate
   - Notifies HR via email

### Step 4: Monitor & Manage

- **Live Status** - Real-time updates on form responses
- **Check Now** - Manual trigger to check for new responses
- **Download Existing** - Process all existing form responses at once
- **Check Responses** - Review interview acceptance/decline status
- **Reschedule** - Automatically find new slots for declined interviews

---

## ⚙️ Configuration

### Environment Variables

Create `backend/.env`:

```env
# Groq Cloud API Key (required)
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxx

# Optional: Customize scoring threshold
MIN_SCORE=70
```

### Business Hours

Edit `backend/calendar_scheduler.py`:

```python
WORK_START_HOUR = 10      # Start time (10 AM)
WORK_START_MINUTE = 0
WORK_END_HOUR = 19        # End time (7 PM)
WORK_END_MINUTE = 30      # 7:30 PM
LATEST_MEETING_START_HOUR = 18    # Latest start (6 PM)
LATEST_MEETING_START_MINUTE = 30  # 6:30 PM
DEFAULT_TZ = "Asia/Kolkata"        # Timezone
```

### Meeting Duration

```python
DEFAULT_DURATION_MINUTES = 30  # Default interview length
```

---

## 🔑 API Endpoints

### Forms Management

- `GET /api/forms` - List all active watchers
- `POST /api/forms/watch` - Connect a new Google Form
- `DELETE /api/forms/{job_id}` - Disconnect a form watcher
- `POST /api/forms/{job_id}/poll` - Manually check for new responses
- `POST /api/forms/{job_id}/download-existing` - Process existing responses

### Interview Management

- `POST /api/forms/check-interview-responses` - Check interview acceptance status
- `POST /api/forms/reschedule` - Reschedule declined interviews

---

## 🛠️ Technology Stack

### Backend
- **FastAPI** - Modern Python web framework
- **Uvicorn** - ASGI server
- **Google APIs** - Forms, Sheets, Drive, Calendar integration
- **Groq Cloud** - AI model hosting (Llama 3.3 70B)
- **PyPDF** - PDF resume parsing
- **python-docx** - DOCX resume parsing
- **pytz** - Timezone handling

### Frontend
- **React 18.3** - UI library
- **Vite 6.0** - Build tool and dev server
- **Vanilla JavaScript** - For form interactions
- **Plus Jakarta Sans** - Modern typography
- **CSS Variables** - Theme management

### Infrastructure
- **Google OAuth 2.0** - Secure authentication
- **Google Cloud Platform** - API services
- **Git** - Version control

---

## 📊 Project Structure

### Backend Components

#### `main.py`
FastAPI application setup, CORS configuration, route mounting.

#### `api_forms.py`
REST API endpoints for form management, polling, and interview scheduling.

#### `form_watcher.py`
Background service that monitors Google Forms responses and triggers processing pipeline.

#### `resume_parser.py`
Extracts text from PDF and DOCX resume files with error handling.

#### `llm_scorer.py`
Interfaces with Groq Cloud API to score resumes using Llama 3.3 70B model.

#### `calendar_scheduler.py`
Google Calendar integration with business hours logic and free/busy checking.

### Frontend Components

#### `index.html`
Single-page application with vanilla JavaScript for form interactions and API calls.

---

## 🐛 Troubleshooting

### Backend Issues

**Problem:** `Port 8000 already in use`
```bash
# Find and kill the process
lsof -ti :8000 | xargs kill -9
```

**Problem:** `Google API authentication failed`
- Delete `backend/token.json`
- Restart backend - browser will open for re-authentication
- Ensure `credentials.json` is from correct Google account

**Problem:** `Drive file not found`
- Ensure form responses are in the same Google account
- Check Drive API is enabled
- Verify file sharing permissions

### Frontend Issues

**Problem:** `Port 3000 already in use`
```bash
# Kill the process
lsof -ti :3000 | xargs kill -9
```

**Problem:** `npm install fails`
```bash
# Clear cache and reinstall
rm -rf node_modules package-lock.json
npm cache clean --force
npm install
```

**Problem:** `API not reachable`
- Ensure backend is running on port 8000
- Check proxy configuration in `vite.config.js`
- Verify CORS settings in `main.py`

---

## 🤝 Contributing

We welcome contributions! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 👨‍💻 Author

**Sarvinsurya**
- GitHub: [@Sarvinsurya](https://github.com/Sarvinsurya)
- Email: sarvinsurya2704@gmail.com

---

## 🙏 Acknowledgments

- **Groq Cloud** - For providing fast AI inference
- **Google Cloud Platform** - For comprehensive API suite
- **FastAPI** - For excellent Python web framework
- **React & Vite** - For modern frontend development

---

## 📚 Additional Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Google Workspace APIs](https://developers.google.com/workspace)
- [Groq Cloud Documentation](https://console.groq.com/docs)
- [React Documentation](https://react.dev/)
- [Vite Documentation](https://vitejs.dev/)

---

**Made with ❤️ by Sarvinsurya | CIT College - Semester 8 AI Laboratory Project**
