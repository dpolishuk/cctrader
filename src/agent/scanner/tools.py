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

    # Validate symbol is not empty (accept both BTCUSDT and BTC/USDT formats)
    if not symbol or len(symbol.strip()) == 0:
        logger.error(f"Invalid symbol: empty or whitespace")
        return {
            'status': 'error',
            'error': 'Symbol cannot be empty'
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
    result = await fetch_market_data.handler({
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
    result = await get_current_price.handler({"symbol": symbol})
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


async def generate_sentiment_query_internal(symbol: str, context: str = "") -> str:
    """Internal function to generate sentiment query."""
    from agent.tools.sentiment import analyze_market_sentiment
    result = await analyze_market_sentiment.handler({
        "symbol": symbol,
        "context": context
    })
    # Extract query from root field instead of parsing JSON
    return result.get("search_query", f"{symbol} cryptocurrency news")


async def execute_web_search_internal(query: str) -> List[Dict[str, str]]:
    """Internal function to execute web search via MCP."""
    # This will be called via the MCP server, but for now we'll simulate
    # In actual implementation, this calls the web-search MCP tool
    # For testing, we return empty list as fallback
    return []


def analyze_sentiment_from_results(web_results: List[Dict[str, str]]) -> tuple[str, int]:
    """
    Analyze web results to generate summary and suggest sentiment score.

    Returns:
        (summary, suggested_score) where score is 0-30
    """
    if not web_results:
        return "No web results available for sentiment analysis", 15

    # Simple heuristic: count positive/negative keywords
    positive_keywords = ["approval", "approved", "bullish", "surge", "rally", "institutional",
                        "adoption", "demand", "breakthrough", "upgrade"]
    negative_keywords = ["crash", "bearish", "decline", "concern", "risk", "regulation",
                        "ban", "hack", "fraud", "lawsuit"]

    positive_count = 0
    negative_count = 0

    for result in web_results:
        text = f"{result.get('title', '')} {result.get('snippet', '')}".lower()
        positive_count += sum(1 for kw in positive_keywords if kw in text)
        negative_count += sum(1 for kw in negative_keywords if kw in text)

    # Generate summary
    if positive_count > negative_count * 1.5:
        summary = f"Positive sentiment detected. Catalysts found: {positive_count} positive signals vs {negative_count} negative."
        score = min(30, 15 + positive_count * 2)
    elif negative_count > positive_count * 1.5:
        summary = f"Negative sentiment detected. Risks found: {negative_count} negative signals vs {positive_count} positive."
        score = max(0, 15 - negative_count * 2)
    else:
        summary = f"Neutral sentiment. Mixed signals: {positive_count} positive, {negative_count} negative."
        score = 15

    return summary, score


@tool(
    name="fetch_sentiment_data",
    description="""
    Fetch complete sentiment analysis data in one call.

    Automatically generates a sentiment query and executes web search.
    Returns sentiment summary and web search results combined.

    This tool handles the entire sentiment gathering workflow in one operation.

    Args:
        symbol: Trading pair (e.g., "BTCUSDT")
        context: Optional context about the move (e.g., "5% up in last hour")

    Returns:
        JSON with sentiment_query, web_results, sentiment_summary, suggested_sentiment_score, warnings, success
    """,
    input_schema={
        "symbol": str,
        "context": str
    }
)
async def fetch_sentiment_data(args: Dict[str, Any]) -> Dict[str, Any]:
    """Fetch sentiment query + web results in one bundled call."""
    symbol = args.get("symbol", "")
    context = args.get("context", "")
    warnings: List[str] = []

    # Step 1: Generate sentiment query
    try:
        sentiment_query = await generate_sentiment_query_internal(symbol, context)
    except Exception as e:
        warnings.append(f"Sentiment query generation failed: {e}")
        sentiment_query = f"{symbol} cryptocurrency news"

    # Step 2: Execute web search
    try:
        web_results = await execute_web_search_internal(sentiment_query)
    except Exception as e:
        warnings.append(f"Web search failed: {e}")
        web_results = []

    # Step 3: Analyze results and generate summary
    sentiment_summary, suggested_score = analyze_sentiment_from_results(web_results)

    # Build response
    response_data = {
        "sentiment_query": sentiment_query,
        "web_results": web_results,
        "sentiment_summary": sentiment_summary,
        "suggested_sentiment_score": suggested_score,
        "warnings": warnings,
        "success": len(warnings) == 0
    }

    return {
        "content": [{
            "type": "text",
            "text": json.dumps(response_data)
        }]
    }
