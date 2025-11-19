"""Database schema for token tracking."""
import aiosqlite


async def create_token_tracking_tables(db: aiosqlite.Connection):
    """
    Create tables for token usage tracking.

    Args:
        db: Active database connection
    """
    # Token usage table - per-request tracking
    await db.execute("""
        CREATE TABLE IF NOT EXISTS token_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            session_id TEXT NOT NULL,
            operation_type TEXT NOT NULL,
            model TEXT NOT NULL,
            tokens_input INTEGER NOT NULL,
            tokens_output INTEGER NOT NULL,
            tokens_total INTEGER NOT NULL,
            cost_usd REAL NOT NULL,
            duration_seconds REAL,
            metadata TEXT
        )
    """)

    # Create index on timestamp for fast time-based queries
    await db.execute("""
        CREATE INDEX IF NOT EXISTS idx_token_usage_timestamp
        ON token_usage(timestamp)
    """)

    # Create index on session_id for session aggregation
    await db.execute("""
        CREATE INDEX IF NOT EXISTS idx_token_usage_session
        ON token_usage(session_id)
    """)

    # Token sessions table - session-level aggregates
    await db.execute("""
        CREATE TABLE IF NOT EXISTS token_sessions (
            session_id TEXT PRIMARY KEY,
            start_time DATETIME NOT NULL,
            end_time DATETIME,
            operation_mode TEXT,
            total_requests INTEGER DEFAULT 0,
            total_tokens_input INTEGER DEFAULT 0,
            total_tokens_output INTEGER DEFAULT 0,
            total_cost_usd REAL DEFAULT 0.0,
            is_active BOOLEAN DEFAULT 1
        )
    """)

    # Rate limit tracking table - rolling window counters
    await db.execute("""
        CREATE TABLE IF NOT EXISTS rate_limit_tracking (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            period TEXT NOT NULL,
            window_start DATETIME NOT NULL,
            request_count INTEGER DEFAULT 0,
            token_count INTEGER DEFAULT 0,
            UNIQUE(period, window_start)
        )
    """)

    # Create index on period and window_start for rate limit queries
    await db.execute("""
        CREATE INDEX IF NOT EXISTS idx_rate_limit_period
        ON rate_limit_tracking(period, window_start)
    """)
