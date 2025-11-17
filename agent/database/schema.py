"""SQLite database schema for trading agent."""
import aiosqlite
from pathlib import Path
from typing import Optional

DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    symbol TEXT NOT NULL,
    signal_type TEXT NOT NULL,
    confidence REAL NOT NULL,
    price REAL NOT NULL,
    timeframe TEXT NOT NULL,
    reason TEXT,
    technical_data TEXT,
    sentiment_data TEXT
);

CREATE INDEX IF NOT EXISTS idx_signal_symbol_timestamp ON signals(symbol, timestamp);
CREATE INDEX IF NOT EXISTS idx_signal_type ON signals(signal_type);

CREATE TABLE IF NOT EXISTS technical_analysis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    rsi REAL,
    macd REAL,
    macd_signal REAL,
    macd_hist REAL,
    bb_upper REAL,
    bb_middle REAL,
    bb_lower REAL,
    volume REAL,
    price REAL,
    additional_indicators TEXT
);

CREATE INDEX IF NOT EXISTS idx_ta_symbol_timeframe ON technical_analysis(symbol, timeframe, timestamp);

CREATE TABLE IF NOT EXISTS sentiment_analysis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    symbol TEXT NOT NULL,
    sentiment_score REAL,
    news_summary TEXT,
    sources TEXT,
    key_events TEXT
);

CREATE INDEX IF NOT EXISTS idx_sentiment_symbol ON sentiment_analysis(symbol, timestamp);

CREATE TABLE IF NOT EXISTS portfolio_state (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    symbol TEXT NOT NULL,
    position_type TEXT,
    entry_price REAL,
    current_price REAL,
    quantity REAL,
    unrealized_pnl REAL,
    realized_pnl REAL,
    stop_loss REAL,
    take_profit REAL,
    UNIQUE(symbol)
);

CREATE TABLE IF NOT EXISTS agent_state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""

async def init_database(db_path: Path) -> None:
    """Initialize the SQLite database with schema."""
    async with aiosqlite.connect(db_path) as db:
        await db.executescript(DB_SCHEMA)
        await db.commit()
