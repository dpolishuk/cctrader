# tests/test_analysis_prompt.py
"""Tests for analysis agent prompt."""
import pytest

from src.agent.agents.prompts.analysis_prompt import (
    build_analysis_prompt,
    ANALYSIS_SYSTEM_PROMPT
)


def test_analysis_system_prompt_exists():
    """Test that system prompt is defined."""
    assert ANALYSIS_SYSTEM_PROMPT is not None
    assert len(ANALYSIS_SYSTEM_PROMPT) > 100
    assert "Analysis Agent" in ANALYSIS_SYSTEM_PROMPT


def test_build_analysis_prompt_basic():
    """Test building basic analysis prompt."""
    prompt = build_analysis_prompt(
        symbol="BTCUSDT",
        momentum_1h=5.0,
        momentum_4h=10.0,
        current_price=50000.0,
        volume_24h=1000000000.0
    )

    assert "BTCUSDT" in prompt
    assert "5.0" in prompt or "5%" in prompt
    assert "50000" in prompt or "50,000" in prompt


def test_build_analysis_prompt_with_context():
    """Test building prompt with additional context."""
    prompt = build_analysis_prompt(
        symbol="ETHUSDT",
        momentum_1h=-3.0,
        momentum_4h=-8.0,
        current_price=3000.0,
        volume_24h=500000000.0,
        additional_context="Market is in a downtrend"
    )

    assert "ETHUSDT" in prompt
    assert "downtrend" in prompt.lower() or "Market is in a downtrend" in prompt


def test_analysis_prompt_mentions_output_format():
    """Test that prompt instructs on output format."""
    assert "JSON" in ANALYSIS_SYSTEM_PROMPT or "json" in ANALYSIS_SYSTEM_PROMPT
    assert "analysis_report" in ANALYSIS_SYSTEM_PROMPT
    assert "proposed_signal" in ANALYSIS_SYSTEM_PROMPT
