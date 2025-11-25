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
