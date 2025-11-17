"""Configuration management."""
import os
from dataclasses import dataclass
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
    TIMEFRAMES: List[str] = ["1m", "5m", "15m", "1h", "4h", "1d"]

    # Database
    DB_PATH: str = os.getenv("DB_PATH", "./trading_data.db")

    # Agent Settings
    MAX_TURNS: int = int(os.getenv("MAX_TURNS", "20"))
    MAX_BUDGET_USD: float = float(os.getenv("MAX_BUDGET_USD", "1.0"))
    ANALYSIS_INTERVAL: int = int(os.getenv("ANALYSIS_INTERVAL", "300"))

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    def validate(self):
        """Validate configuration."""
        if not self.ANTHROPIC_API_KEY:
            raise ValueError("ANTHROPIC_API_KEY not set")
        if not self.BYBIT_API_KEY:
            raise ValueError("BYBIT_API_KEY not set")

config = Config()
