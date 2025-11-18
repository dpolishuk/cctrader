"""Risk management configuration."""
import os
from dataclasses import dataclass, field
from typing import Dict, List
from enum import Enum

class ConfidenceTier(Enum):
    """Confidence tiers for position sizing."""
    HIGH = (80, 100, 2.5)       # (min, max, risk_pct)
    MEDIUM = (60, 79, 1.5)
    LOW = (0, 59, 0.0)

@dataclass
class RiskConfig:
    """Risk management configuration."""

    # Portfolio limits
    max_concurrent_positions: int = 5
    max_total_exposure_pct: float = 25.0

    # Loss limits
    daily_loss_limit_pct: float = -8.0
    weekly_loss_limit_pct: float = -15.0

    # Correlation limits
    max_correlated_positions: int = 2

    # Stop-loss parameters
    min_stop_distance_pct: float = 2.0
    max_stop_distance_pct: float = 5.0

    # Trailing stop parameters
    breakeven_trigger_pct: float = 1.0
    trailing_trigger_pct: float = 2.0
    trailing_distance_high_confidence: float = 2.5
    trailing_distance_medium_confidence: float = 2.0

    # Profit targets
    tp1_risk_reward_ratio: float = 2.0
    tp1_exit_percentage: float = 0.5

    # Correlation groups
    correlation_groups: Dict[str, List[str]] = field(default_factory=lambda: {
        'BTC_CORRELATED': ['BTC', 'ETH', 'BNB', 'SOL', 'ADA', 'AVAX', 'DOT', 'MATIC'],
        'DEFI': ['UNI', 'AAVE', 'COMP', 'MKR', 'SNX', 'CRV', 'SUSHI'],
        'GAMING': ['AXS', 'SAND', 'MANA', 'ENJ', 'GALA', 'ILV'],
        'AI': ['FET', 'AGIX', 'OCEAN', 'GRT'],
        'MEME': ['DOGE', 'SHIB', 'PEPE', 'FLOKI'],
        'LAYER2': ['ARB', 'OP', 'MATIC', 'IMX'],
    })

    def get_risk_pct_for_confidence(self, confidence: int) -> float:
        """Get risk percentage based on confidence score."""
        for tier in ConfidenceTier:
            min_conf, max_conf, risk_pct = tier.value
            if min_conf <= confidence <= max_conf:
                return risk_pct
        return 0.0

    def get_trailing_distance(self, confidence: int) -> float:
        """Get trailing stop distance based on confidence."""
        if confidence >= 80:
            return self.trailing_distance_high_confidence
        else:
            return self.trailing_distance_medium_confidence
