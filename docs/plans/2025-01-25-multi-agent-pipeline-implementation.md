# Multi-Agent Trading Pipeline Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement a 4-agent sequential trading pipeline (Analysis → Risk Auditor → Execution → P&L Auditor).

**Architecture:** Sequential pipeline where each Claude agent passes structured JSON to the next. Each agent has specialized tools and prompts. All outputs persisted to database for audit trail.

**Tech Stack:** Python 3.11+, claude-agent-sdk, aiosqlite, pydantic, pytest

---

## Task 1: Database Schema for Agent Outputs

**Files:**
- Create: `src/agent/database/agent_schema.py`
- Test: `tests/test_agent_schema.py`

**Step 1: Write the failing test**

```python
# tests/test_agent_schema.py
"""Tests for agent output database schema."""
import pytest
import aiosqlite
from pathlib import Path
import tempfile

from src.agent.database.agent_schema import init_agent_schema


@pytest.mark.asyncio
async def test_agent_outputs_table_exists():
    """Test that agent_outputs table is created."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    await init_agent_schema(db_path)

    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='agent_outputs'"
        )
        result = await cursor.fetchone()
        assert result is not None
        assert result[0] == "agent_outputs"

    db_path.unlink()


@pytest.mark.asyncio
async def test_risk_decisions_table_exists():
    """Test that risk_decisions table is created."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    await init_agent_schema(db_path)

    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='risk_decisions'"
        )
        result = await cursor.fetchone()
        assert result is not None

    db_path.unlink()


@pytest.mark.asyncio
async def test_execution_reports_table_exists():
    """Test that execution_reports table is created."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    await init_agent_schema(db_path)

    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='execution_reports'"
        )
        result = await cursor.fetchone()
        assert result is not None

    db_path.unlink()


@pytest.mark.asyncio
async def test_trade_reviews_table_exists():
    """Test that trade_reviews table is created."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    await init_agent_schema(db_path)

    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='trade_reviews'"
        )
        result = await cursor.fetchone()
        assert result is not None

    db_path.unlink()


@pytest.mark.asyncio
async def test_daily_reports_table_exists():
    """Test that daily_reports table is created."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    await init_agent_schema(db_path)

    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='daily_reports'"
        )
        result = await cursor.fetchone()
        assert result is not None

    db_path.unlink()
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_agent_schema.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'src.agent.database.agent_schema'`

**Step 3: Write minimal implementation**

```python
# src/agent/database/agent_schema.py
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
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_agent_schema.py -v
```

Expected: PASS (5 tests)

**Step 5: Commit**

```bash
git add src/agent/database/agent_schema.py tests/test_agent_schema.py
git commit -m "feat(db): add agent pipeline database schema"
```

---

## Task 2: Agent Output Operations (CRUD)

**Files:**
- Create: `src/agent/database/agent_operations.py`
- Test: `tests/test_agent_operations.py`

**Step 1: Write the failing test**

```python
# tests/test_agent_operations.py
"""Tests for agent output database operations."""
import pytest
import tempfile
from pathlib import Path
from datetime import date

from src.agent.database.agent_schema import init_agent_schema
from src.agent.database.agent_operations import AgentOperations


@pytest.fixture
async def db_ops():
    """Create a temporary database with agent schema."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    await init_agent_schema(db_path)
    ops = AgentOperations(db_path)
    yield ops
    db_path.unlink()


@pytest.mark.asyncio
async def test_save_agent_output(db_ops):
    """Test saving agent output."""
    output_id = await db_ops.save_agent_output(
        session_id="test-session-123",
        symbol="BTCUSDT",
        agent_type="analysis",
        input_json='{"symbol": "BTCUSDT"}',
        output_json='{"confidence": 75}',
        tokens_used=1000,
        duration_ms=5000
    )

    assert output_id > 0


@pytest.mark.asyncio
async def test_save_risk_decision(db_ops):
    """Test saving risk decision."""
    decision_id = await db_ops.save_risk_decision(
        session_id="test-session-123",
        symbol="BTCUSDT",
        action="APPROVE",
        original_confidence=75,
        audited_confidence=70,
        modifications='["reduced position size"]',
        warnings='["high exposure"]',
        risk_score=35,
        portfolio_snapshot='{"equity": 10000}'
    )

    assert decision_id > 0


@pytest.mark.asyncio
async def test_save_execution_report(db_ops):
    """Test saving execution report."""
    report_id = await db_ops.save_execution_report(
        session_id="test-session-123",
        symbol="BTCUSDT",
        status="FILLED",
        order_type="LIMIT",
        requested_entry=50000.0,
        actual_entry=49995.0,
        slippage_pct=-0.01,
        position_size=0.1,
        execution_time_ms=1500,
        abort_reason=None
    )

    assert report_id > 0


@pytest.mark.asyncio
async def test_save_trade_review(db_ops):
    """Test saving trade review."""
    review_id = await db_ops.save_trade_review(
        trade_id="TRD-123",
        symbol="BTCUSDT",
        pnl_pct=5.5,
        pnl_usd=550.0,
        result="WIN",
        what_worked='["good entry timing"]',
        what_didnt_work='["tight stop loss"]',
        recommendation="Consider wider stops"
    )

    assert review_id > 0


@pytest.mark.asyncio
async def test_save_daily_report(db_ops):
    """Test saving daily report."""
    report_id = await db_ops.save_daily_report(
        report_date=date(2025, 1, 25),
        total_trades=10,
        wins=6,
        losses=4,
        win_rate=60.0,
        total_pnl_pct=3.5,
        total_pnl_usd=350.0,
        patterns_json='[{"pattern": "momentum works"}]',
        recommendations_json='["increase position sizes"]',
        agent_performance_json='{"analysis": {"accuracy": 65}}'
    )

    assert report_id > 0


@pytest.mark.asyncio
async def test_get_agent_outputs_by_session(db_ops):
    """Test retrieving agent outputs by session."""
    # Save multiple outputs
    await db_ops.save_agent_output(
        session_id="session-abc",
        symbol="BTCUSDT",
        agent_type="analysis",
        input_json="{}",
        output_json="{}",
        tokens_used=100,
        duration_ms=1000
    )
    await db_ops.save_agent_output(
        session_id="session-abc",
        symbol="BTCUSDT",
        agent_type="risk_auditor",
        input_json="{}",
        output_json="{}",
        tokens_used=50,
        duration_ms=500
    )

    outputs = await db_ops.get_agent_outputs_by_session("session-abc")

    assert len(outputs) == 2
    assert outputs[0]["agent_type"] == "analysis"
    assert outputs[1]["agent_type"] == "risk_auditor"
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_agent_operations.py -v
```

Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write minimal implementation**

