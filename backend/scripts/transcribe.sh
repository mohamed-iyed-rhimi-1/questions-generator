#!/bin/bash
# Wrapper script to run manual transcription with virtual environment

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
BACKEND_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"

# Check if virtual environment exists
if [ ! -d "$BACKEND_DIR/venv" ]; then
    echo "Error: Virtual environment not found at $BACKEND_DIR/venv"
    echo "Please create it first with: python -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# Activate virtual environment and run script
cd "$BACKEND_DIR"
source venv/bin/activate
python scripts/manual_transcribe.py "$@"
