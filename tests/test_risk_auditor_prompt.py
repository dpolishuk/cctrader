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