```python
# src/agent/database/agent_operations.py
"""Database operations for multi-agent pipeline."""
import aiosqlite
from pathlib import Path
from datetime import date
from typing import Optional, List, Dict, Any


class AgentOperations:
    """CRUD operations for agent pipeline outputs."""

    def __init__(self, db_path: Path):
        self.db_path = db_path

    async def save_agent_output(
        self,
        session_id: str,
        symbol: str,
        agent_type: str,
        input_json: str,
        output_json: str,
        tokens_used: int,
        duration_ms: int
    ) -> int:
        """Save agent output and return ID."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                INSERT INTO agent_outputs
                (session_id, symbol, agent_type, input_json, output_json, tokens_used, duration_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (session_id, symbol, agent_type, input_json, output_json, tokens_used, duration_ms)
            )
            await db.commit()
            return cursor.lastrowid

    async def save_risk_decision(
        self,
        session_id: str,
        symbol: str,
        action: str,
        original_confidence: int,
        audited_confidence: int,
        modifications: str,
        warnings: str,
        risk_score: int,
        portfolio_snapshot: str
    ) -> int:
        """Save risk decision and return ID."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                INSERT INTO risk_decisions
                (session_id, symbol, action, original_confidence, audited_confidence,
                 modifications, warnings, risk_score, portfolio_snapshot)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (session_id, symbol, action, original_confidence, audited_confidence,
                 modifications, warnings, risk_score, portfolio_snapshot)
            )
            await db.commit()
            return cursor.lastrowid

    async def save_execution_report(
        self,
        session_id: str,
        symbol: str,
        status: str,
        order_type: Optional[str],
        requested_entry: float,
        actual_entry: Optional[float],
        slippage_pct: Optional[float],
        position_size: Optional[float],
        execution_time_ms: Optional[int],
        abort_reason: Optional[str]
    ) -> int:
        """Save execution report and return ID."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                INSERT INTO execution_reports
                (session_id, symbol, status, order_type, requested_entry, actual_entry,
                 slippage_pct, position_size, execution_time_ms, abort_reason)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (session_id, symbol, status, order_type, requested_entry, actual_entry,
                 slippage_pct, position_size, execution_time_ms, abort_reason)
            )
            await db.commit()
            return cursor.lastrowid

    async def save_trade_review(
        self,
        trade_id: str,
        symbol: str,
        pnl_pct: float,
        pnl_usd: float,
        result: str,
        what_worked: str,
        what_didnt_work: str,
        recommendation: str
    ) -> int:
        """Save trade review and return ID."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                INSERT INTO trade_reviews
                (trade_id, symbol, pnl_pct, pnl_usd, result, what_worked,
                 what_didnt_work, recommendation)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (trade_id, symbol, pnl_pct, pnl_usd, result, what_worked,
                 what_didnt_work, recommendation)
            )
            await db.commit()
            return cursor.lastrowid

    async def save_daily_report(
        self,
        report_date: date,
        total_trades: int,
        wins: int,
        losses: int,
        win_rate: float,
        total_pnl_pct: float,
        total_pnl_usd: float,
        patterns_json: str,
        recommendations_json: str,
        agent_performance_json: str
    ) -> int:
        """Save daily report and return ID."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                INSERT OR REPLACE INTO daily_reports
                (report_date, total_trades, wins, losses, win_rate, total_pnl_pct,
                 total_pnl_usd, patterns_json, recommendations_json, agent_performance_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (report_date.isoformat(), total_trades, wins, losses, win_rate,
                 total_pnl_pct, total_pnl_usd, patterns_json, recommendations_json,
                 agent_performance_json)
            )
            await db.commit()
            return cursor.lastrowid

    async def get_agent_outputs_by_session(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all agent outputs for a session."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT * FROM agent_outputs
                WHERE session_id = ?
                ORDER BY created_at ASC
                """,
                (session_id,)
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_risk_decisions_by_date(self, start_date: date, end_date: date) -> List[Dict[str, Any]]:
        """Get risk decisions in date range."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT * FROM risk_decisions
                WHERE date(created_at) BETWEEN ? AND ?
                ORDER BY created_at DESC
                """,
                (start_date.isoformat(), end_date.isoformat())
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_daily_report(self, report_date: date) -> Optional[Dict[str, Any]]:
        """Get daily report for a specific date."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM daily_reports WHERE report_date = ?",
                (report_date.isoformat(),)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_agent_operations.py -v
```

Expected: PASS (6 tests)

**Step 5: Commit**

```bash
git add src/agent/database/agent_operations.py tests/test_agent_operations.py
git commit -m "feat(db): add agent pipeline CRUD operations"
```

---

## Task 3: Pydantic Schemas for Agent Communication

**Files:**
- Create: `src/agent/agents/schemas.py`
- Test: `tests/test_agent_schemas.py`

**Step 1: Write the failing test**

```python
# tests/test_agent_schemas.py
"""Tests for agent communication schemas."""
import pytest
from pydantic import ValidationError

from src.agent.agents.schemas import (
    AnalysisReport,
    ProposedSignal,
    AnalysisAgentOutput,
    RiskDecision,
    AuditedSignal,
    RiskAuditorOutput,
    ExecutionReport,
    PositionOpened,
    ExecutionAgentOutput,
    TradeReview,
    PnlAuditorOutput
)


def test_proposed_signal_valid():
    """Test valid proposed signal."""
    signal = ProposedSignal(
        direction="LONG",
        confidence=72,
        entry_price=0.0407,
        stop_loss=0.0366,
        take_profit=0.0472,
        position_size_pct=4.0,
        reasoning="Strong uptrend"
    )
    assert signal.direction == "LONG"
    assert signal.confidence == 72


def test_proposed_signal_invalid_confidence():
    """Test that confidence must be 0-100."""
    with pytest.raises(ValidationError):
        ProposedSignal(
            direction="LONG",
            confidence=150,  # Invalid
            entry_price=0.0407,
            stop_loss=0.0366,
            take_profit=0.0472,
            position_size_pct=4.0,
            reasoning="Test"
        )


def test_proposed_signal_invalid_direction():
    """Test that direction must be LONG or SHORT."""
    with pytest.raises(ValidationError):
        ProposedSignal(
            direction="UP",  # Invalid
            confidence=50,
            entry_price=0.0407,
            stop_loss=0.0366,
            take_profit=0.0472,
            position_size_pct=4.0,
            reasoning="Test"
        )


def test_risk_decision_valid():
    """Test valid risk decision."""
    decision = RiskDecision(
        action="MODIFY",
        original_confidence=72,
        audited_confidence=68,
        modifications=["Reduced position size"],
        warnings=["High exposure"],
        risk_score=35
    )
    assert decision.action == "MODIFY"


def test_risk_decision_invalid_action():
    """Test that action must be APPROVE/REJECT/MODIFY."""
    with pytest.raises(ValidationError):
        RiskDecision(
            action="MAYBE",  # Invalid
            original_confidence=72,
            audited_confidence=68,
            modifications=[],
            warnings=[],
            risk_score=35
        )


def test_execution_report_filled():
    """Test valid filled execution report."""
    report = ExecutionReport(
        status="FILLED",
        order_type="LIMIT",
        requested_entry=0.0407,
        actual_entry=0.0405,
        slippage_pct=-0.49,
        position_size=250.0,
        position_value_usd=101.25,
        execution_time_ms=1250,
        order_id="ORD-12345",
        notes="Good fill"
    )
    assert report.status == "FILLED"


def test_execution_report_aborted():
    """Test valid aborted execution report."""
    report = ExecutionReport(
        status="ABORTED",
        reason="Price moved too far",
        requested_entry=0.0407,
        current_price=0.0450,
        price_deviation_pct=10.5
    )
    assert report.status == "ABORTED"
    assert report.reason == "Price moved too far"


def test_analysis_agent_output_with_signal():
    """Test analysis output with signal."""
    output = AnalysisAgentOutput(
        analysis_report=AnalysisReport(
            symbol="BTCUSDT",
            timestamp="2025-01-25T10:00:00Z",
            technical={"trend_score": 0.85},
            sentiment={"score": 0.65},
            liquidity={"volume_24h": 1000000},
            btc_correlation=0.72
        ),
        proposed_signal=ProposedSignal(
            direction="LONG",
            confidence=72,
            entry_price=50000,
            stop_loss=48000,
            take_profit=55000,
            position_size_pct=4.0,
            reasoning="Strong trend"
        )
    )
    assert output.proposed_signal is not None
    assert output.proposed_signal.direction == "LONG"


def test_analysis_agent_output_no_trade():
    """Test analysis output with no trade signal."""
    output = AnalysisAgentOutput(
        analysis_report=AnalysisReport(
            symbol="BTCUSDT",
            timestamp="2025-01-25T10:00:00Z",
            technical={"trend_score": 0.45},
            sentiment={"score": 0.50},
            liquidity={"volume_24h": 1000000},
            btc_correlation=0.72
        ),
        proposed_signal=None  # No trade
    )
    assert output.proposed_signal is None
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_agent_schemas.py -v
```

Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write minimal implementation**

