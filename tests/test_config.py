import pytest
from src.agent.config import config


def test_token_interval_minutes_config():
    """Test TOKEN_INTERVAL_MINUTES configuration."""
    assert hasattr(config, 'TOKEN_INTERVAL_MINUTES')
    assert config.TOKEN_INTERVAL_MINUTES == 5
    assert isinstance(config.TOKEN_INTERVAL_MINUTES, int)
