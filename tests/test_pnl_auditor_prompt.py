# tests/test_pnl_auditor_prompt.py
"""Tests for P&L auditor agent prompt."""
import pytest

from src.agent.agents.prompts.pnl_auditor_prompt import (
    build_trade_review_prompt,
    build_daily_report_prompt,
    PNL_AUDITOR_SYSTEM_PROMPT
)


def test_pnl_auditor_system_prompt_exists():
    """Test that system prompt is defined."""
    assert PNL_AUDITOR_SYSTEM_PROMPT is not None
    assert len(PNL_AUDITOR_SYSTEM_PROMPT) > 100
    assert "P&L Auditor" in PNL_AUDITOR_SYSTEM_PROMPT


def test_build_trade_review_prompt():
    """Test building trade review prompt."""
    trade = {
        "trade_id": "TRD-123",
        "symbol": "BTCUSDT",
        "direction": "LONG",
        "entry_price": 50000,
        "exit_price": 52500,
        "pnl_pct": 5.0,
        "pnl_usd": 250.0
    }

    prompt = build_trade_review_prompt(trade=trade)

    assert "TRD-123" in prompt
    assert "BTCUSDT" in prompt
    assert "5.0" in prompt or "5%" in prompt


def test_build_daily_report_prompt():
    """Test building daily report prompt."""
    trades = [
        {"symbol": "BTCUSDT", "pnl_pct": 5.0},
        {"symbol": "ETHUSDT", "pnl_pct": -2.0}
    ]

    prompt = build_daily_report_prompt(
        date="2025-01-25",
        trades=trades
    )

    assert "2025-01-25" in prompt
    assert "BTCUSDT" in prompt


def test_pnl_auditor_mentions_modes():
    """Test that prompt mentions TRADE_REVIEW and DAILY_REPORT."""
    assert "TRADE_REVIEW" in PNL_AUDITOR_SYSTEM_PROMPT
    assert "DAILY_REPORT" in PNL_AUDITOR_SYSTEM_PROMPT