```python
# src/agent/agents/schemas.py
"""Pydantic schemas for agent communication."""
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field, field_validator


# === Analysis Agent Schemas ===

class AnalysisReport(BaseModel):
    """Raw analysis data from Analysis Agent."""
    symbol: str
    timestamp: str
    technical: Dict[str, Any]
    sentiment: Dict[str, Any]
    liquidity: Dict[str, Any]
    btc_correlation: float


class ProposedSignal(BaseModel):
    """Proposed trading signal from Analysis Agent."""
    direction: Literal["LONG", "SHORT"]
    confidence: int = Field(ge=0, le=100)
    entry_price: float = Field(gt=0)
    stop_loss: float = Field(gt=0)
    take_profit: float = Field(gt=0)
    position_size_pct: float = Field(gt=0, le=100)
    reasoning: str


class AnalysisAgentOutput(BaseModel):
    """Complete output from Analysis Agent."""
    analysis_report: AnalysisReport
    proposed_signal: Optional[ProposedSignal] = None


# === Risk Auditor Schemas ===

class RiskDecision(BaseModel):
    """Risk decision from Risk Auditor Agent."""
    action: Literal["APPROVE", "REJECT", "MODIFY"]
    original_confidence: int = Field(ge=0, le=100)
    audited_confidence: Optional[int] = Field(default=None, ge=0, le=100)
    modifications: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    risk_score: int = Field(ge=0, le=100)
    reason: Optional[str] = None  # For rejections


class AuditedSignal(BaseModel):
    """Signal after risk audit modifications."""
    direction: Literal["LONG", "SHORT"]
    confidence: int = Field(ge=0, le=100)
    entry_price: float = Field(gt=0)
    stop_loss: float = Field(gt=0)
    take_profit: float = Field(gt=0)
    position_size_pct: float = Field(gt=0, le=100)
    reasoning: str


class PortfolioSnapshot(BaseModel):
    """Portfolio state at time of risk decision."""
    equity: float
    open_positions: int
    current_exposure_pct: float
    daily_pnl_pct: float
    weekly_pnl_pct: float


class RiskAuditorOutput(BaseModel):
    """Complete output from Risk Auditor Agent."""
    risk_decision: RiskDecision
    audited_signal: Optional[AuditedSignal] = None
    portfolio_snapshot: PortfolioSnapshot


# === Execution Agent Schemas ===

class ExecutionReport(BaseModel):
    """Execution report from Execution Agent."""
    status: Literal["FILLED", "PARTIAL", "ABORTED"]
    order_type: Optional[Literal["MARKET", "LIMIT"]] = None
    requested_entry: float
    actual_entry: Optional[float] = None
    slippage_pct: Optional[float] = None
    position_size: Optional[float] = None
    position_value_usd: Optional[float] = None
    execution_time_ms: Optional[int] = None
    order_id: Optional[str] = None
    notes: Optional[str] = None
    # For aborted orders
    reason: Optional[str] = None
    current_price: Optional[float] = None
    price_deviation_pct: Optional[float] = None


class PositionOpened(BaseModel):
    """Position details when trade is executed."""
    symbol: str
    direction: Literal["LONG", "SHORT"]
    entry_price: float
    stop_loss: float
    take_profit: float
    size: float
    opened_at: str


class ExecutionAgentOutput(BaseModel):
    """Complete output from Execution Agent."""
    execution_report: ExecutionReport
    position_opened: Optional[PositionOpened] = None


# === P&L Auditor Schemas ===

class TradeReviewAnalysis(BaseModel):
    """Analysis section of trade review."""
    what_worked: List[str]
    what_didnt_work: List[str]
    agent_accuracy: Dict[str, Any]


class TradeReview(BaseModel):
    """Per-trade review from P&L Auditor."""
    trade_id: str
    symbol: str
    direction: Literal["LONG", "SHORT"]
    entry_price: float
    exit_price: float
    pnl_pct: float
    pnl_usd: float
    duration_hours: float
    result: Literal["WIN", "LOSS"]
    analysis: TradeReviewAnalysis
    recommendation: str


class DailyReportSummary(BaseModel):
    """Summary section of daily report."""
    total_trades: int
    wins: int
    losses: int
    win_rate: float
    total_pnl_pct: float
    total_pnl_usd: float
    best_trade: Optional[Dict[str, Any]] = None
    worst_trade: Optional[Dict[str, Any]] = None


class PatternIdentified(BaseModel):
    """Pattern identified in daily analysis."""
    pattern: str
    evidence: str
    recommendation: str


class AgentPerformance(BaseModel):
    """Performance metrics for each agent."""
    analysis_agent: Dict[str, Any]
    risk_auditor: Dict[str, Any]
    execution_agent: Dict[str, Any]


class DailyReport(BaseModel):
    """Daily batch report from P&L Auditor."""
    date: str
    summary: DailyReportSummary
    patterns_identified: List[PatternIdentified]
    agent_performance: AgentPerformance
    strategy_recommendations: List[str]


class PnlAuditorOutput(BaseModel):
    """Output from P&L Auditor (either trade review or daily report)."""
    mode: Literal["TRADE_REVIEW", "DAILY_REPORT"]
    trade_review: Optional[TradeReview] = None
    daily_report: Optional[DailyReport] = None
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_agent_schemas.py -v
```

Expected: PASS (10 tests)

**Step 5: Commit**

```bash
git add src/agent/agents/schemas.py tests/test_agent_schemas.py
git commit -m "feat(agents): add pydantic schemas for agent communication"
```

---

## Task 4: Base Agent Class

**Files:**
- Create: `src/agent/agents/__init__.py`
- Create: `src/agent/agents/base_agent.py`
- Test: `tests/test_base_agent.py`

**Step 1: Write the failing test**

```python
# tests/test_base_agent.py
"""Tests for base agent class."""
import pytest
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from src.agent.agents.base_agent import BaseAgent
from src.agent.database.agent_schema import init_agent_schema
from src.agent.database.agent_operations import AgentOperations


class ConcreteAgent(BaseAgent):
    """Concrete implementation for testing."""

    agent_type = "test_agent"

    async def run(self, input_data: dict) -> dict:
        return {"result": "test", "input": input_data}


@pytest.fixture
async def db_ops():
    """Create temporary database."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)
    await init_agent_schema(db_path)
    ops = AgentOperations(db_path)
    yield ops
    db_path.unlink()


@pytest.mark.asyncio
async def test_base_agent_save_output(db_ops):
    """Test that base agent saves output to database."""
    agent = ConcreteAgent(db_ops=db_ops)

    await agent._save_output(
        session_id="test-session",
        symbol="BTCUSDT",
        input_data={"test": "input"},
        output_data={"test": "output"},
        tokens_used=100,
        duration_ms=500
    )

    outputs = await db_ops.get_agent_outputs_by_session("test-session")
    assert len(outputs) == 1
    assert outputs[0]["agent_type"] == "test_agent"
    assert outputs[0]["symbol"] == "BTCUSDT"


@pytest.mark.asyncio
async def test_base_agent_run_with_tracking(db_ops):
    """Test run_with_tracking saves output."""
    agent = ConcreteAgent(db_ops=db_ops)

    result = await agent.run_with_tracking(
        session_id="test-session-2",
        symbol="ETHUSDT",
        input_data={"symbol": "ETHUSDT"}
    )

    assert result["result"] == "test"

    # Verify output was saved
    outputs = await db_ops.get_agent_outputs_by_session("test-session-2")
    assert len(outputs) == 1


@pytest.mark.asyncio
async def test_base_agent_requires_agent_type():
    """Test that agent_type must be defined."""

    class BadAgent(BaseAgent):
        async def run(self, input_data: dict) -> dict:
            return {}

    with pytest.raises(NotImplementedError):
        BadAgent(db_ops=MagicMock())
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_base_agent.py -v
```

Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write minimal implementation**

```python
# src/agent/agents/__init__.py
"""Multi-agent pipeline components."""
from .base_agent import BaseAgent
from .schemas import (
    AnalysisAgentOutput,
    RiskAuditorOutput,
    ExecutionAgentOutput,
    PnlAuditorOutput
)

__all__ = [
    "BaseAgent",
    "AnalysisAgentOutput",
    "RiskAuditorOutput",
    "ExecutionAgentOutput",
    "PnlAuditorOutput"
]
```

```python
# src/agent/agents/base_agent.py
"""Base class for all pipeline agents."""
import json
import time
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

from src.agent.database.agent_operations import AgentOperations

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Base class for all pipeline agents."""

    agent_type: str = None  # Must be overridden by subclass

    def __init__(self, db_ops: AgentOperations):
        """
        Initialize base agent.

        Args:
            db_ops: Database operations instance for saving outputs
        """
        if self.agent_type is None:
            raise NotImplementedError("Subclass must define agent_type")

        self.db_ops = db_ops

    @abstractmethod
    async def run(self, input_data: dict) -> dict:
        """
        Execute agent logic. Must be implemented by subclass.

        Args:
            input_data: Input data for the agent

        Returns:
            Agent output as dictionary
        """
        pass

    async def run_with_tracking(
        self,
        session_id: str,
        symbol: str,
        input_data: dict
    ) -> dict:
        """
        Run agent with automatic output tracking.

        Args:
            session_id: Unique session identifier
            symbol: Trading symbol being analyzed
            input_data: Input data for the agent

        Returns:
            Agent output as dictionary
        """
        start_time = time.time()
        tokens_used = 0  # Will be populated by Claude client

        try:
            output_data = await self.run(input_data)

            duration_ms = int((time.time() - start_time) * 1000)

            # Save output to database
            await self._save_output(
                session_id=session_id,
                symbol=symbol,
                input_data=input_data,
                output_data=output_data,
                tokens_used=tokens_used,
                duration_ms=duration_ms
            )

            return output_data

        except Exception as e:
            logger.error(f"{self.agent_type} failed: {e}", exc_info=True)
            raise

    async def _save_output(
        self,
        session_id: str,
        symbol: str,
        input_data: dict,
        output_data: dict,
        tokens_used: int,
        duration_ms: int
    ) -> None:
        """
        Save agent output to database for audit trail.

        Args:
            session_id: Unique session identifier
            symbol: Trading symbol
            input_data: Input that was provided to agent
            output_data: Output produced by agent
            tokens_used: Number of tokens consumed
            duration_ms: Execution duration in milliseconds
        """
        await self.db_ops.save_agent_output(
            session_id=session_id,
            symbol=symbol,
            agent_type=self.agent_type,
            input_json=json.dumps(input_data),
            output_json=json.dumps(output_data),
            tokens_used=tokens_used,
            duration_ms=duration_ms
        )

        logger.info(
            f"Saved {self.agent_type} output for {symbol} "
            f"(session: {session_id}, duration: {duration_ms}ms)"
        )
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_base_agent.py -v
```

Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add src/agent/agents/__init__.py src/agent/agents/base_agent.py tests/test_base_agent.py
git commit -m "feat(agents): add base agent class with tracking"
```

---

## Task 5: Analysis Agent Prompt

**Files:**
- Create: `src/agent/agents/prompts/__init__.py`
- Create: `src/agent/agents/prompts/analysis_prompt.py`
- Test: `tests/test_analysis_prompt.py`

**Step 1: Write the failing test**

```python
# tests/test_analysis_prompt.py
"""Tests for analysis agent prompt."""
import pytest

