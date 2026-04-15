#!/bin/bash
# Development startup script for IntelliMeet AI
# Runs both backend and frontend concurrently

echo "🚀 Starting IntelliMeet AI Development Environment..."
echo ""

# Get the script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "🛑 Shutting down services..."
    kill $(jobs -p) 2>/dev/null
    exit
}

trap cleanup SIGINT SIGTERM

# Start backend
echo "📦 Starting Backend (FastAPI on port 8000)..."
cd "$SCRIPT_DIR/backend"

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv .venv
fi

# Activate virtual environment
source .venv/bin/activate

# Install requirements
echo "Installing Python dependencies..."
.venv/bin/pip install -r requirements.txt -q

# Run backend in background
echo "✅ Backend starting..."
.venv/bin/python main.py &
BACKEND_PID=$!

# Wait a bit for backend to start
sleep 3

# Start frontend
echo ""
echo "🎨 Starting Frontend (Vite on port 3000)..."
cd "$SCRIPT_DIR/frontend"

# Install npm packages if node_modules doesn't exist
if [ ! -d "node_modules" ]; then
    echo "Installing npm dependencies..."
    npm install
fi

echo "✅ Frontend starting..."
npm run dev &
FRONTEND_PID=$!

# Wait for both processes
echo ""
echo "✨ Development environment is ready!"
echo ""
echo "📍 Backend API:  http://localhost:8000"
echo "📍 Frontend UI:  http://localhost:3000"
echo "📍 API Docs:     http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop both services"
echo ""

# Wait for any process to exit
wait
