#!/usr/bin/env bash

# Exit immediately on error
set -e

# Log file location
LOG_FILE="logs/server.log"

# Ensure log directory exists
mkdir -p "$(dirname "$LOG_FILE")"

# Launch FastAPI app with uvicorn
uvicorn mcp_server.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --reload \
    --log-level info \
    >> "$LOG_FILE" 2>&1