from src.agent.agents.prompts.analysis_prompt import (
    build_analysis_prompt,
    ANALYSIS_SYSTEM_PROMPT
)


def test_analysis_system_prompt_exists():
    """Test that system prompt is defined."""
    assert ANALYSIS_SYSTEM_PROMPT is not None
    assert len(ANALYSIS_SYSTEM_PROMPT) > 100
    assert "Analysis Agent" in ANALYSIS_SYSTEM_PROMPT


def test_build_analysis_prompt_basic():
    """Test building basic analysis prompt."""
    prompt = build_analysis_prompt(
        symbol="BTCUSDT",
        momentum_1h=5.0,
        momentum_4h=10.0,
        current_price=50000.0,
        volume_24h=1000000000.0
    )

    assert "BTCUSDT" in prompt
    assert "5.0" in prompt or "5%" in prompt
    assert "50000" in prompt or "50,000" in prompt


def test_build_analysis_prompt_with_context():
    """Test building prompt with additional context."""
    prompt = build_analysis_prompt(
        symbol="ETHUSDT",
        momentum_1h=-3.0,
        momentum_4h=-8.0,
        current_price=3000.0,
        volume_24h=500000000.0,
        additional_context="Market is in a downtrend"
    )

    assert "ETHUSDT" in prompt
    assert "downtrend" in prompt.lower() or "Market is in a downtrend" in prompt


def test_analysis_prompt_mentions_output_format():
    """Test that prompt instructs on output format."""
    assert "JSON" in ANALYSIS_SYSTEM_PROMPT or "json" in ANALYSIS_SYSTEM_PROMPT
    assert "analysis_report" in ANALYSIS_SYSTEM_PROMPT
    assert "proposed_signal" in ANALYSIS_SYSTEM_PROMPT
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_analysis_prompt.py -v
```

Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write minimal implementation**

```python
# src/agent/agents/prompts/__init__.py
"""Agent prompts."""
from .analysis_prompt import build_analysis_prompt, ANALYSIS_SYSTEM_PROMPT

__all__ = ["build_analysis_prompt", "ANALYSIS_SYSTEM_PROMPT"]
```

```python
# src/agent/agents/prompts/analysis_prompt.py
"""Prompt for Analysis Agent."""

ANALYSIS_SYSTEM_PROMPT = """You are a Market Analysis Agent. Your job is to analyze trading opportunities with precision and objectivity.

## Your Capabilities
You have access to tools for:
- Multi-timeframe technical analysis (15m, 1h, 4h)
- Sentiment analysis via web search
- Current price and volume data

## Your Process
1. Gather technical data using fetch_technical_snapshot
2. Gather sentiment data using fetch_sentiment_data
3. Synthesize findings into a complete analysis
4. Decide: Is this a tradeable opportunity?
5. If yes, propose a signal with specific entry/exit levels

## Output Format
You MUST output valid JSON with exactly this structure:

```json
{
  "analysis_report": {
    "symbol": "SYMBOL",
    "timestamp": "ISO-8601 timestamp",
    "technical": {
      "trend_score": 0.0-1.0,
      "momentum_score": -1.0 to 1.0,
      "volatility": "low/normal/high",
      "key_levels": {"support": price, "resistance": price},
      "timeframe_alignment": "aligned/mixed/conflicting"
    },
    "sentiment": {
      "score": 0-30,
      "catalysts": ["list of catalysts found"],
      "news_summary": "brief summary"
    },
    "liquidity": {
      "volume_24h": number,
      "spread_pct": number,
      "assessment": "good/adequate/poor"
    },
    "btc_correlation": 0.0-1.0
  },
  "proposed_signal": {
    "direction": "LONG" or "SHORT",
    "confidence": 0-100,
    "entry_price": exact price,
    "stop_loss": exact price,
    "take_profit": exact price,
    "position_size_pct": 1.0-5.0,
    "reasoning": "2-3 sentence explanation"
  }
}
```

## When to Output NO_TRADE
Set `proposed_signal` to `null` when:
- Confidence would be below 50
- Timeframes show conflicting signals
- No clear catalyst or setup
- Liquidity is insufficient

## Scoring Guidelines
- Technical score (0-40): Based on trend alignment, momentum, patterns
- Sentiment score (0-30): Based on news/catalysts found
- Liquidity score (0-20): Based on volume and spread
- Correlation score (0-10): Based on BTC correlation (lower = better for altcoins)

Total confidence = technical + sentiment + liquidity + correlation

## Important Rules
- Be conservative. When uncertain, output NO_TRADE.
- Use exact prices, not ranges.
- Stop-loss should be 5-15% from entry for altcoins.
- Take-profit should have at least 1.5:1 reward:risk ratio.
- Position size should be 2-4% for normal setups, up to 5% for high confidence only.
"""


def build_analysis_prompt(
    symbol: str,
    momentum_1h: float,
    momentum_4h: float,
    current_price: float,
    volume_24h: float,
    additional_context: str = ""
) -> str:
    """
    Build the analysis prompt for a specific symbol.

    Args:
        symbol: Trading pair (e.g., "BTCUSDT")
        momentum_1h: 1-hour price change percentage
        momentum_4h: 4-hour price change percentage
        current_price: Current market price
        volume_24h: 24-hour trading volume in USD
        additional_context: Optional additional context

    Returns:
        Complete prompt string for the agent
    """
    direction_hint = "LONG" if momentum_1h > 0 else "SHORT"

    prompt = f"""Analyze {symbol} as a potential {direction_hint} opportunity.

## Current Context
- Symbol: {symbol}
- Current Price: ${current_price:,.6f}
- 1h Momentum: {momentum_1h:+.2f}%
- 4h Momentum: {momentum_4h:+.2f}%
- 24h Volume: ${volume_24h:,.0f}

## Your Task
1. Use fetch_technical_snapshot to get multi-timeframe technical analysis
2. Use fetch_sentiment_data to check for news/catalysts
3. Synthesize your findings
4. Output your analysis as JSON (see system prompt for format)

{f"Additional Context: {additional_context}" if additional_context else ""}

Remember: Only propose a signal if confidence >= 50. Be conservative."""

    return prompt
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_analysis_prompt.py -v
```

Expected: PASS (4 tests)

**Step 5: Commit**

```bash
git add src/agent/agents/prompts/__init__.py src/agent/agents/prompts/analysis_prompt.py tests/test_analysis_prompt.py
git commit -m "feat(agents): add analysis agent prompt"
```

---

## Task 6: Risk Auditor Prompt

**Files:**
- Create: `src/agent/agents/prompts/risk_auditor_prompt.py`
- Modify: `src/agent/agents/prompts/__init__.py`
- Test: `tests/test_risk_auditor_prompt.py`

**Step 1: Write the failing test**

```python
# tests/test_risk_auditor_prompt.py
"""Tests for risk auditor agent prompt."""
import pytest

from src.agent.agents.prompts.risk_auditor_prompt import (
    build_risk_auditor_prompt,
    RISK_AUDITOR_SYSTEM_PROMPT
)


