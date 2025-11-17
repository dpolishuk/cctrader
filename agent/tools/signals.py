"""Trading signal generation combining technical and sentiment analysis."""
from typing import Any, Dict
from claude_agent_sdk import tool
import json

@tool(
    name="generate_trading_signal",
    description="Generate buy/sell/hold signal based on technical and sentiment analysis",
    input_schema={
        "symbol": str,
        "technical_data": dict,
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
        sentiment = args.get("sentiment_data", {})
        price = args.get("current_price")

        # Extract technical indicators
        indicators = technical.get("indicators", {})
        interpretation = technical.get("interpretation", {})

        rsi = indicators.get("rsi", 50)
        macd_hist = indicators.get("macd_hist", 0)
        rsi_status = interpretation.get("rsi_status", "Neutral")
        macd_status = interpretation.get("macd_status", "Neutral")

        # Technical score (-1 to 1)
        tech_score = 0.0

        # RSI contribution
        if rsi < 30:
            tech_score += 0.4  # Oversold = bullish
        elif rsi > 70:
            tech_score -= 0.4  # Overbought = bearish
        else:
            tech_score += (50 - rsi) / 100  # Neutral zone

        # MACD contribution
        if macd_hist > 0:
            tech_score += 0.3
        elif macd_hist < 0:
            tech_score -= 0.3

        # Bollinger Bands
        bb_status = interpretation.get("bb_status", "")
        if "Lower" in bb_status:
            tech_score += 0.3  # Near lower band = potential bounce
        elif "Upper" in bb_status:
            tech_score -= 0.3  # Near upper band = potential reversal

        # Sentiment score (extract from sentiment_data)
        sentiment_score = sentiment.get("sentiment_score", 0.0)  # Assuming -1 to 1

        # Combined score (60% technical, 40% sentiment)
        combined_score = (tech_score * 0.6) + (sentiment_score * 0.4)

        # Generate signal
        if combined_score > 0.5:
            signal = "STRONG_BUY"
            confidence = min(abs(combined_score), 1.0)
        elif combined_score > 0.2:
            signal = "BUY"
            confidence = abs(combined_score)
        elif combined_score < -0.5:
            signal = "STRONG_SELL"
            confidence = min(abs(combined_score), 1.0)
        elif combined_score < -0.2:
            signal = "SELL"
            confidence = abs(combined_score)
        else:
            signal = "HOLD"
            confidence = 1.0 - abs(combined_score)

        # Generate reason
        reasons = []
        if rsi_status != "Neutral":
            reasons.append(f"RSI: {rsi_status} ({rsi:.1f})")
        if macd_status != "Neutral":
            reasons.append(f"MACD: {macd_status}")
        if sentiment_score > 0.3:
            reasons.append("Positive market sentiment")
        elif sentiment_score < -0.3:
            reasons.append("Negative market sentiment")

        reason = " | ".join(reasons) if reasons else "Mixed signals"

        signal_text = f"""
🎯 TRADING SIGNAL for {symbol}

Signal: {signal}
Confidence: {confidence:.1%}
Current Price: ${price:.2f}

Technical Score: {tech_score:.2f}
Sentiment Score: {sentiment_score:.2f}
Combined Score: {combined_score:.2f}

Reasoning: {reason}
"""

        return {
            "content": [{"type": "text", "text": signal_text}],
            "signal": {
                "type": signal,
                "confidence": confidence,
                "price": price,
                "technical_score": tech_score,
                "sentiment_score": sentiment_score,
                "combined_score": combined_score,
                "reason": reason
            }
        }

    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Error generating signal: {str(e)}"}],
            "is_error": True
        }
