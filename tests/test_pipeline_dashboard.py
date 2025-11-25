"""Tests for main pipeline dashboard."""
import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch
from rich.console import Console
from rich.layout import Layout

from src.agent.pipeline.dashboard.pipeline_dashboard import (
    PipelineDashboard,
    DashboardConfig
)
from src.agent.pipeline.dashboard.events import StageEvent, StageStatus, PipelineState


@pytest.fixture
def dashboard():
    """Create dashboard instance."""
    return PipelineDashboard()


@pytest.fixture
def dashboard_with_config():
    """Create dashboard with custom config."""
    config = DashboardConfig(
        show_sidebar=True,
        show_history=True,
        max_history=5
    )
    return PipelineDashboard(config=config)


@pytest.fixture
def portfolio_state():
    """Sample portfolio state."""
    return {
        "equity": 10450.0,
        "open_positions": 3,
        "current_exposure_pct": 12.0,
        "daily_pnl_pct": 1.2,
        "weekly_pnl_pct": 3.8
    }


@pytest.fixture
def agent_stats():
    """Sample agent stats."""
    return {
        "analyzed": 12,
        "approved": 8,
        "rejected": 2,
        "modified": 2,
        "executed": 6,
        "aborted": 2,
        "win_rate": 66.7
    }


def test_dashboard_creation(dashboard):
    """Test dashboard can be created."""
    assert dashboard is not None
    assert dashboard.state is None


def test_dashboard_start_pipeline(dashboard):
    """Test starting a new pipeline run."""
    dashboard.start_pipeline(symbol="BTCUSDT", session_id="test-123")

    assert dashboard.state is not None
    assert dashboard.state.symbol == "BTCUSDT"
    assert dashboard.state.session_id == "test-123"


def test_dashboard_handle_event(dashboard):
    """Test handling stage events."""
    dashboard.start_pipeline(symbol="BTCUSDT", session_id="test-123")

    event = StageEvent(
        stage="analysis",
        status=StageStatus.COMPLETE,
        symbol="BTCUSDT",
        elapsed_ms=2300,
        output={"proposed_signal": {"direction": "LONG"}}
    )

    dashboard.handle_event(event)

    assert dashboard.state.stages["analysis"]["status"] == StageStatus.COMPLETE


def test_dashboard_update_portfolio(dashboard, portfolio_state):
    """Test updating portfolio state."""
    dashboard.update_portfolio(portfolio_state)
    assert dashboard.portfolio_state == portfolio_state


def test_dashboard_update_stats(dashboard, agent_stats):
    """Test updating agent stats."""
    dashboard.update_stats(agent_stats)
    assert dashboard.agent_stats == agent_stats


def test_dashboard_build_layout(dashboard_with_config, portfolio_state, agent_stats):
    """Test building the complete layout."""
    dashboard_with_config.start_pipeline(symbol="BTCUSDT", session_id="test-123")
    dashboard_with_config.update_portfolio(portfolio_state)
    dashboard_with_config.update_stats(agent_stats)

    layout = dashboard_with_config.build_layout()

    assert isinstance(layout, Layout)


def test_dashboard_finalize_pipeline(dashboard):
    """Test finalizing pipeline run."""
    dashboard.start_pipeline(symbol="BTCUSDT", session_id="test-123")
    dashboard.finalize_pipeline(outcome="EXECUTED", detail="+1.5%")

    assert len(dashboard.history.entries) == 1
    assert dashboard.history.entries[0].outcome == "EXECUTED"


def test_dashboard_render_no_pipeline(dashboard):
    """Test rendering when no pipeline is active."""
    # Should not crash
    layout = dashboard.build_layout()
    assert layout is not None


def test_config_defaults():
    """Test default configuration."""
    config = DashboardConfig()
    assert config.show_sidebar is True
    assert config.show_history is True
    assert config.max_history == 10
