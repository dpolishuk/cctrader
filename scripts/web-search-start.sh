#!/bin/bash
# Start web-search daemon in background

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$SCRIPT_DIR/web-search.pid"

# Check if already running
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        echo "Daemon already running (PID: $PID)"
        exit 1
    fi
    rm -f "$PID_FILE"
fi

# Start daemon in background
nohup "$SCRIPT_DIR/web-search-daemon.sh" > /dev/null 2>&1 &

sleep 1

if [ -f "$PID_FILE" ]; then
    echo "Daemon started (PID: $(cat "$PID_FILE"))"
else
    echo "Failed to start daemon"
    exit 1
fi