def test_risk_auditor_system_prompt_exists():
    """Test that system prompt is defined."""
    assert RISK_AUDITOR_SYSTEM_PROMPT is not None
    assert len(RISK_AUDITOR_SYSTEM_PROMPT) > 100
    assert "Risk Auditor" in RISK_AUDITOR_SYSTEM_PROMPT


def test_build_risk_auditor_prompt():
    """Test building risk auditor prompt."""
    analysis_output = {
        "analysis_report": {"symbol": "BTCUSDT", "technical": {}},
        "proposed_signal": {
            "direction": "LONG",
            "confidence": 72,
            "entry_price": 50000,
            "stop_loss": 48000,
            "take_profit": 55000,
            "position_size_pct": 4.0
        }
    }

    portfolio_state = {
        "equity": 10000,
        "open_positions": 3,
        "current_exposure_pct": 15.0,
        "daily_pnl_pct": -1.2,
        "weekly_pnl_pct": 3.5
    }

    prompt = build_risk_auditor_prompt(
        analysis_output=analysis_output,
        portfolio_state=portfolio_state
    )

    assert "BTCUSDT" in prompt
    assert "72" in prompt  # confidence
    assert "10000" in prompt or "10,000" in prompt  # equity


def test_risk_auditor_mentions_actions():
    """Test that prompt mentions APPROVE/REJECT/MODIFY."""
    assert "APPROVE" in RISK_AUDITOR_SYSTEM_PROMPT
    assert "REJECT" in RISK_AUDITOR_SYSTEM_PROMPT
    assert "MODIFY" in RISK_AUDITOR_SYSTEM_PROMPT
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_risk_auditor_prompt.py -v
```

Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write minimal implementation**

```python
# src/agent/agents/prompts/risk_auditor_prompt.py
"""Prompt for Risk Auditor Agent."""
import json

RISK_AUDITOR_SYSTEM_PROMPT = """You are a Risk Auditor Agent. Your job is to protect the portfolio from excessive risk.

## Your Authority
You have FULL AUTHORITY to:
- **APPROVE**: Signal passes all risk checks, execute as proposed
- **REJECT**: Signal violates risk limits or is too risky, do not execute
- **MODIFY**: Adjust position size, stop-loss, or take-profit to meet risk requirements

## Risk Checks to Perform
1. **Confidence threshold**: Reject if confidence < 60
2. **Position limit**: Reject if already at max positions (5)
3. **Exposure limit**: Modify size if would exceed 25% total exposure
4. **Daily loss limit**: Reject ALL trades if daily loss >= -5%
5. **Weekly loss limit**: Reject ALL trades if weekly loss >= -10%
6. **Correlation limit**: Reject if >2 positions in same correlation group
7. **Risk/reward ratio**: Modify if R:R < 1.5
8. **Stop-loss validity**: Reject if stop > 15% from entry (too wide)

## Available Tools
- get_portfolio_state: Current equity, exposure, P&L
- get_open_positions: List of current positions
- check_correlation_group: Check correlation with existing positions
- get_risk_config: Current risk limits

## Output Format
You MUST output valid JSON with exactly this structure:

For APPROVE or MODIFY:
```json
{
  "risk_decision": {
    "action": "APPROVE" or "MODIFY",
    "original_confidence": original_score,
    "audited_confidence": adjusted_score,
    "modifications": ["list of changes made"],
    "warnings": ["list of concerns"],
    "risk_score": 0-100 (higher = riskier)
  },
  "audited_signal": {
    "direction": "LONG" or "SHORT",
    "confidence": adjusted_confidence,
    "entry_price": price,
    "stop_loss": price (possibly adjusted),
    "take_profit": price (possibly adjusted),
    "position_size_pct": pct (possibly reduced),
    "reasoning": "explanation of changes"
  },
  "portfolio_snapshot": {
    "equity": current_equity,
    "open_positions": count,
    "current_exposure_pct": pct,
    "daily_pnl_pct": pct,
    "weekly_pnl_pct": pct
  }
}
```

For REJECT:
```json
{
  "risk_decision": {
    "action": "REJECT",
    "reason": "specific reason for rejection",
    "risk_score": 0-100
  },
  "audited_signal": null,
  "portfolio_snapshot": { ... }
}
```

## Important Rules
- Be conservative. Your job is to PROTECT the portfolio.
- Always explain your reasoning.
- If modifying, explain each change.
- Check ALL risk limits, not just the obvious ones.
- When in doubt, REJECT.
"""


def build_risk_auditor_prompt(
    analysis_output: dict,
    portfolio_state: dict
) -> str:
    """
    Build the risk auditor prompt.

    Args:
        analysis_output: Output from Analysis Agent
        portfolio_state: Current portfolio state

    Returns:
        Complete prompt string for the agent
    """
    analysis_json = json.dumps(analysis_output, indent=2)
    portfolio_json = json.dumps(portfolio_state, indent=2)

    signal = analysis_output.get("proposed_signal", {})
    symbol = analysis_output.get("analysis_report", {}).get("symbol", "UNKNOWN")

    prompt = f"""Review this trading signal for {symbol} and make a risk decision.

## Analysis Agent Output
```json
{analysis_json}
```

## Current Portfolio State
```json
{portfolio_json}
```

## Your Task
1. Use get_portfolio_state to verify current state
2. Use get_open_positions to check existing positions
3. Use check_correlation_group to assess correlation risk
4. Evaluate against ALL risk checks
5. Output your decision as JSON (see system prompt for format)

Signal Summary:
- Direction: {signal.get('direction', 'N/A')}
- Confidence: {signal.get('confidence', 0)}
- Entry: {signal.get('entry_price', 0)}
- Stop Loss: {signal.get('stop_loss', 0)}
- Take Profit: {signal.get('take_profit', 0)}
- Position Size: {signal.get('position_size_pct', 0)}%

Make your risk decision: APPROVE, MODIFY, or REJECT."""

    return prompt
```

**Step 4: Update `__init__.py`**

```python
# src/agent/agents/prompts/__init__.py
"""Agent prompts."""
from .analysis_prompt import build_analysis_prompt, ANALYSIS_SYSTEM_PROMPT
from .risk_auditor_prompt import build_risk_auditor_prompt, RISK_AUDITOR_SYSTEM_PROMPT

__all__ = [
    "build_analysis_prompt",
    "ANALYSIS_SYSTEM_PROMPT",
    "build_risk_auditor_prompt",
    "RISK_AUDITOR_SYSTEM_PROMPT"
]
```

**Step 5: Run test to verify it passes**

```bash
pytest tests/test_risk_auditor_prompt.py -v
```

Expected: PASS (3 tests)

**Step 6: Commit**

```bash
git add src/agent/agents/prompts/risk_auditor_prompt.py src/agent/agents/prompts/__init__.py tests/test_risk_auditor_prompt.py
git commit -m "feat(agents): add risk auditor agent prompt"
```

---

## Task 7: Execution Agent Prompt

**Files:**
- Create: `src/agent/agents/prompts/execution_prompt.py`
- Modify: `src/agent/agents/prompts/__init__.py`
- Test: `tests/test_execution_prompt.py`

**Step 1: Write the failing test**

```python
# tests/test_execution_prompt.py
"""Tests for execution agent prompt."""
import pytest

from src.agent.agents.prompts.execution_prompt import (
    build_execution_prompt,
    EXECUTION_SYSTEM_PROMPT
)


def test_execution_system_prompt_exists():
    """Test that system prompt is defined."""
    assert EXECUTION_SYSTEM_PROMPT is not None
    assert len(EXECUTION_SYSTEM_PROMPT) > 100
    assert "Execution Agent" in EXECUTION_SYSTEM_PROMPT


def test_build_execution_prompt():
    """Test building execution prompt."""
    audited_signal = {
        "direction": "LONG",
        "confidence": 68,
        "entry_price": 0.0407,
        "stop_loss": 0.0375,
        "take_profit": 0.0472,
        "position_size_pct": 2.5
    }

    prompt = build_execution_prompt(
        symbol="MONUSDT",
        audited_signal=audited_signal,
        portfolio_equity=10000.0
    )

    assert "MONUSDT" in prompt
    assert "0.0407" in prompt
    assert "LONG" in prompt


def test_execution_prompt_mentions_abort():
    """Test that prompt mentions abort conditions."""
    assert "ABORT" in EXECUTION_SYSTEM_PROMPT or "abort" in EXECUTION_SYSTEM_PROMPT
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_execution_prompt.py -v
```

Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write minimal implementation**

```python
# src/agent/agents/prompts/execution_prompt.py
"""Prompt for Execution Agent."""
import json

