"""Market data tools using CCXT for Bybit."""
import ccxt.async_support as ccxt
import pandas as pd
from typing import Any, Dict, List
from claude_agent_sdk import tool
import os

# Initialize Bybit exchange
_exchange = None

def get_exchange():
    """Get or create Bybit exchange instance."""
    global _exchange
    if _exchange is None:
        _exchange = ccxt.bybit({
            'apiKey': os.getenv('BYBIT_API_KEY'),
            'secret': os.getenv('BYBIT_API_SECRET'),
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future',
            }
        })
        if os.getenv('BYBIT_TESTNET', 'false').lower() == 'true':
            _exchange.set_sandbox_mode(True)
    return _exchange

@tool(
    name="fetch_market_data",
    description="Fetch OHLCV candlestick data from Bybit for a symbol and timeframe",
    input_schema={
        "symbol": str,
        "timeframe": str,
        "limit": int
    }
)
async def fetch_market_data(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fetch OHLCV data from Bybit.

    Returns:
        Dictionary with OHLCV data as pandas DataFrame (serialized)
    """
    try:
        exchange = get_exchange()
        symbol = args.get("symbol", "BTC/USDT")
        timeframe = args.get("timeframe", "1h")
        limit = args.get("limit", 100)

        # Fetch OHLCV: [[timestamp, open, high, low, close, volume], ...]
        ohlcv = await exchange.fetch_ohlcv(symbol, timeframe, limit=limit)

        # Convert to DataFrame
        df = pd.DataFrame(
            ohlcv,
            columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
        )
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

        return {
            "content": [{
                "type": "text",
                "text": f"Fetched {len(df)} candles for {symbol} ({timeframe})\n"
                        f"Latest price: {df['close'].iloc[-1]:.2f}\n"
                        f"Data range: {df['timestamp'].iloc[0]} to {df['timestamp'].iloc[-1]}"
            }],
            "data": df.to_dict(orient='records')
        }
    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"Error fetching market data: {str(e)}"
            }],
            "is_error": True
        }

@tool(
    name="get_current_price",
    description="Get the current price for a trading symbol on Bybit",
    input_schema={"symbol": str}
)
async def get_current_price(args: Dict[str, Any]) -> Dict[str, Any]:
    """Fetch current ticker price."""
    try:
        exchange = get_exchange()
        symbol = args.get("symbol", "BTC/USDT")

        ticker = await exchange.fetch_ticker(symbol)

        return {
            "content": [{
                "type": "text",
                "text": f"{symbol} Current Price: ${ticker['last']:.2f}\n"
                        f"24h Change: {ticker['percentage']:.2f}%\n"
                        f"24h Volume: {ticker['quoteVolume']:.2f} USDT"
            }],
            "price": ticker['last'],
            "change_24h": ticker['percentage'],
            "volume_24h": ticker['quoteVolume']
        }
    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Error: {str(e)}"}],
            "is_error": True
        }
