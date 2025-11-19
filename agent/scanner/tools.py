"""Scanner-specific tools for Claude Agent integration."""
import asyncio
import json
import logging
from typing import Dict, Any, Optional, List
from claude_agent_sdk import tool

logger = logging.getLogger(__name__)

# Module-level storage for signal queue (simpler than contextvars for MCP)
_signal_queue: Optional[asyncio.Queue] = None


def set_signal_queue(queue: asyncio.Queue):
    """Set the signal queue for the current analysis session."""
    global _signal_queue
    _signal_queue = queue


def clear_signal_queue():
    """Clear the signal queue after analysis completes."""
    global _signal_queue
    _signal_queue = None


@tool(
    name="submit_trading_signal",
    description="Submit analyzed trading signal with confidence breakdown. Call this as FINAL step with all analysis results.",
    input_schema={
        "confidence": int,
        "entry_price": float,
        "stop_loss": float,
        "tp1": float,
        "technical_score": float,
        "sentiment_score": float,
        "liquidity_score": float,
        "correlation_score": float,
        "symbol": str,
        "analysis": str
    }
)
async def submit_trading_signal(args: Dict[str, Any]) -> Dict[str, Any]:
    """Submit analyzed trading signal with confidence breakdown."""
    # Extract parameters from args dict
    confidence = args.get("confidence", 0)
    entry_price = args.get("entry_price", 0.0)
    stop_loss = args.get("stop_loss", 0.0)
    tp1 = args.get("tp1", 0.0)
    technical_score = args.get("technical_score", 0.0)
    sentiment_score = args.get("sentiment_score", 0.0)
    liquidity_score = args.get("liquidity_score", 0.0)
    correlation_score = args.get("correlation_score", 0.0)
    symbol = args.get("symbol", "UNKNOWN")
    analysis = args.get("analysis", "")

    # DEBUG: Print to confirm function is called
    print(f"[DEBUG] submit_trading_signal called for {symbol} with confidence={confidence}")
    logger.info(f"[TOOL START] submit_trading_signal called for {symbol}")

    # Validate confidence is in valid range
    if not (0 <= confidence <= 100):
        logger.error(f"Invalid confidence score: {confidence} (must be 0-100)")
        return {
            'status': 'error',
            'error': f'Confidence must be 0-100, got {confidence}'
        }

    # Validate component scores
    if not (0 <= technical_score <= 40):
        logger.error(f"Invalid technical_score: {technical_score} (must be 0-40)")
        return {
            'status': 'error',
            'error': f'technical_score must be 0-40, got {technical_score}'
        }

    if not (0 <= sentiment_score <= 30):
        logger.error(f"Invalid sentiment_score: {sentiment_score} (must be 0-30)")
        return {
            'status': 'error',
            'error': f'sentiment_score must be 0-30, got {sentiment_score}'
        }

    if not (0 <= liquidity_score <= 20):
        logger.error(f"Invalid liquidity_score: {liquidity_score} (must be 0-20)")
        return {
            'status': 'error',
            'error': f'liquidity_score must be 0-20, got {liquidity_score}'
        }

    if not (0 <= correlation_score <= 10):
        logger.error(f"Invalid correlation_score: {correlation_score} (must be 0-10)")
        return {
            'status': 'error',
            'error': f'correlation_score must be 0-10, got {correlation_score}'
        }

    # Validate prices are positive
    if entry_price <= 0:
        logger.error(f"Invalid entry_price: {entry_price} (must be positive)")
        return {
            'status': 'error',
            'error': f'entry_price must be positive, got {entry_price}'
        }

    if stop_loss <= 0:
        logger.error(f"Invalid stop_loss: {stop_loss} (must be positive)")
        return {
            'status': 'error',
            'error': f'stop_loss must be positive, got {stop_loss}'
        }

    if tp1 <= 0:
        logger.error(f"Invalid tp1: {tp1} (must be positive)")
        return {
            'status': 'error',
            'error': f'tp1 must be positive, got {tp1}'
        }

    # Validate symbol format (basic check)
    if '/' not in symbol:
        logger.error(f"Invalid symbol format: {symbol} (expected format: BASE/QUOTE)")
        return {
            'status': 'error',
            'error': f'Invalid symbol format: {symbol}'
        }

    # Validate analysis is not empty
    if not analysis or len(analysis.strip()) == 0:
        logger.error("Analysis text is empty")
        return {
            'status': 'error',
            'error': 'Analysis text cannot be empty'
        }

    # Build validated signal
    signal = {
        'confidence': confidence,
        'entry_price': entry_price,
        'stop_loss': stop_loss,
        'tp1': tp1,
        'technical_score': technical_score,
        'sentiment_score': sentiment_score,
        'liquidity_score': liquidity_score,
        'correlation_score': correlation_score,
        'symbol': symbol,
        'analysis': analysis
    }

    # Get the signal queue from module-level storage
    global _signal_queue

    if _signal_queue is None:
        logger.error("Signal queue not set - tool called outside wrapper context?")
        return {
            'status': 'error',
            'error': 'Internal error: signal queue not available'
        }

    try:
        logger.info(f"Got signal queue: {_signal_queue}")
        logger.info(f"Submitting signal for {symbol}: confidence={confidence}")
        await _signal_queue.put(signal)
        logger.info(f"Signal successfully queued for {symbol}")

        return {
            'status': 'success',
            'message': f'Signal submitted for {symbol} with confidence {confidence}'
        }

    except Exception as e:
        # Catch any errors during queue operation
        logger.error(f"Error submitting signal: {e}", exc_info=True)
        return {
            'status': 'error',
            'error': f'Internal error: {str(e)}'
        }


