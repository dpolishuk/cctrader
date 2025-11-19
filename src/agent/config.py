"""Configuration management."""
import os
from dataclasses import dataclass, field
from typing import List
from dotenv import load_dotenv

load_dotenv()

@dataclass
class Config:
    # API Keys
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    BYBIT_API_KEY: str = os.getenv("BYBIT_API_KEY", "")
    BYBIT_API_SECRET: str = os.getenv("BYBIT_API_SECRET", "")

    # Exchange Settings
    BYBIT_TESTNET: bool = os.getenv("BYBIT_TESTNET", "false").lower() == "true"
    DEFAULT_SYMBOL: str = os.getenv("DEFAULT_SYMBOL", "BTC/USDT")

    # Timeframes
    TIMEFRAMES: List[str] = field(default_factory=lambda: ["1m", "5m", "15m", "1h", "4h", "1d"])

    # Database
    DB_PATH: str = os.getenv("DB_PATH", "./trading_data.db")

    # Agent Settings
    MAX_TURNS: int = int(os.getenv("MAX_TURNS", "20"))
    MAX_BUDGET_USD: float = float(os.getenv("MAX_BUDGET_USD", "1.0"))
    ANALYSIS_INTERVAL: int = int(os.getenv("ANALYSIS_INTERVAL", "300"))

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # Token Tracking
    TOKEN_TRACKING_ENABLED: bool = os.getenv("TOKEN_TRACKING_ENABLED", "true").lower() == "true"
    CLAUDE_HOURLY_LIMIT: int = int(os.getenv("CLAUDE_HOURLY_LIMIT", "500"))
    CLAUDE_DAILY_LIMIT: int = int(os.getenv("CLAUDE_DAILY_LIMIT", "5000"))
    CLAUDE_COST_PER_1M_INPUT: float = float(os.getenv("CLAUDE_COST_PER_1M_INPUT", "3.00"))
    CLAUDE_COST_PER_1M_OUTPUT: float = float(os.getenv("CLAUDE_COST_PER_1M_OUTPUT", "15.00"))
    TOKEN_WARNING_THRESHOLD: int = int(os.getenv("TOKEN_WARNING_THRESHOLD", "50"))
    TOKEN_CRITICAL_THRESHOLD: int = int(os.getenv("TOKEN_CRITICAL_THRESHOLD", "80"))
    TOKEN_HISTORY_DAYS: int = int(os.getenv("TOKEN_HISTORY_DAYS", "90"))

    def validate(self):
        """Validate configuration."""
        if not self.ANTHROPIC_API_KEY:
            raise ValueError("ANTHROPIC_API_KEY not set")
        if not self.BYBIT_API_KEY:
            raise ValueError("BYBIT_API_KEY not set")

config = Config()
