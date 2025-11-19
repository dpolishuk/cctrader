import pytest
from src.agent.scanner.prompts import PromptBuilder

def test_build_analysis_prompt():
    """Test building agent analysis prompt."""
    builder = PromptBuilder()

    mover_context = {
        'symbol': 'SOLUSDT',
        'direction': 'LONG',
        'change_1h': 7.2,
        'change_4h': 5.8,
        'current_price': 145.30,
        'volume_24h': 1_200_000_000,
    }

    portfolio_context = {
        'total_value': 10000,
        'open_positions': 2,
        'exposure_pct': 15.0,
    }

    prompt = builder.build_analysis_prompt(mover_context, portfolio_context)

    assert 'SOLUSDT' in prompt
    assert 'LONG' in prompt
    assert '+7.2' in prompt  # Check for the value (works with both 7.2% and 7.20%)
    assert 'multi-timeframe' in prompt.lower()
    assert 'perplexity' in prompt.lower()
    assert 'confidence' in prompt.lower()
    assert '60' in prompt  # Min confidence threshold

def test_build_reanalysis_prompt():
    """Test building position re-analysis prompt."""
    builder = PromptBuilder()

    position = {
        'symbol': 'BTCUSDT',
        'direction': 'LONG',
        'entry_price': 90000,
        'current_price': 91500,
        'pnl_pct': 1.67,
        'original_confidence': 78,
        'duration_minutes': 45,
    }

    prompt = builder.build_reanalysis_prompt(position)

    assert 'BTCUSDT' in prompt
    assert 'Re-analyze' in prompt
    assert '90000' in prompt or '90,000' in prompt
    assert 'confidence' in prompt.lower()
    assert 'sentiment changed' in prompt.lower()
