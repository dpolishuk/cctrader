"""Scanner configuration."""
import os
from dataclasses import dataclass, field

@dataclass
class ScannerConfig:
    """Configuration for market movers scanner."""

    # Scanning parameters
    scan_interval_seconds: int = field(default_factory=lambda: int(os.getenv('SCAN_INTERVAL', '300')))
    mover_threshold_pct: float = field(default_factory=lambda: float(os.getenv('MOVER_THRESHOLD', '5.0')))
    max_movers_per_scan: int = field(default_factory=lambda: int(os.getenv('MAX_MOVERS_PER_SCAN', '20')))
    min_volume_usd: float = field(default_factory=lambda: float(os.getenv('MIN_VOLUME_USD', '5000000')))

    # Agent analysis
    min_confidence: int = field(default_factory=lambda: int(os.getenv('MIN_CONFIDENCE', '60')))
    agent_timeout_seconds: int = field(default_factory=lambda: int(os.getenv('AGENT_TIMEOUT', '120')))
    max_search_queries_per_cycle: int = 20

    # Sentiment analysis toggle
    use_sentiment: bool = True  # Set to False to disable sentiment scoring

    # Web search configuration
    web_search_mcp_url: str = field(default_factory=lambda: os.getenv('WEB_SEARCH_MCP_URL', 'http://localhost:3000/mcp'))
    web_search_timeout_seconds: int = field(default_factory=lambda: int(os.getenv('WEB_SEARCH_TIMEOUT', '30')))

    # Position management
    monitoring_interval_seconds: int = field(default_factory=lambda: int(os.getenv('MONITORING_INTERVAL', '300')))
    reanalysis_interval_seconds: int = 900
    trailing_stop_update_seconds: int = 300
