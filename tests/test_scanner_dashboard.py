# tests/test_scanner_dashboard.py
"""Tests for scanner dashboard component."""
import pytest
from datetime import datetime
from unittest.mock import MagicMock

from src.agent.scanner.dashboard import (
    MoverStatus,
    CycleState,
    ScannerEvent,
    ScannerDashboard,
)


class TestMoverStatus:
    """Tests for MoverStatus dataclass."""

    def test_create_gainer_mover(self):
        """Test creating a gainer mover status."""
        mover = MoverStatus(
            symbol="BTCUSDT",
            change_pct=7.2,
            direction="gainer",
            status="pending",
        )
        assert mover.symbol == "BTCUSDT"
        assert mover.change_pct == 7.2
        assert mover.direction == "gainer"
        assert mover.status == "pending"
        assert mover.stage is None
        assert mover.result is None

    def test_create_loser_mover(self):
        """Test creating a loser mover status."""
        mover = MoverStatus(
            symbol="SOLUSDT",
            change_pct=-6.1,
            direction="loser",
            status="analyzing",
            stage="analysis",
            stage_detail="sentiment",
        )
        assert mover.symbol == "SOLUSDT"
        assert mover.change_pct == -6.1
        assert mover.direction == "loser"
        assert mover.stage == "analysis"
        assert mover.stage_detail == "sentiment"

    def test_complete_mover_with_result(self):
        """Test a completed mover with result data."""
        mover = MoverStatus(
            symbol="ETHUSDT",
            change_pct=5.8,
            direction="gainer",
            status="complete",
            stage="execution",
            result="EXECUTED",
            confidence=75,
            entry_price=3450.0,
        )
        assert mover.result == "EXECUTED"
        assert mover.confidence == 75
        assert mover.entry_price == 3450.0


class TestCycleState:
    """Tests for CycleState dataclass."""

    def test_create_empty_cycle(self):
        """Test creating an empty cycle state."""
        cycle = CycleState(
            cycle_number=5,
            started_at=datetime.now(),
            movers=[],
        )
        assert cycle.cycle_number == 5
        assert cycle.movers == []
        assert cycle.signals_generated == 0
        assert cycle.trades_executed == 0
        assert cycle.trades_rejected == 0

    def test_create_cycle_with_movers(self):
        """Test creating a cycle with movers."""
        movers = [
            MoverStatus("BTCUSDT", 7.2, "gainer", "complete", result="NO_TRADE"),
            MoverStatus("ETHUSDT", 5.8, "gainer", "analyzing"),
            MoverStatus("SOLUSDT", -6.1, "loser", "pending"),
        ]
        cycle = CycleState(
            cycle_number=5,
            started_at=datetime.now(),
            movers=movers,
            signals_generated=2,
            trades_executed=1,
        )
        assert len(cycle.movers) == 3
        assert cycle.signals_generated == 2
        assert cycle.trades_executed == 1


class TestScannerEvent:
    """Tests for ScannerEvent constants."""

    def test_event_types_exist(self):
        """Test that all event types are defined."""
        assert ScannerEvent.CYCLE_START == "cycle_start"
        assert ScannerEvent.MOVER_START == "mover_start"
        assert ScannerEvent.ANALYSIS_PHASE == "analysis_phase"
        assert ScannerEvent.SIGNAL_GENERATED == "signal_generated"
        assert ScannerEvent.RISK_CHECK == "risk_check"
        assert ScannerEvent.EXECUTION == "execution"
        assert ScannerEvent.MOVER_COMPLETE == "mover_complete"
        assert ScannerEvent.CYCLE_COMPLETE == "cycle_complete"


