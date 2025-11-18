"""Database schema for market movers strategy."""
import aiosqlite

async def create_movers_tables(db: aiosqlite.Connection):
    """Create tables for market movers strategy."""

    # Signals table
    await db.execute("""
        CREATE TABLE IF NOT EXISTS movers_signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            symbol TEXT NOT NULL,
            direction TEXT NOT NULL,
            confidence INTEGER NOT NULL,
            entry_price REAL NOT NULL,
            stop_loss REAL NOT NULL,
            tp1 REAL NOT NULL,
            position_size_usd REAL NOT NULL,
            risk_amount_usd REAL NOT NULL,
            technical_score REAL,
            sentiment_score REAL,
            liquidity_score REAL,
            correlation_score REAL,
            analysis TEXT,
            status TEXT DEFAULT 'PENDING'
        )
    """)

    # Rejections table
    await db.execute("""
        CREATE TABLE IF NOT EXISTS movers_rejections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            symbol TEXT NOT NULL,
            direction TEXT NOT NULL,
            confidence INTEGER,
            reason TEXT NOT NULL,
            details TEXT
        )
    """)

    # Metrics table
    await db.execute("""
        CREATE TABLE IF NOT EXISTS movers_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            cycle_duration_seconds REAL,
            movers_found INTEGER,
            signals_generated INTEGER,
            signals_executed INTEGER,
            signals_rejected INTEGER,
            open_positions INTEGER,
            total_exposure_pct REAL,
            daily_pnl_pct REAL,
            weekly_pnl_pct REAL,
            risk_level TEXT
        )
    """)

    # Create indexes
    await db.execute("CREATE INDEX IF NOT EXISTS idx_movers_signals_symbol ON movers_signals(symbol)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_movers_signals_timestamp ON movers_signals(timestamp)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_movers_rejections_reason ON movers_rejections(reason)")
