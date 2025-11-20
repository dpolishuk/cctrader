"""Trading signal generation combining technical and sentiment analysis."""
from typing import Any, Dict
from claude_agent_sdk import tool
import json


def calculate_pattern_score(pattern_data: Dict[str, Any]) -> float:
    """
    Calculate score based on Fibonacci level position.

    Logic:
    - Near 0% or 23.6%: +0.5 to +1.0 (strong support, bullish)
    - Near 38.2%: +0.2 to +0.5 (moderate support)
    - Near 50%: -0.2 to +0.2 (neutral)
    - Near 61.8%: -0.5 to -0.2 (moderate resistance)
    - Near 78.6% or 100%: -1.0 to -0.5 (strong resistance, bearish)

    Args:
        pattern_data: Dictionary containing pattern analysis with current_level

    Returns:
        float: Score from -1.0 to 1.0
    """
    if not pattern_data:
        return 0.0

    current_level = pattern_data.get("current_level", "50.0")
    try:
        level_num = float(current_level)
    except (ValueError, TypeError):
        return 0.0

    if level_num < 30:  # Near swing low (0%, 23.6%)
        return 0.7
    elif level_num < 45:  # 38.2% zone
        return 0.3
    elif level_num < 55:  # 50% zone
        return 0.0
    elif level_num < 70:  # 61.8% zone
        return -0.3
    else:  # Near swing high (78.6%, 100%)
        return -0.7