EXECUTION_SYSTEM_PROMPT = """You are an Execution Agent. Your job is to execute trades optimally.

## Your Capabilities
You receive a risk-approved signal and must execute it with best possible price.

You can:
- Execute immediately with market order
- Place limit order and wait for fill
- Split into multiple smaller orders (for large positions)
- ABORT if market conditions have changed significantly

## Available Tools
- get_current_price: Real-time bid/ask/last price
- get_orderbook_depth: Order book snapshot
- place_market_order: Execute at market price
- place_limit_order: Place limit order at specified price
- check_order_status: Check if limit order filled
- cancel_order: Cancel unfilled limit order
- get_spread_info: Current spread and slippage estimate

## Execution Logic
1. Check current price vs target entry
2. If price moved >2% against entry → ABORT
3. If spread >0.5% → use limit order
4. If order book thin → consider abort or reduce size
5. Execute and monitor fill

## Abort Conditions (MUST abort if any are true)
- Price moved >2% away from intended entry
- Spread exceeds 1%
- Order book would cause >1% slippage
- Limit order not filled within 30 seconds

## Output Format

For FILLED:
```json
{
  "execution_report": {
    "status": "FILLED",
    "order_type": "MARKET" or "LIMIT",
    "requested_entry": price,
    "actual_entry": price,
    "slippage_pct": pct,
    "position_size": quantity,
    "position_value_usd": value,
    "execution_time_ms": ms,
    "order_id": "id",
    "notes": "any notes"
  },
  "position_opened": {
    "symbol": "SYMBOL",
    "direction": "LONG" or "SHORT",
    "entry_price": actual_price,
    "stop_loss": price,
    "take_profit": price,
    "size": quantity,
    "opened_at": "ISO timestamp"
  }
}
```

For ABORTED:
```json
{
  "execution_report": {
    "status": "ABORTED",
    "reason": "specific reason",
    "requested_entry": price,
    "current_price": price,
    "price_deviation_pct": pct
  },
  "position_opened": null
}
```

## Important Rules
- Your goal is BEST EXECUTION, not just any execution
- Negative slippage (better price than requested) is good
- Always report actual fill price, not requested
- If in doubt about market conditions, ABORT
"""


def build_execution_prompt(
    symbol: str,
    audited_signal: dict,
    portfolio_equity: float
) -> str:
    """
    Build the execution prompt.

    Args:
        symbol: Trading pair
        audited_signal: Signal approved by Risk Auditor
        portfolio_equity: Current portfolio value

    Returns:
        Complete prompt string for the agent
    """
    signal_json = json.dumps(audited_signal, indent=2)

    position_value = portfolio_equity * (audited_signal.get("position_size_pct", 0) / 100)

    prompt = f"""Execute this risk-approved trade for {symbol}.

## Audited Signal
```json
{signal_json}
```

## Position Details
- Direction: {audited_signal.get('direction')}
- Target Entry: {audited_signal.get('entry_price')}
- Stop Loss: {audited_signal.get('stop_loss')}
- Take Profit: {audited_signal.get('take_profit')}
- Position Size: {audited_signal.get('position_size_pct')}% of portfolio
- Position Value: ${position_value:,.2f}

## Your Task
1. Use get_current_price to check current market price
2. Use get_spread_info to assess execution conditions
3. Decide: Market order, limit order, or abort?
4. Execute if conditions are favorable
5. Report execution result as JSON

Remember: You can ABORT if market has moved significantly against the entry."""

    return prompt
```

**Step 4: Update `__init__.py`**

Add to `src/agent/agents/prompts/__init__.py`:
```python
from .execution_prompt import build_execution_prompt, EXECUTION_SYSTEM_PROMPT
```

And update `__all__`.

**Step 5: Run test to verify it passes**

```bash
pytest tests/test_execution_prompt.py -v
```

Expected: PASS (3 tests)

**Step 6: Commit**

```bash
git add src/agent/agents/prompts/execution_prompt.py src/agent/agents/prompts/__init__.py tests/test_execution_prompt.py
git commit -m "feat(agents): add execution agent prompt"
```

---

## Task 8: P&L Auditor Prompt

**Files:**
- Create: `src/agent/agents/prompts/pnl_auditor_prompt.py`
- Modify: `src/agent/agents/prompts/__init__.py`
- Test: `tests/test_pnl_auditor_prompt.py`

**Step 1: Write the failing test**

```python
# tests/test_pnl_auditor_prompt.py
"""Tests for P&L auditor agent prompt."""
import pytest

from src.agent.agents.prompts.pnl_auditor_prompt import (
    build_trade_review_prompt,
    build_daily_report_prompt,
    PNL_AUDITOR_SYSTEM_PROMPT
)


def test_pnl_auditor_system_prompt_exists():
    """Test that system prompt is defined."""
    assert PNL_AUDITOR_SYSTEM_PROMPT is not None
    assert len(PNL_AUDITOR_SYSTEM_PROMPT) > 100
    assert "P&L Auditor" in PNL_AUDITOR_SYSTEM_PROMPT


def test_build_trade_review_prompt():
    """Test building trade review prompt."""
    trade = {
        "trade_id": "TRD-123",
        "symbol": "BTCUSDT",
        "direction": "LONG",
        "entry_price": 50000,
        "exit_price": 52500,
        "pnl_pct": 5.0,
        "pnl_usd": 250.0
    }

    prompt = build_trade_review_prompt(trade=trade)

    assert "TRD-123" in prompt
    assert "BTCUSDT" in prompt
    assert "5.0" in prompt or "5%" in prompt


def test_build_daily_report_prompt():
    """Test building daily report prompt."""
    trades = [
        {"symbol": "BTCUSDT", "pnl_pct": 5.0},
        {"symbol": "ETHUSDT", "pnl_pct": -2.0}
    ]

    prompt = build_daily_report_prompt(
        date="2025-01-25",
        trades=trades
    )

    assert "2025-01-25" in prompt
    assert "BTCUSDT" in prompt


def test_pnl_auditor_mentions_modes():
    """Test that prompt mentions TRADE_REVIEW and DAILY_REPORT."""
    assert "TRADE_REVIEW" in PNL_AUDITOR_SYSTEM_PROMPT
    assert "DAILY_REPORT" in PNL_AUDITOR_SYSTEM_PROMPT
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_pnl_auditor_prompt.py -v
```

Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write minimal implementation**

```python
# src/agent/agents/prompts/pnl_auditor_prompt.py
"""Prompt for P&L Auditor Agent."""
import json
from typing import List

PNL_AUDITOR_SYSTEM_PROMPT = """You are a P&L Auditor Agent. Your job is to review trading performance and identify insights.

## Two Modes

### TRADE_REVIEW Mode
Analyze a single closed trade immediately after it closes.
Focus on: What worked? What didn't? Any recommendations?

### DAILY_REPORT Mode
Batch analysis of all trades from the day.
Focus on: Patterns, agent performance, strategy recommendations.

## Available Tools
- get_trade_details: Full details of a specific trade
- get_trade_history: List of trades for a period
- get_market_context: What was happening in market during trade
- calculate_metrics: Win rate, avg P&L, Sharpe, drawdown
- get_signal_accuracy: Compare original signals vs outcomes
- get_agent_performance: How accurate was each agent

## Output Format

For TRADE_REVIEW:
```json
{
  "mode": "TRADE_REVIEW",
  "trade_review": {
    "trade_id": "id",
    "symbol": "SYMBOL",
    "direction": "LONG" or "SHORT",
    "entry_price": price,
    "exit_price": price,
    "pnl_pct": pct,
    "pnl_usd": usd,
    "duration_hours": hours,
    "result": "WIN" or "LOSS",
    "analysis": {
      "what_worked": ["list"],
      "what_didnt_work": ["list"],
      "agent_accuracy": {
        "analysis_agent_confidence": score,
        "risk_auditor_confidence": score,
        "actual_outcome": "WIN/LOSS",
        "assessment": "description"
      }
    },
    "recommendation": "actionable suggestion"
  },
  "daily_report": null
}
```

For DAILY_REPORT:
```json
{
  "mode": "DAILY_REPORT",
  "trade_review": null,
  "daily_report": {
    "date": "YYYY-MM-DD",
    "summary": {
      "total_trades": n,
      "wins": n,
      "losses": n,
      "win_rate": pct,
      "total_pnl_pct": pct,
      "total_pnl_usd": usd,
      "best_trade": {"symbol": "X", "pnl_pct": n},
      "worst_trade": {"symbol": "Y", "pnl_pct": n}
    },
    "patterns_identified": [
      {
        "pattern": "description",
        "evidence": "data supporting this",
        "recommendation": "what to do"
      }
    ],
    "agent_performance": {
      "analysis_agent": {"signals_generated": n, "accuracy": pct},
      "risk_auditor": {"approved": n, "rejected": n, "modified": n},
      "execution_agent": {"filled": n, "aborted": n, "avg_slippage_pct": pct}
    },
    "strategy_recommendations": ["list of recommendations"]
  }
}
```

## Important Rules
- Be specific and actionable, not generic
- Back up patterns with evidence
- Focus on what can be CHANGED, not just observed
- Compare agent predictions vs actual outcomes
"""


