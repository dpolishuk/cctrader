import pytest
from agent.scanner.risk_config import RiskConfig, ConfidenceTier

def test_risk_config_defaults():
    """Test risk configuration has correct portfolio limits."""
    config = RiskConfig()

    assert config.max_concurrent_positions == 5
    assert config.max_total_exposure_pct == 25.0
    assert config.daily_loss_limit_pct == -8.0
    assert config.weekly_loss_limit_pct == -15.0
    assert config.max_correlated_positions == 2

def test_confidence_tier_risk_calculation():
    """Test position sizing based on confidence tiers."""
    config = RiskConfig()

    # High confidence: 80-100 → 2.5% risk
    high_risk = config.get_risk_pct_for_confidence(85)
    assert high_risk == 2.5

    # Medium confidence: 60-79 → 1.5% risk
    medium_risk = config.get_risk_pct_for_confidence(70)
    assert medium_risk == 1.5

    # Low confidence: <60 → 0% (no trade)
    low_risk = config.get_risk_pct_for_confidence(50)
    assert low_risk == 0.0

def test_correlation_groups():
    """Test correlation group definitions."""
    config = RiskConfig()

    assert 'BTC_CORRELATED' in config.correlation_groups
    assert 'BTC' in config.correlation_groups['BTC_CORRELATED']
    assert 'ETH' in config.correlation_groups['BTC_CORRELATED']
    assert 'DEFI' in config.correlation_groups
