#!/bin/bash
# Frontend-only startup script for IntelliMeet AI

cd "$(dirname "$0")/frontend"

echo "🎨 Starting IntelliMeet AI Frontend..."
echo ""

# Install dependencies if needed
if [ ! -d "node_modules" ]; then
    echo "📦 Installing npm dependencies..."
    npm install
fi

echo "✅ Starting Vite dev server on port 3000..."
echo "📍 Frontend: http://localhost:3000"
echo ""

npm run dev
