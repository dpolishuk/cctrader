"""SQLite schema for paper trading functionality."""
import aiosqlite
from pathlib import Path

PAPER_TRADING_SCHEMA = """
-- Paper trading portfolios
CREATE TABLE IF NOT EXISTS paper_portfolios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    starting_capital REAL NOT NULL,
    current_equity REAL NOT NULL,
    execution_mode TEXT NOT NULL DEFAULT 'realistic',  -- instant, realistic, historical
    is_active INTEGER DEFAULT 1,
    max_position_size_pct REAL DEFAULT 5.0,  -- Max % of portfolio per position
    max_total_exposure_pct REAL DEFAULT 80.0,  -- Max % of portfolio deployed
    max_daily_loss_pct REAL DEFAULT 5.0,
    max_drawdown_pct REAL DEFAULT 10.0,
    circuit_breaker_active INTEGER DEFAULT 0,
    peak_equity REAL,  -- Track for drawdown calculation
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_paper_portfolio_active ON paper_portfolios(is_active);

-- Paper trading positions
CREATE TABLE IF NOT EXISTS paper_positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_id INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    position_type TEXT NOT NULL,  -- LONG, SHORT, NONE
    entry_price REAL NOT NULL,
    current_price REAL,
    quantity REAL NOT NULL,
    stop_loss REAL,
    take_profit REAL,
    unrealized_pnl REAL DEFAULT 0,
    opened_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_open INTEGER DEFAULT 1,
    FOREIGN KEY (portfolio_id) REFERENCES paper_portfolios(id),
    UNIQUE(portfolio_id, symbol, is_open)
);

CREATE INDEX IF NOT EXISTS idx_paper_positions_portfolio ON paper_positions(portfolio_id, is_open);
CREATE INDEX IF NOT EXISTS idx_paper_positions_symbol ON paper_positions(symbol);

-- Paper trading trade history
CREATE TABLE IF NOT EXISTS paper_trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_id INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    trade_type TEXT NOT NULL,  -- OPEN_LONG, OPEN_SHORT, CLOSE
    price REAL NOT NULL,
    quantity REAL NOT NULL,
    execution_mode TEXT NOT NULL,
    slippage_pct REAL DEFAULT 0,
    actual_fill_price REAL NOT NULL,
    signal_price REAL,  -- Price when signal generated
    signal_id INTEGER,  -- Reference to signals table
    executed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    realized_pnl REAL,
    commission REAL DEFAULT 0,
    notes TEXT,
    FOREIGN KEY (portfolio_id) REFERENCES paper_portfolios(id),
    FOREIGN KEY (signal_id) REFERENCES signals(id)
);

CREATE INDEX IF NOT EXISTS idx_paper_trades_portfolio ON paper_trades(portfolio_id, executed_at);
CREATE INDEX IF NOT EXISTS idx_paper_trades_symbol ON paper_trades(symbol);

-- Risk compliance audit log
CREATE TABLE IF NOT EXISTS paper_risk_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,  -- PRE_TRADE_BLOCK, LIMIT_WARNING, LIMIT_VIOLATION, CIRCUIT_BREAKER
    severity TEXT NOT NULL,  -- INFO, WARNING, CRITICAL
    rule_type TEXT NOT NULL,  -- POSITION_SIZE, EXPOSURE, DAILY_LOSS, DRAWDOWN, CORRELATION
    rule_limit REAL,
    current_value REAL,
    symbol TEXT,
    trade_id INTEGER,
    message TEXT,
    triggered_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (portfolio_id) REFERENCES paper_portfolios(id),
    FOREIGN KEY (trade_id) REFERENCES paper_trades(id)
);

CREATE INDEX IF NOT EXISTS idx_paper_audit_portfolio ON paper_risk_audit(portfolio_id, triggered_at);
CREATE INDEX IF NOT EXISTS idx_paper_audit_severity ON paper_risk_audit(severity);

-- Performance metrics (aggregated statistics)
CREATE TABLE IF NOT EXISTS paper_performance_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_id INTEGER NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    total_trades INTEGER DEFAULT 0,
    winning_trades INTEGER DEFAULT 0,
    losing_trades INTEGER DEFAULT 0,
    win_rate REAL DEFAULT 0,
    total_pnl REAL DEFAULT 0,
    realized_pnl REAL DEFAULT 0,
    unrealized_pnl REAL DEFAULT 0,
    max_drawdown_pct REAL DEFAULT 0,
    current_drawdown_pct REAL DEFAULT 0,
    sharpe_ratio REAL,
    sortino_ratio REAL,
    profit_factor REAL,
    avg_win REAL,
    avg_loss REAL,
    largest_win REAL,
    largest_loss REAL,
    avg_slippage_pct REAL,
    avg_execution_lag_ms REAL,
    FOREIGN KEY (portfolio_id) REFERENCES paper_portfolios(id)
);

CREATE INDEX IF NOT EXISTS idx_paper_metrics_portfolio ON paper_performance_metrics(portfolio_id, timestamp);

-- Execution quality tracking
CREATE TABLE IF NOT EXISTS paper_execution_quality (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id INTEGER NOT NULL,
    signal_generated_at DATETIME NOT NULL,
    execution_started_at DATETIME NOT NULL,
    execution_completed_at DATETIME NOT NULL,
    signal_price REAL NOT NULL,
    executed_price REAL NOT NULL,
    slippage_pct REAL NOT NULL,
    execution_lag_ms INTEGER NOT NULL,
    market_volatility REAL,  -- ATR or similar at execution time
    partial_fill INTEGER DEFAULT 0,
    fill_percentage REAL DEFAULT 100.0,
    FOREIGN KEY (trade_id) REFERENCES paper_trades(id)
);

CREATE INDEX IF NOT EXISTS idx_paper_exec_quality_trade ON paper_execution_quality(trade_id);
"""

async def init_paper_trading_db(db_path: Path) -> None:
    """Initialize paper trading tables in the database."""
    async with aiosqlite.connect(db_path) as db:
        await db.executescript(PAPER_TRADING_SCHEMA)
        await db.commit()
