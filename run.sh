#!/usr/bin/env bash
set -e

# Change directory to the repository root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check if virtual environment exists
if [ -d ".venv" ]; then
    PYTHON_EXEC=".venv/bin/python"
elif [ -d "venv" ]; then
    PYTHON_EXEC="venv/bin/python"
else
    echo "Error: Virtual environment (.venv or venv) not found."
    echo "Create one and install dependencies with:"
    echo "  python3 -m venv .venv"
    echo "  .venv/bin/pip install -r requirements.txt"
    exit 1
fi

exec "$PYTHON_EXEC" main.py "$@"
