"""Confidence score calculation for trading signals."""
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

class ConfidenceCalculator:
    """Calculates multi-factor confidence scores (0-100)."""

    # Timeframe weights for technical analysis
    TIMEFRAME_WEIGHTS = {
        '4h': 0.30,
        '1h': 0.25,
        '15m': 0.20,
        '5m': 0.15,
        '1m': 0.10,
    }

    def calculate_technical_score(self, technical_data: Dict[str, Dict[str, Any]]) -> float:
        """
        Calculate technical alignment score (0-40 points).

        Args:
            technical_data: Dict of timeframe -> indicators

        Returns:
            Score 0-40
        """
        weighted_sum = 0.0

        for timeframe, weight in self.TIMEFRAME_WEIGHTS.items():
            if timeframe not in technical_data:
                continue

            data = technical_data[timeframe]
            points = 0

            # RSI scoring
            rsi = data.get('rsi', 50)
            if 30 <= rsi <= 70:
                points += 2
            elif rsi < 30:
                points += 1  # Oversold bounce potential
            elif rsi > 70:
                points -= 1  # Overbought

            # MACD scoring
            macd_signal = data.get('macd_signal', '')
            if macd_signal == 'bullish_cross':
                points += 2
            elif macd_signal == 'bearish_cross':
                points -= 2
            elif macd_signal == 'histogram_positive':
                points += 1

            # Bollinger Bands scoring
            bb_position = data.get('bb_position', 'middle')
            if bb_position in ['upper', 'lower']:
                points += 1

            # Volume scoring
            volume_ratio = data.get('volume_ratio', 1.0)
            if volume_ratio > 1.0:
                points += 2

            # Weight by timeframe
            max_points = 7  # Max possible per timeframe
            weighted_sum += (points / max_points) * weight * 40

        return min(weighted_sum, 40.0)

    def calculate_sentiment_score(self, sentiment_data: Dict[str, Any], direction: str) -> float:
        """
        Calculate sentiment score (0-30 points).

        Args:
            sentiment_data: Sentiment analysis results
            direction: 'LONG' or 'SHORT'

        Returns:
            Score 0-30
        """
        classification = sentiment_data.get('classification', 'NEUTRAL')

        # Base scores for LONG
        score_map = {
            'STRONG_POSITIVE': 27.5,
            'MILD_POSITIVE': 19.5,
            'NEUTRAL': 12.0,
            'MILD_NEGATIVE': 7.0,
            'STRONG_NEGATIVE': 2.0,
        }

        score = score_map.get(classification, 12.0)

        # Invert for SHORT positions
        if direction == 'SHORT':
            score = 30.0 - score

        return score

    def calculate_liquidity_score(self, liquidity_data: Dict[str, Any]) -> float:
        """
        Calculate liquidity score (0-20 points + bonuses).

        Args:
            liquidity_data: Liquidity metrics

        Returns:
            Score 0-20 (capped, but bonuses can push higher internally)
        """
        volume_ratio = liquidity_data.get('volume_ratio', 1.0)

        # Base score from volume
        if volume_ratio >= 2.0:
            score = 20
        elif volume_ratio >= 1.5:
            score = 15
        elif volume_ratio >= 1.0:
            score = 10
        else:
            score = 5

        # Bonuses (but cap total at 20)
        bid_ask_spread = liquidity_data.get('bid_ask_spread_pct', 0.1)
        if bid_ask_spread < 0.05:
            score = min(score + 5, 20)

        order_book_depth = liquidity_data.get('order_book_depth_usd', 0)
        if order_book_depth > 500_000:
            score = min(score + 3, 20)

        return min(score, 20.0)

    def calculate_correlation_score(self, correlation_data: Dict[str, Any]) -> float:
        """
        Calculate BTC correlation score (0-10 points + bonus).

        Args:
            correlation_data: BTC correlation metrics

        Returns:
            Score 0-10
        """
        btc_change = correlation_data.get('btc_change_1h', 0)
        symbol_change = correlation_data.get('symbol_change_1h', 0)
        relative_strength = symbol_change - btc_change

        # Base score
        if btc_change > 0:  # BTC uptrend
            score = 10 if symbol_change > 0 else 5
        else:  # BTC downtrend
            score = 7 if symbol_change > 0 else 3

        # Bonus for strong outperformance
        if relative_strength > 3.0:
            score = min(score + 3, 10)

        return min(score, 10.0)

    def calculate_final_confidence(
        self,
        technical: float,
        sentiment: float,
        liquidity: float,
        correlation: float
    ) -> int:
        """
        Calculate final confidence score.

        Args:
            technical: Technical score (0-40)
            sentiment: Sentiment score (0-30)
            liquidity: Liquidity score (0-20)
            correlation: Correlation score (0-10)

        Returns:
            Final confidence (0-100)
        """
        confidence = technical + sentiment + liquidity + correlation
        confidence = min(max(confidence, 0), 100)  # Clamp 0-100
        return int(confidence)
