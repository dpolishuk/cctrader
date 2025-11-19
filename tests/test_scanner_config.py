import pytest
from src.agent.scanner.config import ScannerConfig

def test_scanner_config_defaults():
    """Test scanner configuration has correct defaults."""
    config = ScannerConfig()

    assert config.scan_interval_seconds == 300
    assert config.mover_threshold_pct == 5.0
    assert config.max_movers_per_scan == 20
    assert config.min_volume_usd == 5_000_000
    assert config.min_confidence == 60
    assert config.monitoring_interval_seconds == 300

def test_scanner_config_from_env(monkeypatch):
    """Test scanner configuration from environment variables."""
    monkeypatch.setenv('SCAN_INTERVAL', '600')
    monkeypatch.setenv('MOVER_THRESHOLD', '7.0')

    config = ScannerConfig()

    assert config.scan_interval_seconds == 600
    assert config.mover_threshold_pct == 7.0
