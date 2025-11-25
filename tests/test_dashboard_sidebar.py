"""Tests for dashboard sidebar components."""
import pytest
from rich.console import Console
from rich.panel import Panel

from src.agent.pipeline.dashboard.sidebar import (
    SidebarRenderer,
    render_portfolio_panel,
    render_agent_stats_panel
)


@pytest.fixture
def renderer():
    """Create renderer instance."""
    return SidebarRenderer()


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
    """Sample agent statistics."""
    return {
        "analyzed": 12,
        "approved": 8,
        "rejected": 2,
        "modified": 2,
        "executed": 6,
        "aborted": 2,
        "win_rate": 66.7
    }


def test_render_portfolio_panel(renderer, portfolio_state):
    """Test rendering portfolio panel."""
    panel = renderer.render_portfolio(portfolio_state)
    assert isinstance(panel, Panel)

    console = Console(force_terminal=True, width=50)
    with console.capture() as capture:
        console.print(panel)
    output = capture.get()

    assert "10,450" in output or "10450" in output
    assert "12" in output  # exposure
    assert "1.2" in output  # daily pnl


def test_render_portfolio_panel_negative_pnl(renderer):
    """Test portfolio with negative P&L shows red."""
    state = {
        "equity": 9500.0,
        "open_positions": 2,
        "current_exposure_pct": 8.0,
        "daily_pnl_pct": -2.5,
        "weekly_pnl_pct": -4.2
    }
    panel = renderer.render_portfolio(state)
    assert isinstance(panel, Panel)


def test_render_agent_stats_panel(renderer, agent_stats):
    """Test rendering agent stats panel."""
    panel = renderer.render_agent_stats(agent_stats)
    assert isinstance(panel, Panel)

    console = Console(force_terminal=True, width=50)
    with console.capture() as capture:
        console.print(panel)
    output = capture.get()

    assert "12" in output  # analyzed
    assert "66" in output or "67" in output  # win rate


def test_render_agent_stats_no_trades(renderer):
    """Test agent stats with no trades."""
    stats = {
        "analyzed": 5,
        "approved": 0,
        "rejected": 5,
        "modified": 0,
        "executed": 0,
        "aborted": 0,
        "win_rate": 0.0
    }
    panel = renderer.render_agent_stats(stats)
    assert isinstance(panel, Panel)


def test_render_portfolio_empty_state(renderer):
    """Test portfolio with empty/default state."""
    panel = renderer.render_portfolio({})
    assert isinstance(panel, Panel)


def test_standalone_functions(portfolio_state, agent_stats):
    """Test standalone render functions."""
    portfolio_panel = render_portfolio_panel(portfolio_state)
    assert isinstance(portfolio_panel, Panel)

    stats_panel = render_agent_stats_panel(agent_stats)
    assert isinstance(stats_panel, Panel)
