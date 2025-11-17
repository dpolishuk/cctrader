"""Technical analysis tools using pandas-ta."""
import pandas as pd
import pandas_ta as ta
from typing import Any, Dict
from claude_agent_sdk import tool

@tool(
    name="analyze_technicals",
    description="Perform technical analysis on OHLCV data with RSI, MACD, Bollinger Bands",
    input_schema={
        "ohlcv_data": list,
        "symbol": str,
        "timeframe": str
    }
)
async def analyze_technicals(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate technical indicators: RSI, MACD, Bollinger Bands, Volume analysis.

    Returns analysis results with indicator values and interpretation.
    """
    try:
        ohlcv_data = args.get("ohlcv_data", [])
        symbol = args.get("symbol", "Unknown")
        timeframe = args.get("timeframe", "Unknown")

        if not ohlcv_data:
            return {
                "content": [{"type": "text", "text": "No OHLCV data provided"}],
                "is_error": True
            }

        # Convert to DataFrame
        df = pd.DataFrame(ohlcv_data)

        # Calculate indicators
        # RSI (14-period)
        df['rsi'] = ta.rsi(df['close'], length=14)

        # MACD
        macd = ta.macd(df['close'])
        df['macd'] = macd['MACD_12_26_9']
        df['macd_signal'] = macd['MACDs_12_26_9']
        df['macd_hist'] = macd['MACDh_12_26_9']

        # Bollinger Bands
        bbands = ta.bbands(df['close'], length=20, std=2)
        df['bb_upper'] = bbands['BBU_20_2.0']
        df['bb_middle'] = bbands['BBM_20_2.0']
        df['bb_lower'] = bbands['BBL_20_2.0']

        # Volume SMA
        df['volume_sma'] = ta.sma(df['volume'], length=20)

        # Get latest values
        latest = df.iloc[-1]

        # Interpretation
        rsi_status = "Oversold" if latest['rsi'] < 30 else "Overbought" if latest['rsi'] > 70 else "Neutral"
        macd_status = "Bullish" if latest['macd'] > latest['macd_signal'] else "Bearish"
        bb_status = "Near Upper Band" if latest['close'] > latest['bb_middle'] else "Near Lower Band"

        indicators = {
            "rsi": float(latest['rsi']),
            "macd": float(latest['macd']),
            "macd_signal": float(latest['macd_signal']),
            "macd_hist": float(latest['macd_hist']),
            "bb_upper": float(latest['bb_upper']),
            "bb_middle": float(latest['bb_middle']),
            "bb_lower": float(latest['bb_lower']),
            "price": float(latest['close']),
            "volume": float(latest['volume']),
            "volume_sma": float(latest['volume_sma'])
        }

        analysis_text = f"""Technical Analysis for {symbol} ({timeframe}):

RSI (14): {latest['rsi']:.2f} - {rsi_status}
MACD: {latest['macd']:.4f} (Signal: {latest['macd_signal']:.4f}) - {macd_status}
Bollinger Bands: {bb_status}
  Upper: {latest['bb_upper']:.2f}
  Middle: {latest['bb_middle']:.2f}
  Lower: {latest['bb_lower']:.2f}
Current Price: {latest['close']:.2f}
Volume: {latest['volume']:.2f} (SMA: {latest['volume_sma']:.2f})
"""

        return {
            "content": [{"type": "text", "text": analysis_text}],
            "indicators": indicators,
            "interpretation": {
                "rsi_status": rsi_status,
                "macd_status": macd_status,
                "bb_status": bb_status
            }
        }

    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Error in technical analysis: {str(e)}"}],
            "is_error": True
        }

@tool(
    name="multi_timeframe_analysis",
    description="Analyze multiple timeframes simultaneously for comprehensive view",
    input_schema={
        "symbol": str,
        "timeframes": list
    }
)
async def multi_timeframe_analysis(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Coordinate analysis across multiple timeframes.
    This tool orchestrates calls to fetch_market_data and analyze_technicals.
    """
    return {
        "content": [{
            "type": "text",
            "text": "Use fetch_market_data and analyze_technicals for each timeframe: " +
                    ", ".join(args.get("timeframes", []))
        }]
    }
