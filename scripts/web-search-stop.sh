#!/bin/bash
# Stop web-search daemon

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$SCRIPT_DIR/web-search.pid"

if [ ! -f "$PID_FILE" ]; then
    echo "Daemon not running (no PID file)"
    exit 0
fi

PID=$(cat "$PID_FILE")

if kill -0 "$PID" 2>/dev/null; then
    echo "Stopping daemon (PID: $PID)..."
    kill "$PID"
    sleep 2

    # Force kill if still running
    if kill -0 "$PID" 2>/dev/null; then
        kill -9 "$PID"
    fi

    rm -f "$PID_FILE"
    echo "Daemon stopped"
else
    echo "Daemon not running (stale PID file)"
    rm -f "$PID_FILE"
fi
