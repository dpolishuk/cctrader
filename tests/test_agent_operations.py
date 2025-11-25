"""Tests for agent output database operations."""
import pytest
import pytest_asyncio
import tempfile
from pathlib import Path
from datetime import date

from src.agent.database.agent_schema import init_agent_schema
from src.agent.database.agent_operations import AgentOperations


@pytest_asyncio.fixture
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
