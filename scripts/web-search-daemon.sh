#!/bin/bash
# Web Search MCP Daemon - auto-restarts on crash

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
CONFIG_FILE="$SCRIPT_DIR/web-search.conf"
LOG_FILE="$PROJECT_DIR/logs/web-search.log"
PID_FILE="$SCRIPT_DIR/web-search.pid"

# Load config
source "$CONFIG_FILE"

# Create logs directory
mkdir -p "$(dirname "$LOG_FILE")"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

rotate_log() {
    local size_kb=$(du -k "$LOG_FILE" 2>/dev/null | cut -f1)
    local max_kb=$((MAX_LOG_SIZE_MB * 1024))
    if [ "${size_kb:-0}" -gt "$max_kb" ]; then
        mv "$LOG_FILE" "$LOG_FILE.old"
        log "Log rotated"
    fi
}

cleanup() {
    log "Daemon stopping..."
    rm -f "$PID_FILE"
    exit 0
}

trap cleanup SIGTERM SIGINT

# Save PID
echo $$ > "$PID_FILE"
log "Daemon started (PID: $$)"

# Main loop - restart on crash
while true; do
    rotate_log
    log "Starting web-search server on port $PORT..."

    MODE="$MODE" \
    PORT="$PORT" \
    DEFAULT_SEARCH_ENGINE="$DEFAULT_SEARCH_ENGINE" \
    ALLOWED_SEARCH_ENGINES="$ALLOWED_SEARCH_ENGINES" \
    ENABLE_CORS="$ENABLE_CORS" \
    USE_PROXY="$USE_PROXY" \
    PROXY_URL="$PROXY_URL" \
    npx open-websearch@latest >> "$LOG_FILE" 2>&1

    EXIT_CODE=$?
    log "Server exited with code $EXIT_CODE, restarting in ${RESTART_DELAY}s..."
    sleep "$RESTART_DELAY"
done
