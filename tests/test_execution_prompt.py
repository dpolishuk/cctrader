# tests/test_execution_prompt.py
"""Tests for execution agent prompt."""
import pytest

from src.agent.agents.prompts.execution_prompt import (
    build_execution_prompt,
    EXECUTION_SYSTEM_PROMPT
)


def test_execution_system_prompt_exists():
    """Test that system prompt is defined."""
    assert EXECUTION_SYSTEM_PROMPT is not None
    assert len(EXECUTION_SYSTEM_PROMPT) > 100
    assert "Execution Agent" in EXECUTION_SYSTEM_PROMPT


def test_build_execution_prompt():
    """Test building execution prompt."""
    audited_signal = {
        "direction": "LONG",
        "confidence": 68,
        "entry_price": 0.0407,
        "stop_loss": 0.0375,
        "take_profit": 0.0472,
        "position_size_pct": 2.5
    }

    prompt = build_execution_prompt(
        symbol="MONUSDT",
        audited_signal=audited_signal,
        portfolio_equity=10000.0
    )

    assert "MONUSDT" in prompt
    assert "0.0407" in prompt
    assert "LONG" in prompt


def test_execution_prompt_mentions_abort():
    """Test that prompt mentions abort conditions."""
    assert "ABORT" in EXECUTION_SYSTEM_PROMPT or "abort" in EXECUTION_SYSTEM_PROMPT