@tool(
    name="generate_trading_signal",
    description="Generate buy/sell/hold signal based on technical and sentiment analysis",
    input_schema={
        "symbol": str,
        "technical_data": dict,
        "trend_data": dict,
        "momentum_data": dict,
        "volatility_data": dict,
        "pattern_data": dict,
        "sentiment_data": dict,
        "current_price": float
    }
)
async def generate_trading_signal(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Combine technical indicators and sentiment to generate trading signal.

    Signal logic:
    - Strong Buy: Bullish technicals + positive sentiment
    - Buy: Moderately bullish technicals or positive sentiment
    - Hold: Mixed signals
    - Sell: Bearish technicals or negative sentiment
    - Strong Sell: Bearish technicals + negative sentiment
    """
    try:
        symbol = args.get("symbol")
        technical = args.get("technical_data", {})
        trend_data = args.get("trend_data", {})
        momentum_data = args.get("momentum_data", {})
        volatility_data = args.get("volatility_data", {})
        pattern_data = args.get("pattern_data", {})
        sentiment = args.get("sentiment_data", {})
        price = args.get("current_price")

        # Extract technical indicators
        indicators = technical.get("indicators", {})
        interpretation = technical.get("interpretation", {})

        rsi = indicators.get("rsi", 50)
        macd_hist = indicators.get("macd_hist", 0)
        rsi_status = interpretation.get("rsi_status", "Neutral")
        macd_status = interpretation.get("macd_status", "Neutral")

        # Calculate classic technical score (RSI, MACD, BB)
        classic_score = 0.0

        # RSI contribution
        if rsi < 30:
            classic_score += 0.4  # Oversold = bullish
        elif rsi > 70:
            classic_score -= 0.4  # Overbought = bearish
        else:
            classic_score += (50 - rsi) / 100  # Neutral zone

        # MACD contribution
        if macd_hist > 0:
            classic_score += 0.3
        elif macd_hist < 0:
            classic_score -= 0.3

        # Bollinger Bands
        bb_status = interpretation.get("bb_status", "")
        if "Lower" in bb_status:
            classic_score += 0.3  # Near lower band = potential bounce
        elif "Upper" in bb_status:
            classic_score -= 0.3  # Near upper band = potential reversal

        # Extract new indicator scores
        trend_score = trend_data.get("trend_score", 0.5) if trend_data else 0.5  # 0.0-1.0
        momentum_score = momentum_data.get("momentum_score", 0.0) if momentum_data else 0.0  # -1.0 to 1.0
        volatility_score = volatility_data.get("volatility_score", 0.5) if volatility_data else 0.5  # 0.0-1.0
        pattern_score = calculate_pattern_score(pattern_data) if pattern_data else 0.0  # -1.0 to 1.0

        # Normalize scores to -1.0 to 1.0 range
        trend_normalized = (trend_score - 0.5) * 2  # 0-1 -> -1 to 1
        momentum_normalized = momentum_score  # Already -1 to 1
        pattern_normalized = pattern_score  # Already -1 to 1

        # Weighted technical score (Component weights sum to 1.0)
        # classic: 0.30, trend: 0.25, momentum: 0.25, volatility: 0.10, patterns: 0.10
        tech_score = (
            classic_score * 0.30 +
            trend_normalized * 0.25 +
            momentum_normalized * 0.25 +
            pattern_normalized * 0.10
        )

        # Apply volatility adjustment (reduce confidence in high volatility)
        if volatility_score > 0.7:  # High volatility
            confidence_adjustment = 0.8  # Reduce confidence by 20%
        else:
            confidence_adjustment = 1.0

        # Sentiment score (extract from sentiment_data)
        sentiment_score = sentiment.get("sentiment_score", 0.0)  # Assuming -1 to 1

        # Combined score (60% technical, 40% sentiment)
        combined_score = (tech_score * 0.6) + (sentiment_score * 0.4)

        # Generate signal
        if combined_score > 0.5:
            signal = "STRONG_BUY"
            confidence = min(abs(combined_score), 1.0) * confidence_adjustment
        elif combined_score > 0.2:
            signal = "BUY"
            confidence = abs(combined_score) * confidence_adjustment
        elif combined_score < -0.5:
            signal = "STRONG_SELL"
            confidence = min(abs(combined_score), 1.0) * confidence_adjustment
        elif combined_score < -0.2:
            signal = "SELL"
            confidence = abs(combined_score) * confidence_adjustment
        else:
            signal = "HOLD"
            confidence = (1.0 - abs(combined_score)) * confidence_adjustment

        # Generate reason
        reasons = []

        # Classic indicators
        if rsi_status != "Neutral":
            reasons.append(f"RSI: {rsi_status} ({rsi:.1f})")
        if macd_status != "Neutral":
            reasons.append(f"MACD: {macd_status}")

        # Sentiment
        if sentiment_score > 0.3:
            reasons.append("Positive market sentiment")
        elif sentiment_score < -0.3:
            reasons.append("Negative market sentiment")

        # New indicators
        if trend_data:
            raw_trend_score = trend_data.get("trend_score", 0.5)
            if raw_trend_score > 0.7:
                reasons.append("Strong uptrend (EMA/Ichimoku bullish)")
            elif raw_trend_score < 0.3:
                reasons.append("Strong downtrend (EMA/Ichimoku bearish)")

        if momentum_data:
            raw_momentum_score = momentum_data.get("momentum_score", 0.0)
            if raw_momentum_score > 0.5:
                reasons.append("Bullish momentum (Stochastic/Elder)")
            elif raw_momentum_score < -0.5:
                reasons.append("Bearish momentum (Stochastic/Elder)")

        if volatility_data:
            vol_score = volatility_data.get("volatility_score", 0.5)
            if vol_score > 0.7:
                reasons.append("High volatility - use wider stops")

        if pattern_data:
            current_level = pattern_data.get("current_level", "")
            if current_level:
                reasons.append(f"At Fibonacci {current_level}% level")

        reason = " | ".join(reasons) if reasons else "Mixed signals"

        signal_text = f"""
🎯 TRADING SIGNAL for {symbol}

Signal: {signal}
Confidence: {confidence:.1%}
Current Price: ${price:.2f}

Score Breakdown:
  Classic (RSI/MACD/BB): {classic_score:.2f}
  Trend (EMA/Ichimoku): {trend_normalized:.2f}
  Momentum (Stoch/Elder): {momentum_normalized:.2f}
  Patterns (Fibonacci): {pattern_normalized:.2f}
  Technical Score: {tech_score:.2f} (60% weight)
  Sentiment Score: {sentiment_score:.2f} (40% weight)
  Combined Score: {combined_score:.2f}

Volatility Adjustment: {confidence_adjustment:.0%}

Reasoning: {reason}
"""

        return {
            "content": [{"type": "text", "text": signal_text}],
            "signal": {
                "type": signal,
                "confidence": confidence,
                "price": price,
                "classic_score": classic_score,
                "trend_score": trend_normalized,
                "momentum_score": momentum_normalized,
                "pattern_score": pattern_normalized,
                "technical_score": tech_score,
                "sentiment_score": sentiment_score,
                "combined_score": combined_score,
                "volatility_adjustment": confidence_adjustment,
                "reason": reason
            }
        }

    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Error generating signal: {str(e)}"}],
            "is_error": True
        }