def build_trade_review_prompt(trade: dict) -> str:
    """
    Build prompt for per-trade review.

    Args:
        trade: Closed trade details

    Returns:
        Complete prompt string
    """
    trade_json = json.dumps(trade, indent=2)

    result = "WIN" if trade.get("pnl_pct", 0) > 0 else "LOSS"

    prompt = f"""Review this closed trade and provide insights.

## Trade Details
```json
{trade_json}
```

## Summary
- Trade ID: {trade.get('trade_id', 'N/A')}
- Symbol: {trade.get('symbol', 'N/A')}
- Direction: {trade.get('direction', 'N/A')}
- Result: {result}
- P&L: {trade.get('pnl_pct', 0):.2f}% (${trade.get('pnl_usd', 0):.2f})

## Your Task
1. Use get_trade_details to get full trade context
2. Use get_market_context to understand market conditions
3. Analyze what worked and what didn't
4. Provide one actionable recommendation
5. Output as JSON in TRADE_REVIEW format"""

    return prompt


def build_daily_report_prompt(date: str, trades: List[dict]) -> str:
    """
    Build prompt for daily batch report.

    Args:
        date: Report date (YYYY-MM-DD)
        trades: List of trades from the day

    Returns:
        Complete prompt string
    """
    trades_json = json.dumps(trades, indent=2)

    total = len(trades)
    wins = sum(1 for t in trades if t.get("pnl_pct", 0) > 0)
    losses = total - wins
    total_pnl = sum(t.get("pnl_pct", 0) for t in trades)

    prompt = f"""Generate daily performance report for {date}.

## Trades Summary
- Total Trades: {total}
- Wins: {wins}
- Losses: {losses}
- Total P&L: {total_pnl:.2f}%

## Trade Details
```json
{trades_json}
```

## Your Task
1. Use get_trade_history to get full trade details
2. Use calculate_metrics for performance metrics
3. Use get_agent_performance to assess each agent
4. Identify 2-3 patterns in the data
5. Provide actionable strategy recommendations
6. Output as JSON in DAILY_REPORT format"""

    return prompt
```

**Step 4: Update `__init__.py`**

Add imports and update `__all__`.

**Step 5: Run test to verify it passes**

```bash
pytest tests/test_pnl_auditor_prompt.py -v
```

Expected: PASS (4 tests)

**Step 6: Commit**

```bash
git add src/agent/agents/prompts/pnl_auditor_prompt.py src/agent/agents/prompts/__init__.py tests/test_pnl_auditor_prompt.py
git commit -m "feat(agents): add P&L auditor agent prompt"
```

---

## Task 9: Pipeline Orchestrator

**Files:**
- Create: `src/agent/pipeline/__init__.py`
- Create: `src/agent/pipeline/orchestrator.py`
- Test: `tests/test_pipeline_orchestrator.py`

**Step 1: Write the failing test**

```python
# tests/test_pipeline_orchestrator.py
"""Tests for pipeline orchestrator."""
import pytest
from unittest.mock import AsyncMock, MagicMock
import tempfile
from pathlib import Path

from src.agent.pipeline.orchestrator import PipelineOrchestrator, PipelineResult
from src.agent.database.agent_schema import init_agent_schema
from src.agent.database.agent_operations import AgentOperations


