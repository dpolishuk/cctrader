"""Database schema for multi-agent pipeline outputs."""
import aiosqlite
from pathlib import Path

AGENT_SCHEMA = """
-- Agent outputs for audit trail
CREATE TABLE IF NOT EXISTS agent_outputs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    agent_type TEXT NOT NULL,
    input_json TEXT,
    output_json TEXT,
    tokens_used INTEGER,
    duration_ms INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_agent_outputs_session ON agent_outputs(session_id);
CREATE INDEX IF NOT EXISTS idx_agent_outputs_symbol ON agent_outputs(symbol);
CREATE INDEX IF NOT EXISTS idx_agent_outputs_type ON agent_outputs(agent_type);

-- Risk decisions (separate for quick queries)
CREATE TABLE IF NOT EXISTS risk_decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    action TEXT NOT NULL,
    original_confidence INTEGER,
    audited_confidence INTEGER,
    modifications TEXT,
    warnings TEXT,
    risk_score INTEGER,
    portfolio_snapshot TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_risk_decisions_session ON risk_decisions(session_id);
CREATE INDEX IF NOT EXISTS idx_risk_decisions_action ON risk_decisions(action);

-- Execution reports
CREATE TABLE IF NOT EXISTS execution_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    status TEXT NOT NULL,
    order_type TEXT,
    requested_entry REAL,
    actual_entry REAL,
    slippage_pct REAL,
    position_size REAL,
    execution_time_ms INTEGER,
    abort_reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_execution_reports_session ON execution_reports(session_id);
CREATE INDEX IF NOT EXISTS idx_execution_reports_status ON execution_reports(status);

-- Trade reviews (per-trade P&L audits)
CREATE TABLE IF NOT EXISTS trade_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    pnl_pct REAL,
    pnl_usd REAL,
    result TEXT,
    what_worked TEXT,
    what_didnt_work TEXT,
    recommendation TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_trade_reviews_trade ON trade_reviews(trade_id);

-- Daily reports (batch P&L audits)
CREATE TABLE IF NOT EXISTS daily_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_date DATE NOT NULL UNIQUE,
    total_trades INTEGER,
    wins INTEGER,
    losses INTEGER,
    win_rate REAL,
    total_pnl_pct REAL,
    total_pnl_usd REAL,
    patterns_json TEXT,
    recommendations_json TEXT,
    agent_performance_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_daily_reports_date ON daily_reports(report_date);
"""


async def init_agent_schema(db_path: Path) -> None:
    """Initialize the agent pipeline database tables."""
    async with aiosqlite.connect(db_path) as db:
        await db.executescript(AGENT_SCHEMA)
        await db.commit()