async def fetch_market_data_internal(symbol: str, timeframe: str, limit: int = 50) -> Dict[str, Any]:
    """Internal function to fetch market data."""
    from agent.tools.market_data import fetch_market_data
    result = await fetch_market_data({
        "symbol": symbol,
        "timeframe": timeframe,
        "limit": limit
    })
    # Extract data from MCP response format
    if "content" in result and len(result["content"]) > 0:
        return json.loads(result["content"][0]["text"])
    return {}


async def get_current_price_internal(symbol: str) -> float:
    """Internal function to get current price."""
    from agent.tools.market_data import get_current_price
    result = await get_current_price({"symbol": symbol})
    # Extract price from MCP response format
    if "content" in result and len(result["content"]) > 0:
        data = json.loads(result["content"][0]["text"])
        return data.get("price", 0.0)
    return 0.0


@tool(
    name="fetch_technical_snapshot",
    description="""
    Fetch complete technical analysis data in one call.

    Returns ALL timeframe data (15m, 1h, 4h) plus current price.
    This is the PRIMARY tool for gathering technical data - more efficient than individual fetches.

    Returns data even if some timeframes fail (graceful degradation).

    Args:
        symbol: Trading pair (e.g., "BTCUSDT")

    Returns:
        JSON with timeframes dict, current_price, warnings array, success_count
    """,
    input_schema={
        "symbol": str
    }
)
async def fetch_technical_snapshot(args: Dict[str, Any]) -> Dict[str, Any]:
    """Fetch all technical data in one bundled call."""
    symbol = args.get("symbol", "")
    warnings: List[str] = []
    success_count = 0

    # Fetch all data in parallel using asyncio.gather
    results = await asyncio.gather(
        fetch_market_data_internal(symbol, "15m", limit=50),
        fetch_market_data_internal(symbol, "1h", limit=50),
        fetch_market_data_internal(symbol, "4h", limit=50),
        get_current_price_internal(symbol),
        return_exceptions=True
    )

    # Process results with error handling
    timeframes = {}
    current_price = 0.0

    # 15m data
    if isinstance(results[0], Exception):
        warnings.append(f"15m data fetch failed: {results[0]}")
        timeframes["15m"] = None
    else:
        timeframes["15m"] = results[0]
        success_count += 1

    # 1h data
    if isinstance(results[1], Exception):
        warnings.append(f"1h data fetch failed: {results[1]}")
        timeframes["1h"] = None
    else:
        timeframes["1h"] = results[1]
        success_count += 1

    # 4h data
    if isinstance(results[2], Exception):
        warnings.append(f"4h data fetch failed: {results[2]}")
        timeframes["4h"] = None
    else:
        timeframes["4h"] = results[2]
        success_count += 1

    # Current price
    if isinstance(results[3], Exception):
        warnings.append(f"Current price fetch failed: {results[3]}")
        current_price = 0.0
    else:
        current_price = results[3]
        success_count += 1

    # Build response
    response_data = {
        "timeframes": timeframes,
        "current_price": current_price,
        "warnings": warnings,
        "success_count": success_count
    }

    return {
        "content": [{
            "type": "text",
            "text": json.dumps(response_data)
        }]
    }