@pytest.fixture
async def db_ops():
    """Create temporary database."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)
    await init_agent_schema(db_path)
    ops = AgentOperations(db_path)
    yield ops
    db_path.unlink()


@pytest.fixture
def mock_agents():
    """Create mock agents."""
    analysis = AsyncMock()
    risk = AsyncMock()
    execution = AsyncMock()
    pnl = AsyncMock()
    return analysis, risk, execution, pnl


@pytest.mark.asyncio
async def test_pipeline_no_trade(db_ops, mock_agents):
    """Test pipeline when analysis returns no trade."""
    analysis, risk, execution, pnl = mock_agents

    # Analysis returns no signal
    analysis.run_with_tracking.return_value = {
        "analysis_report": {"symbol": "BTCUSDT"},
        "proposed_signal": None
    }

    orchestrator = PipelineOrchestrator(
        analysis_agent=analysis,
        risk_auditor=risk,
        execution_agent=execution,
        pnl_auditor=pnl,
        db_ops=db_ops
    )

    result = await orchestrator.run_pipeline(
        session_id="test-123",
        symbol="BTCUSDT",
        momentum_data={"1h": 5.0, "4h": 10.0}
    )

    assert result.status == "NO_TRADE"
    assert result.stage == "analysis"
    # Risk agent should not be called
    risk.run_with_tracking.assert_not_called()


@pytest.mark.asyncio
async def test_pipeline_rejected(db_ops, mock_agents):
    """Test pipeline when risk auditor rejects."""
    analysis, risk, execution, pnl = mock_agents

    # Analysis returns signal
    analysis.run_with_tracking.return_value = {
        "analysis_report": {"symbol": "BTCUSDT"},
        "proposed_signal": {"direction": "LONG", "confidence": 72}
    }

    # Risk auditor rejects
    risk.run_with_tracking.return_value = {
        "risk_decision": {"action": "REJECT", "reason": "Daily loss limit"},
        "audited_signal": None
    }

    orchestrator = PipelineOrchestrator(
        analysis_agent=analysis,
        risk_auditor=risk,
        execution_agent=execution,
        pnl_auditor=pnl,
        db_ops=db_ops
    )

    result = await orchestrator.run_pipeline(
        session_id="test-123",
        symbol="BTCUSDT",
        momentum_data={"1h": 5.0, "4h": 10.0}
    )

    assert result.status == "REJECTED"
    assert result.stage == "risk_auditor"
    # Execution should not be called
    execution.run_with_tracking.assert_not_called()


@pytest.mark.asyncio
async def test_pipeline_executed(db_ops, mock_agents):
    """Test successful pipeline execution."""
    analysis, risk, execution, pnl = mock_agents

    # Analysis returns signal
    analysis.run_with_tracking.return_value = {
        "analysis_report": {"symbol": "BTCUSDT"},
        "proposed_signal": {"direction": "LONG", "confidence": 72}
    }

    # Risk auditor approves
    risk.run_with_tracking.return_value = {
        "risk_decision": {"action": "APPROVE"},
        "audited_signal": {"direction": "LONG", "confidence": 72}
    }

    # Execution succeeds
    execution.run_with_tracking.return_value = {
        "execution_report": {"status": "FILLED"},
        "position_opened": {"symbol": "BTCUSDT", "entry_price": 50000}
    }

    orchestrator = PipelineOrchestrator(
        analysis_agent=analysis,
        risk_auditor=risk,
        execution_agent=execution,
        pnl_auditor=pnl,
        db_ops=db_ops
    )

    result = await orchestrator.run_pipeline(
        session_id="test-123",
        symbol="BTCUSDT",
        momentum_data={"1h": 5.0, "4h": 10.0}
    )

    assert result.status == "EXECUTED"
    assert result.position is not None
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_pipeline_orchestrator.py -v
```

Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write minimal implementation**

```python
# src/agent/pipeline/__init__.py
"""Pipeline orchestration."""
from .orchestrator import PipelineOrchestrator, PipelineResult

__all__ = ["PipelineOrchestrator", "PipelineResult"]
```

```python
# src/agent/pipeline/orchestrator.py
"""Pipeline orchestrator for multi-agent trading system."""
import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any

from src.agent.agents.base_agent import BaseAgent
from src.agent.database.agent_operations import AgentOperations

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """Result of pipeline execution."""
    status: str  # NO_TRADE, REJECTED, ABORTED, EXECUTED
    stage: str  # Which stage produced this result
    analysis_output: Optional[Dict[str, Any]] = None
    risk_output: Optional[Dict[str, Any]] = None
    execution_output: Optional[Dict[str, Any]] = None
    position: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class PipelineOrchestrator:
    """Orchestrates the 4-agent trading pipeline."""

    def __init__(
        self,
        analysis_agent: BaseAgent,
        risk_auditor: BaseAgent,
        execution_agent: BaseAgent,
        pnl_auditor: BaseAgent,
        db_ops: AgentOperations
    ):
        """
        Initialize pipeline orchestrator.

        Args:
            analysis_agent: Analysis Agent instance
            risk_auditor: Risk Auditor Agent instance
            execution_agent: Execution Agent instance
            pnl_auditor: P&L Auditor Agent instance
            db_ops: Database operations for audit trail
        """
        self.analysis_agent = analysis_agent
        self.risk_auditor = risk_auditor
        self.execution_agent = execution_agent
        self.pnl_auditor = pnl_auditor
        self.db_ops = db_ops

    async def run_pipeline(
        self,
        session_id: str,
        symbol: str,
        momentum_data: Dict[str, float],
        current_price: Optional[float] = None,
        volume_24h: Optional[float] = None,
        portfolio_state: Optional[Dict[str, Any]] = None
    ) -> PipelineResult:
        """
        Run the complete 4-agent pipeline.

        Args:
            session_id: Unique session identifier
            symbol: Trading symbol (e.g., "BTCUSDT")
            momentum_data: Dict with "1h" and "4h" momentum percentages
            current_price: Optional current price
            volume_24h: Optional 24h volume
            portfolio_state: Optional current portfolio state

        Returns:
            PipelineResult with status and outputs
        """
        logger.info(f"Starting pipeline for {symbol} (session: {session_id})")

        # Stage 1: Analysis
        logger.info("Stage 1: Running Analysis Agent")
        try:
            analysis_output = await self.analysis_agent.run_with_tracking(
                session_id=session_id,
                symbol=symbol,
                input_data={
                    "symbol": symbol,
                    "momentum_1h": momentum_data.get("1h", 0),
                    "momentum_4h": momentum_data.get("4h", 0),
                    "current_price": current_price,
                    "volume_24h": volume_24h
                }
            )
        except Exception as e:
            logger.error(f"Analysis Agent failed: {e}")
            return PipelineResult(
                status="ERROR",
                stage="analysis",
                error=str(e)
            )

        # Check if analysis produced a signal
        proposed_signal = analysis_output.get("proposed_signal")
        if proposed_signal is None:
            logger.info(f"Analysis Agent returned NO_TRADE for {symbol}")
            return PipelineResult(
                status="NO_TRADE",
                stage="analysis",
                analysis_output=analysis_output
            )

        # Stage 2: Risk Audit
        logger.info("Stage 2: Running Risk Auditor Agent")
        try:
            risk_output = await self.risk_auditor.run_with_tracking(
                session_id=session_id,
                symbol=symbol,
                input_data={
                    "analysis_output": analysis_output,
                    "portfolio_state": portfolio_state or {}
                }
            )
        except Exception as e:
            logger.error(f"Risk Auditor failed: {e}")
            return PipelineResult(
                status="ERROR",
                stage="risk_auditor",
                analysis_output=analysis_output,
                error=str(e)
            )

        # Check risk decision
        risk_decision = risk_output.get("risk_decision", {})
        action = risk_decision.get("action", "REJECT")

        if action == "REJECT":
            reason = risk_decision.get("reason", "Unknown")
            logger.info(f"Risk Auditor REJECTED signal for {symbol}: {reason}")
            return PipelineResult(
                status="REJECTED",
                stage="risk_auditor",
                analysis_output=analysis_output,
                risk_output=risk_output
            )

        # Stage 3: Execution
        audited_signal = risk_output.get("audited_signal")
        if audited_signal is None:
            logger.error("Risk Auditor approved but no audited_signal provided")
            return PipelineResult(
                status="ERROR",
                stage="risk_auditor",
                analysis_output=analysis_output,
                risk_output=risk_output,
                error="Missing audited_signal"
            )

        logger.info("Stage 3: Running Execution Agent")
        try:
            execution_output = await self.execution_agent.run_with_tracking(
                session_id=session_id,
                symbol=symbol,
                input_data={
                    "symbol": symbol,
                    "audited_signal": audited_signal,
                    "portfolio_equity": portfolio_state.get("equity", 10000) if portfolio_state else 10000
                }
            )
        except Exception as e:
            logger.error(f"Execution Agent failed: {e}")
            return PipelineResult(
                status="ERROR",
                stage="execution",
                analysis_output=analysis_output,
                risk_output=risk_output,
                error=str(e)
            )

        # Check execution result
        exec_report = execution_output.get("execution_report", {})
        exec_status = exec_report.get("status", "ABORTED")

        if exec_status == "ABORTED":
            reason = exec_report.get("reason", "Unknown")
            logger.info(f"Execution Agent ABORTED for {symbol}: {reason}")
            return PipelineResult(
                status="ABORTED",
                stage="execution",
                analysis_output=analysis_output,
                risk_output=risk_output,
                execution_output=execution_output
            )

        # Success!
        position = execution_output.get("position_opened")
        logger.info(f"Pipeline EXECUTED successfully for {symbol}")

        return PipelineResult(
            status="EXECUTED",
            stage="execution",
            analysis_output=analysis_output,
            risk_output=risk_output,
            execution_output=execution_output,
            position=position
        )

    async def run_trade_review(
        self,
        session_id: str,
        trade: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Run P&L Auditor for a closed trade.

        Args:
            session_id: Session identifier
            trade: Closed trade details

        Returns:
            Trade review output
        """
        return await self.pnl_auditor.run_with_tracking(
            session_id=session_id,
            symbol=trade.get("symbol", "UNKNOWN"),
            input_data={
                "mode": "TRADE_REVIEW",
                "trade": trade
            }
        )

    async def run_daily_report(
        self,
        session_id: str,
        date: str,
        trades: list
    ) -> Dict[str, Any]:
        """
        Run P&L Auditor for daily batch report.

        Args:
            session_id: Session identifier
            date: Report date (YYYY-MM-DD)
            trades: List of trades from the day

        Returns:
            Daily report output
        """
        return await self.pnl_auditor.run_with_tracking(
            session_id=session_id,
            symbol="PORTFOLIO",
            input_data={
                "mode": "DAILY_REPORT",
                "date": date,
                "trades": trades
            }
        )
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_pipeline_orchestrator.py -v
```

Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add src/agent/pipeline/__init__.py src/agent/pipeline/orchestrator.py tests/test_pipeline_orchestrator.py
git commit -m "feat(pipeline): add pipeline orchestrator"
```

---

## Remaining Tasks (Summary)

The following tasks follow the same TDD pattern:

### Task 10: Risk Auditor Tools
- Create: `src/agent/agents/tools/risk_tools.py`
- Tools: `get_portfolio_state`, `get_open_positions`, `check_correlation_group`, `get_risk_config`

### Task 11: Execution Agent Tools
- Create: `src/agent/agents/tools/execution_tools.py`
- Tools: `get_orderbook_depth`, `place_market_order`, `place_limit_order`, `check_order_status`, `cancel_order`

### Task 12: P&L Auditor Tools
- Create: `src/agent/agents/tools/pnl_tools.py`
- Tools: `get_trade_details`, `get_trade_history`, `calculate_metrics`, `get_agent_performance`

### Task 13: Analysis Agent Implementation
- Create: `src/agent/agents/analysis_agent.py`
- Refactor from current `AgentWrapper` to use new base class

### Task 14: Risk Auditor Agent Implementation
- Create: `src/agent/agents/risk_auditor_agent.py`

### Task 15: Execution Agent Implementation
- Create: `src/agent/agents/execution_agent.py`

### Task 16: P&L Auditor Agent Implementation
- Create: `src/agent/agents/pnl_auditor_agent.py`

### Task 17: Integration with Main Loop
- Modify: `src/agent/scanner/main_loop.py`
- Replace single agent call with pipeline orchestrator

### Task 18: CLI Commands for Reports
- Modify: `src/agent/main.py`
- Add commands: `daily-report`, `agent-performance`

### Task 19: Integration Tests
- Create: `tests/test_pipeline_integration.py`
- End-to-end pipeline test with mocked Claude responses

---

## Implementation Notes

1. **Each task is independent** - Can be done in any order after Task 4 (base agent)
2. **Tests first** - Always write failing test before implementation
3. **Small commits** - One commit per task keeps history clean
4. **Mock Claude** - Use mocks for unit tests, real API for integration only

---

**Plan complete and saved to `docs/plans/2025-01-25-multi-agent-pipeline-implementation.md`.**

**Two execution options:**

1. **Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

2. **Parallel Session (separate)** - Open new session in worktree with executing-plans, batch execution with checkpoints

**Which approach?**
