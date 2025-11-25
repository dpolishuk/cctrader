# tests/test_mover_row.py
"""Tests for mover row renderer component."""
import pytest
from rich.text import Text

from src.agent.pipeline.dashboard.mover_row import (
    MoverRowRenderer,
    MoverRowData,
    MoverRowStyle,
)


class TestMoverRowData:
    """Tests for MoverRowData dataclass."""

    def test_create_basic_mover_data(self):
        """Test creating basic mover row data."""
        data = MoverRowData(
            symbol="BTCUSDT",
            change_pct=7.2,
            direction="gainer",
            status="pending",
        )
        assert data.symbol == "BTCUSDT"
        assert data.change_pct == 7.2
        assert data.direction == "gainer"
        assert data.status == "pending"

    def test_create_complete_mover_data(self):
        """Test creating mover data with all fields."""
        data = MoverRowData(
            symbol="ETHUSDT",
            change_pct=5.8,
            direction="gainer",
            status="complete",
            stage="execution",
            stage_detail="filled",
            result="EXECUTED",
            confidence=72,
            entry_price=3450.0,
        )
        assert data.result == "EXECUTED"
        assert data.confidence == 72
        assert data.entry_price == 3450.0


class TestMoverRowStyle:
    """Tests for MoverRowStyle configuration."""

    def test_default_style(self):
        """Test default style settings."""
        style = MoverRowStyle()
        assert style.show_icon is True
        assert style.show_progress is True
        assert style.compact is False

    def test_compact_style(self):
        """Test compact style settings."""
        style = MoverRowStyle(compact=True)
        assert style.compact is True


class TestMoverRowRenderer:
    """Tests for MoverRowRenderer class."""

    def test_create_renderer(self):
        """Test creating a renderer."""
        renderer = MoverRowRenderer()
        assert renderer is not None

    def test_render_pending_gainer(self):
        """Test rendering a pending gainer."""
        renderer = MoverRowRenderer()
        data = MoverRowData(
            symbol="BTCUSDT",
            change_pct=7.2,
            direction="gainer",
            status="pending",
        )
        result = renderer.render(data)
        assert isinstance(result, Text)
        # Check contains key elements (symbol formatted without USDT suffix)
        plain = result.plain
        assert "BTC" in plain
        assert "7.2" in plain
        assert "Pending" in plain

    def test_render_pending_loser(self):
        """Test rendering a pending loser."""
        renderer = MoverRowRenderer()
        data = MoverRowData(
            symbol="SOLUSDT",
            change_pct=-6.1,
            direction="loser",
            status="pending",
        )
        result = renderer.render(data)
        plain = result.plain
        assert "SOL" in plain
        assert "6.1" in plain

    def test_render_analyzing_with_phase(self):
        """Test rendering an analyzing mover with phase progress."""
        renderer = MoverRowRenderer()
        data = MoverRowData(
            symbol="ETHUSDT",
            change_pct=5.8,
            direction="gainer",
            status="analyzing",
            stage="analysis",
            stage_detail="sentiment",
        )
        result = renderer.render(data)
        plain = result.plain
        assert "ETH" in plain
        assert "Analysis" in plain
        assert "sentiment" in plain

    def test_render_complete_executed(self):
        """Test rendering a completed executed mover."""
        renderer = MoverRowRenderer()
        data = MoverRowData(
            symbol="BTCUSDT",
            change_pct=7.2,
            direction="gainer",
            status="complete",
            result="EXECUTED",
            confidence=72,
            entry_price=67500.0,
        )
        result = renderer.render(data)
        plain = result.plain
        assert "BTC" in plain
        assert "EXECUTED" in plain
        assert "67,500" in plain

    def test_render_complete_no_trade(self):
        """Test rendering a completed no-trade mover."""
        renderer = MoverRowRenderer()
        data = MoverRowData(
            symbol="AVAXUSDT",
            change_pct=5.2,
            direction="gainer",
            status="complete",
            result="NO_TRADE",
            confidence=45,
        )
        result = renderer.render(data)
        plain = result.plain
        assert "AVAX" in plain
        assert "NO_TRADE" in plain
        assert "45" in plain

    def test_render_complete_rejected(self):
        """Test rendering a rejected mover."""
        renderer = MoverRowRenderer()
        data = MoverRowData(
            symbol="LINKUSDT",
            change_pct=-5.5,
            direction="loser",
            status="complete",
            result="REJECTED",
        )
        result = renderer.render(data)
        plain = result.plain
        assert "LINK" in plain
        assert "REJECTED" in plain

    def test_render_compact_mode(self):
        """Test rendering in compact mode."""
        style = MoverRowStyle(compact=True, show_progress=False)
        renderer = MoverRowRenderer(style=style)
        data = MoverRowData(
            symbol="BTCUSDT",
            change_pct=7.2,
            direction="gainer",
            status="complete",
            result="EXECUTED",
            entry_price=67500.0,
        )
        result = renderer.render(data)
        assert isinstance(result, Text)
        # Compact mode should still have essential info
        plain = result.plain
        assert "BTC" in plain or "BTCUSDT" in plain

    def test_render_multiple_rows(self):
        """Test rendering multiple rows."""
        renderer = MoverRowRenderer()
        data_list = [
            MoverRowData("BTCUSDT", 7.2, "gainer", "complete", result="NO_TRADE"),
            MoverRowData("ETHUSDT", 5.8, "gainer", "analyzing", stage_detail="sentiment"),
            MoverRowData("SOLUSDT", -6.1, "loser", "pending"),
        ]
        results = [renderer.render(d) for d in data_list]
        assert len(results) == 3
        assert all(isinstance(r, Text) for r in results)

    def test_format_symbol(self):
        """Test symbol formatting."""
        renderer = MoverRowRenderer()
        # Test various symbol formats
        assert "BTC" in renderer._format_symbol("BTCUSDT")
        assert "BTC" in renderer._format_symbol("BTC/USDT")
        assert "BTC" in renderer._format_symbol("BTC/USDT:USDT")

    def test_status_icon_mapping(self):
        """Test that status icons are correctly mapped."""
        renderer = MoverRowRenderer()
        data_pending = MoverRowData("TEST", 1.0, "gainer", "pending")
        data_analyzing = MoverRowData("TEST", 1.0, "gainer", "analyzing")
        data_complete = MoverRowData("TEST", 1.0, "gainer", "complete", result="EXECUTED")

        result_pending = renderer.render(data_pending)
        result_analyzing = renderer.render(data_analyzing)
        result_complete = renderer.render(data_complete)

        # Each status should have distinct visual representation
        assert result_pending.plain != result_analyzing.plain
        assert result_analyzing.plain != result_complete.plain
