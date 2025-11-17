"""Database operations for trading agent."""
import aiosqlite
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path

class TradingDatabase:
    def __init__(self, db_path: Path):
        self.db_path = db_path

    async def save_signal(
        self,
        symbol: str,
        signal_type: str,
        confidence: float,
        price: float,
        timeframe: str,
        reason: str,
        technical_data: Dict,
        sentiment_data: Dict
    ) -> int:
        """Save a trading signal to the database."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                INSERT INTO signals
                (symbol, signal_type, confidence, price, timeframe, reason, technical_data, sentiment_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (symbol, signal_type, confidence, price, timeframe, reason,
                 json.dumps(technical_data), json.dumps(sentiment_data))
            )
            await db.commit()
            return cursor.lastrowid

    async def save_technical_analysis(
        self,
        symbol: str,
        timeframe: str,
        indicators: Dict[str, Any]
    ) -> int:
        """Save technical analysis results."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                INSERT INTO technical_analysis
                (symbol, timeframe, rsi, macd, macd_signal, macd_hist,
                 bb_upper, bb_middle, bb_lower, volume, price, additional_indicators)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    symbol, timeframe,
                    indicators.get('rsi'), indicators.get('macd'),
                    indicators.get('macd_signal'), indicators.get('macd_hist'),
                    indicators.get('bb_upper'), indicators.get('bb_middle'),
                    indicators.get('bb_lower'), indicators.get('volume'),
                    indicators.get('price'), json.dumps(indicators.get('additional', {}))
                )
            )
            await db.commit()
            return cursor.lastrowid

    async def get_recent_signals(
        self,
        symbol: str,
        limit: int = 10
    ) -> List[Dict]:
        """Retrieve recent signals for a symbol."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """
                SELECT * FROM signals
                WHERE symbol = ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (symbol, limit)
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def get_portfolio_position(self, symbol: str) -> Optional[Dict]:
        """Get current portfolio position for a symbol."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM portfolio_state WHERE symbol = ?",
                (symbol,)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None
