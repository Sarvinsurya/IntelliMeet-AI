#!/bin/bash
# Mac/Linux startup script for IntelliMeet AI

cd "$(dirname "$0")/backend" || exit 1
echo "Running IntelliMeet AI backend from: $(pwd)"

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate virtual environment
source .venv/bin/activate

# Install requirements
echo "Installing requirements..."
.venv/bin/pip install -r requirements.txt -q

# Run the application
echo "Starting IntelliMeet AI..."
.venv/bin/python main.py
