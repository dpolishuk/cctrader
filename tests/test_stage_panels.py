"""Tests for stage panel renderer."""
import pytest
from rich.console import Console
from rich.panel import Panel

from src.agent.pipeline.dashboard.stage_panels import (
    StagePanelRenderer,
    render_analysis_panel,
    render_risk_panel,
    render_execution_panel,
    render_running_panel,
    render_pending_panel
)
from src.agent.pipeline.dashboard.events import StageStatus


@pytest.fixture
def renderer():
    """Create renderer instance."""
    return StagePanelRenderer()


@pytest.fixture
def analysis_output():
    """Sample analysis agent output."""
    return {
        "analysis_report": {
            "symbol": "BTCUSDT",
            "technical": {"trend_score": 0.85, "momentum_score": 0.7},
            "sentiment": {"score": 22, "catalysts": ["ETF inflows"]},
            "liquidity": {"volume_24h": 1000000000, "assessment": "good"},
            "btc_correlation": 0.3
        },
        "proposed_signal": {
            "direction": "LONG",
            "confidence": 72,
            "entry_price": 67500.0,
            "stop_loss": 64125.0,
            "take_profit": 72900.0,
            "position_size_pct": 3.0,
            "reasoning": "Strong uptrend on 4h with momentum confirmation."
        }
    }


@pytest.fixture
def risk_output():
    """Sample risk auditor output."""
    return {
        "risk_decision": {
            "action": "MODIFY",
            "original_confidence": 72,
            "audited_confidence": 68,
            "modifications": ["Reduced position size from 3% to 2.5%"],
            "warnings": ["High BTC correlation"],
            "risk_score": 35
        },
        "audited_signal": {
            "direction": "LONG",
            "confidence": 68,
            "entry_price": 67500.0,
            "stop_loss": 64125.0,
            "take_profit": 72900.0,
            "position_size_pct": 2.5,
            "reasoning": "Adjusted for risk limits"
        },
        "portfolio_snapshot": {
            "equity": 10450.0,
            "open_positions": 3,
            "current_exposure_pct": 12.0,
            "daily_pnl_pct": 1.2,
            "weekly_pnl_pct": 3.8
        }
    }


@pytest.fixture
def execution_output():
    """Sample execution agent output."""
    return {
        "execution_report": {
            "status": "FILLED",
            "order_type": "LIMIT",
            "requested_entry": 67500.0,
            "actual_entry": 67489.5,
            "slippage_pct": -0.016,
            "position_size": 0.0037,
            "position_value_usd": 249.91,
            "execution_time_ms": 850
        },
        "position_opened": {
            "symbol": "BTCUSDT",
            "direction": "LONG",
            "entry_price": 67489.5,
            "stop_loss": 64125.0,
            "take_profit": 72900.0,
            "size": 0.0037,
            "opened_at": "2025-01-25T14:35:22Z"
        }
    }


def test_render_analysis_panel_complete(renderer, analysis_output):
    """Test rendering complete analysis panel."""
    panel = renderer.render_analysis(
        status=StageStatus.COMPLETE,
        elapsed_ms=2300,
        output=analysis_output
    )
    assert isinstance(panel, Panel)
    # Check panel has content (render to string to verify)
    console = Console(force_terminal=True, width=100)
    with console.capture() as capture:
        console.print(panel)
    output = capture.get()
    assert "BTCUSDT" in output or "Analysis" in output


def test_render_analysis_panel_no_signal(renderer):
    """Test rendering analysis panel with no trade."""
    output = {
        "analysis_report": {"symbol": "ETHUSDT"},
        "proposed_signal": None
    }
    panel = renderer.render_analysis(
        status=StageStatus.COMPLETE,
        elapsed_ms=1800,
        output=output
    )
    assert isinstance(panel, Panel)


def test_render_risk_panel_approve(renderer, risk_output):
    """Test rendering risk panel with approval."""
    risk_output["risk_decision"]["action"] = "APPROVE"
    panel = renderer.render_risk(
        status=StageStatus.COMPLETE,
        elapsed_ms=1800,
        output=risk_output,
        previous_signal={"confidence": 72, "position_size_pct": 3.0}
    )
    assert isinstance(panel, Panel)


def test_render_risk_panel_reject(renderer):
    """Test rendering risk panel with rejection."""
    output = {
        "risk_decision": {
            "action": "REJECT",
            "reason": "Daily loss limit exceeded",
            "risk_score": 85
        },
        "audited_signal": None,
        "portfolio_snapshot": {"equity": 9500}
    }
    panel = renderer.render_risk(
        status=StageStatus.COMPLETE,
        elapsed_ms=1500,
        output=output,
        previous_signal={"confidence": 72}
    )
    assert isinstance(panel, Panel)


def test_render_execution_panel_filled(renderer, execution_output):
    """Test rendering execution panel with filled order."""
    panel = renderer.render_execution(
        status=StageStatus.COMPLETE,
        elapsed_ms=900,
        output=execution_output
    )
    assert isinstance(panel, Panel)


def test_render_execution_panel_aborted(renderer):
    """Test rendering execution panel with aborted order."""
    output = {
        "execution_report": {
            "status": "ABORTED",
            "reason": "Price moved 3% against entry",
            "requested_entry": 67500.0,
            "current_price": 69525.0,
            "price_deviation_pct": 3.0
        },
        "position_opened": None
    }
    panel = renderer.render_execution(
        status=StageStatus.COMPLETE,
        elapsed_ms=1200,
        output=output
    )
    assert isinstance(panel, Panel)


def test_render_running_panel(renderer):
    """Test rendering running state panel."""
    panel = renderer.render_running(
        stage_name="Risk Auditor",
        stage_number=2,
        elapsed_ms=1200,
        message="Checking correlation limits..."
    )
    assert isinstance(panel, Panel)
    console = Console(force_terminal=True, width=100)
    with console.capture() as capture:
        console.print(panel)
    output = capture.get()
    assert "Running" in output or "1.2" in output


def test_render_pending_panel(renderer):
    """Test rendering pending state panel."""
    panel = renderer.render_pending(
        stage_name="Execution Agent",
        stage_number=3
    )
    assert isinstance(panel, Panel)


def test_standalone_functions():
    """Test standalone render functions work."""
    # These are convenience wrappers
    assert render_pending_panel("Test", 1) is not None
    assert render_running_panel("Test", 1, 500) is not None