class TestScannerDashboard:
    """Tests for ScannerDashboard class."""

    def test_create_dashboard(self):
        """Test creating a scanner dashboard."""
        dashboard = ScannerDashboard()
        assert dashboard.current_cycle is None
        assert dashboard.history == []

    def test_start_cycle(self):
        """Test starting a new scan cycle."""
        dashboard = ScannerDashboard()
        movers_data = [
            {"symbol": "BTCUSDT", "change_pct": 7.2, "direction": "gainer"},
            {"symbol": "ETHUSDT", "change_pct": 5.8, "direction": "gainer"},
            {"symbol": "SOLUSDT", "change_pct": -6.1, "direction": "loser"},
        ]
        dashboard.start_cycle(cycle_number=5, movers=movers_data)

        assert dashboard.current_cycle is not None
        assert dashboard.current_cycle.cycle_number == 5
        assert len(dashboard.current_cycle.movers) == 3
        assert dashboard.current_cycle.movers[0].symbol == "BTCUSDT"
        assert dashboard.current_cycle.movers[0].status == "pending"

    def test_update_mover_status(self):
        """Test updating a mover's status."""
        dashboard = ScannerDashboard()
        dashboard.start_cycle(
            cycle_number=1,
            movers=[{"symbol": "BTCUSDT", "change_pct": 7.2, "direction": "gainer"}],
        )

        dashboard.update_mover(
            symbol="BTCUSDT",
            status="analyzing",
            stage="analysis",
            stage_detail="technical",
        )

        mover = dashboard.current_cycle.movers[0]
        assert mover.status == "analyzing"
        assert mover.stage == "analysis"
        assert mover.stage_detail == "technical"

    def test_complete_mover(self):
        """Test completing a mover analysis."""
        dashboard = ScannerDashboard()
        dashboard.start_cycle(
            cycle_number=1,
            movers=[{"symbol": "BTCUSDT", "change_pct": 7.2, "direction": "gainer"}],
        )

        dashboard.complete_mover(
            symbol="BTCUSDT",
            result="EXECUTED",
            confidence=72,
            entry_price=67500.0,
        )

        mover = dashboard.current_cycle.movers[0]
        assert mover.status == "complete"
        assert mover.result == "EXECUTED"
        assert mover.confidence == 72
        assert mover.entry_price == 67500.0

    def test_complete_cycle(self):
        """Test completing a cycle."""
        dashboard = ScannerDashboard()
        dashboard.start_cycle(
            cycle_number=1,
            movers=[
                {"symbol": "BTCUSDT", "change_pct": 7.2, "direction": "gainer"},
                {"symbol": "ETHUSDT", "change_pct": 5.8, "direction": "gainer"},
            ],
        )
        dashboard.complete_mover("BTCUSDT", "EXECUTED", confidence=72)
        dashboard.complete_mover("ETHUSDT", "NO_TRADE", confidence=45)

        dashboard.complete_cycle(
            signals_generated=2,
            trades_executed=1,
            trades_rejected=0,
        )

        assert dashboard.current_cycle.signals_generated == 2
        assert dashboard.current_cycle.trades_executed == 1
        assert len(dashboard.history) == 1
        assert dashboard.history[0].cycle_number == 1

    def test_get_cycle_progress(self):
        """Test getting cycle progress."""
        dashboard = ScannerDashboard()
        dashboard.start_cycle(
            cycle_number=1,
            movers=[
                {"symbol": "BTCUSDT", "change_pct": 7.2, "direction": "gainer"},
                {"symbol": "ETHUSDT", "change_pct": 5.8, "direction": "gainer"},
                {"symbol": "SOLUSDT", "change_pct": -6.1, "direction": "loser"},
            ],
        )
        dashboard.complete_mover("BTCUSDT", "NO_TRADE")

        progress = dashboard.get_cycle_progress()
        assert progress["total"] == 3
        assert progress["completed"] == 1
        assert progress["pending"] == 2

    def test_handle_event_cycle_start(self):
        """Test handling cycle_start event."""
        dashboard = ScannerDashboard()
        dashboard.handle_event(
            ScannerEvent.CYCLE_START,
            cycle_number=5,
            movers=[{"symbol": "BTCUSDT", "change_pct": 7.2, "direction": "gainer"}],
        )
        assert dashboard.current_cycle is not None
        assert dashboard.current_cycle.cycle_number == 5

    def test_handle_event_mover_start(self):
        """Test handling mover_start event."""
        dashboard = ScannerDashboard()
        dashboard.start_cycle(1, [{"symbol": "BTCUSDT", "change_pct": 7.2, "direction": "gainer"}])

        dashboard.handle_event(ScannerEvent.MOVER_START, symbol="BTCUSDT")

        assert dashboard.current_cycle.movers[0].status == "analyzing"

    def test_handle_event_analysis_phase(self):
        """Test handling analysis_phase event."""
        dashboard = ScannerDashboard()
        dashboard.start_cycle(1, [{"symbol": "BTCUSDT", "change_pct": 7.2, "direction": "gainer"}])
        dashboard.handle_event(ScannerEvent.MOVER_START, symbol="BTCUSDT")

        dashboard.handle_event(
            ScannerEvent.ANALYSIS_PHASE,
            symbol="BTCUSDT",
            phase="technical",
        )

        mover = dashboard.current_cycle.movers[0]
        assert mover.stage == "analysis"
        assert mover.stage_detail == "technical"

    def test_handle_event_signal_generated(self):
        """Test handling signal_generated event."""
        dashboard = ScannerDashboard()
        dashboard.start_cycle(1, [{"symbol": "BTCUSDT", "change_pct": 7.2, "direction": "gainer"}])
        dashboard.handle_event(ScannerEvent.MOVER_START, symbol="BTCUSDT")

        dashboard.handle_event(
            ScannerEvent.SIGNAL_GENERATED,
            symbol="BTCUSDT",
            confidence=72,
            entry_price=67500.0,
        )

        mover = dashboard.current_cycle.movers[0]
        assert mover.confidence == 72
        assert mover.entry_price == 67500.0

    def test_update_portfolio(self):
        """Test updating portfolio data."""
        dashboard = ScannerDashboard()
        dashboard.update_portfolio({
            "equity": 10450.0,
            "positions": 3,
            "exposure_pct": 12.0,
            "pnl_pct": 1.2,
        })
        assert dashboard.portfolio["equity"] == 10450.0
        assert dashboard.portfolio["positions"] == 3

    def test_update_stats(self):
        """Test updating cycle stats."""
        dashboard = ScannerDashboard()
        dashboard.update_stats({
            "total_signals": 5,
            "total_executed": 3,
            "win_rate": 66.7,
        })
        assert dashboard.stats["total_signals"] == 5
        assert dashboard.stats["win_rate"] == 66.7

    def test_render_returns_renderable(self):
        """Test that render method returns a Rich renderable."""
        dashboard = ScannerDashboard()
        dashboard.start_cycle(1, [{"symbol": "BTCUSDT", "change_pct": 7.2, "direction": "gainer"}])

        result = dashboard.render()
        # Should return a Rich Layout or similar renderable object
        assert result is not None
