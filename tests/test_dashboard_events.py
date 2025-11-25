"""Tests for dashboard events."""
import pytest
from dataclasses import asdict

from src.agent.pipeline.dashboard.events import (
    StageEvent,
    StageStatus,
    PipelineState
)


def test_stage_event_creation():
    """Test creating a stage event."""
    event = StageEvent(
        stage="analysis",
        status=StageStatus.RUNNING,
        symbol="BTCUSDT",
        elapsed_ms=1500
    )
    assert event.stage == "analysis"
    assert event.status == StageStatus.RUNNING
    assert event.symbol == "BTCUSDT"
    assert event.elapsed_ms == 1500


def test_stage_event_with_output():
    """Test stage event with output data."""
    event = StageEvent(
        stage="analysis",
        status=StageStatus.COMPLETE,
        symbol="BTCUSDT",
        elapsed_ms=2300,
        output={"proposed_signal": {"direction": "LONG"}}
    )
    assert event.output is not None
    assert event.output["proposed_signal"]["direction"] == "LONG"


def test_stage_event_with_message():
    """Test stage event with status message."""
    event = StageEvent(
        stage="execution",
        status=StageStatus.RUNNING,
        symbol="BTCUSDT",
        elapsed_ms=800,
        message="Checking orderbook depth..."
    )
    assert event.message == "Checking orderbook depth..."


def test_stage_status_enum():
    """Test all stage statuses exist."""
    assert StageStatus.PENDING
    assert StageStatus.RUNNING
    assert StageStatus.COMPLETE
    assert StageStatus.SKIPPED
    assert StageStatus.ERROR


def test_pipeline_state_initialization():
    """Test pipeline state tracks all stages."""
    state = PipelineState(symbol="BTCUSDT", session_id="test-123")
    assert state.symbol == "BTCUSDT"
    assert state.session_id == "test-123"
    assert "analysis" in state.stages
    assert "risk_auditor" in state.stages
    assert "execution" in state.stages
    assert "pnl_auditor" in state.stages


def test_pipeline_state_update():
    """Test updating pipeline state with event."""
    state = PipelineState(symbol="BTCUSDT", session_id="test-123")
    event = StageEvent(
        stage="analysis",
        status=StageStatus.COMPLETE,
        symbol="BTCUSDT",
        elapsed_ms=2300,
        output={"proposed_signal": {"direction": "LONG"}}
    )
    state.update(event)
    assert state.stages["analysis"]["status"] == StageStatus.COMPLETE
    assert state.stages["analysis"]["elapsed_ms"] == 2300
    assert state.stages["analysis"]["output"] is not None
