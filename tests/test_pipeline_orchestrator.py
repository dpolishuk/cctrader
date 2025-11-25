# tests/test_pipeline_orchestrator.py
"""Tests for pipeline orchestrator."""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
import tempfile
from pathlib import Path

from src.agent.pipeline.orchestrator import PipelineOrchestrator, PipelineResult
from src.agent.database.agent_schema import init_agent_schema
from src.agent.database.agent_operations import AgentOperations
from src.agent.pipeline.dashboard.events import StageEvent, StageStatus


@pytest_asyncio.fixture
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


@pytest.mark.asyncio
async def test_pipeline_emits_events(db_ops, mock_agents):
    """Test that pipeline emits events via callback."""
    analysis, risk, execution, pnl = mock_agents
    events_received = []

    def event_callback(event: StageEvent):
        events_received.append(event)

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
        db_ops=db_ops,
        event_callback=event_callback
    )

    await orchestrator.run_pipeline(
        session_id="test-123",
        symbol="BTCUSDT",
        momentum_data={"1h": 5.0, "4h": 10.0}
    )

    # Should have events for: analysis started, analysis complete,
    # risk started, risk complete, execution started, execution complete
    assert len(events_received) >= 4

    # Check we have analysis events
    analysis_events = [e for e in events_received if e.stage == "analysis"]
    assert any(e.status == StageStatus.RUNNING for e in analysis_events)
    assert any(e.status == StageStatus.COMPLETE for e in analysis_events)


@pytest.mark.asyncio
async def test_pipeline_events_include_output(db_ops, mock_agents):
    """Test that complete events include output data."""
    analysis, risk, execution, pnl = mock_agents
    events_received = []

    def event_callback(event: StageEvent):
        events_received.append(event)

    analysis.run_with_tracking.return_value = {
        "analysis_report": {"symbol": "BTCUSDT"},
        "proposed_signal": None  # No trade
    }

    orchestrator = PipelineOrchestrator(
        analysis_agent=analysis,
        risk_auditor=risk,
        execution_agent=execution,
        pnl_auditor=pnl,
        db_ops=db_ops,
        event_callback=event_callback
    )

    await orchestrator.run_pipeline(
        session_id="test-123",
        symbol="BTCUSDT",
        momentum_data={"1h": 5.0, "4h": 10.0}
    )

    # Find the analysis complete event
    complete_events = [e for e in events_received
                       if e.stage == "analysis" and e.status == StageStatus.COMPLETE]
    assert len(complete_events) == 1
    assert complete_events[0].output is not None


@pytest.mark.asyncio
async def test_pipeline_no_callback(db_ops, mock_agents):
    """Test pipeline works without callback."""
    analysis, risk, execution, pnl = mock_agents

    analysis.run_with_tracking.return_value = {
        "analysis_report": {"symbol": "BTCUSDT"},
        "proposed_signal": None
    }

    # No event_callback provided
    orchestrator = PipelineOrchestrator(
        analysis_agent=analysis,
        risk_auditor=risk,
        execution_agent=execution,
        pnl_auditor=pnl,
        db_ops=db_ops
    )

    # Should not raise error
    result = await orchestrator.run_pipeline(
        session_id="test-123",
        symbol="BTCUSDT",
        momentum_data={"1h": 5.0, "4h": 10.0}
    )

    assert result.status == "NO_TRADE"
