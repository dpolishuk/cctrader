"""Tests for token pricing calculator."""
import pytest
from src.agent.tracking.pricing import TokenPricingCalculator


def test_calculate_cost_default_pricing():
    """Test cost calculation with default Sonnet 4.5 pricing."""
    calculator = TokenPricingCalculator()

    cost = calculator.calculate_cost(
        tokens_input=1_000_000,
        tokens_output=500_000
    )

    # $3/1M input + $15/1M output * 0.5M = $3 + $7.50 = $10.50
    assert cost == 10.50


def test_calculate_cost_custom_pricing():
    """Test cost calculation with custom pricing."""
    calculator = TokenPricingCalculator(
        cost_per_1m_input=2.0,
        cost_per_1m_output=10.0
    )

    cost = calculator.calculate_cost(
        tokens_input=500_000,
        tokens_output=250_000
    )

    # $2/1M * 0.5M + $10/1M * 0.25M = $1 + $2.50 = $3.50
    assert cost == 3.50


def test_calculate_cost_zero_tokens():
    """Test cost calculation with zero tokens."""
    calculator = TokenPricingCalculator()

    cost = calculator.calculate_cost(
        tokens_input=0,
        tokens_output=0
    )

    assert cost == 0.0


def test_get_pricing_info():
    """Test getting pricing information."""
    calculator = TokenPricingCalculator()

    info = calculator.get_pricing_info()

    assert info['cost_per_1m_input'] == 3.0
    assert info['cost_per_1m_output'] == 15.0
    assert 'model' in info
