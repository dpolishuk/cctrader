"""Scanner-specific tools for Claude Agent integration."""
import anthropic
import aiohttp
import asyncio
import json
import logging
from typing import Dict, Any, Optional, List
from claude_agent_sdk import tool

from .config import ScannerConfig

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


# Module-level storage for scanner config
_scanner_config: Optional[ScannerConfig] = None


def set_scanner_config(config: ScannerConfig):
    """Set scanner config for web search URL."""
    global _scanner_config
    _scanner_config = config


def get_web_search_url() -> str:
    """Get web search MCP URL from config or default."""
    if _scanner_config:
        return _scanner_config.web_search_mcp_url
    return "http://localhost:3000/mcp"


def get_web_search_timeout() -> int:
    """Get web search timeout from config or default."""
    if _scanner_config:
        return _scanner_config.web_search_timeout_seconds
    return 30


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
    from src.agent.tools.market_data import fetch_market_data
    result = await fetch_market_data.handler({
        "symbol": symbol,
        "timeframe": timeframe,
        "limit": limit
    })
    # Extract data from the 'data' field (not from content text)
    if "data" in result and result["data"]:
        return result["data"]
    return []


async def get_current_price_internal(symbol: str) -> float:
    """Internal function to get current price."""
    from src.agent.tools.market_data import get_current_price
    result = await get_current_price.handler({"symbol": symbol})
    # Extract price from top-level field (not from content text)
    if "price" in result:
        return result["price"]
    return 0.0


@tool(
    name="fetch_technical_snapshot",
    description="""
    Fetch complete technical analysis snapshot in one call.

    Returns ANALYZED technical data for multiple timeframes (15m, 1h, 4h).
    Includes trend, momentum, volatility, and pattern analysis for each timeframe.
    This is the PRIMARY tool for gathering technical data - fully analyzed and ready to use.

    Returns data even if some timeframes fail (graceful degradation).

    Args:
        symbol: Trading pair (e.g., "BTCUSDT")

    Returns:
        JSON with analyzed data per timeframe, current price, warnings, and summary.
        Each timeframe includes: trend_score, momentum_score, volatility_score, key signals.
    """,
    input_schema={
        "symbol": str
    }
)
async def fetch_technical_snapshot(args: Dict[str, Any]) -> Dict[str, Any]:
    """Fetch and analyze all technical data in one bundled call."""
    from src.agent.tools.technical_analysis import (
        analyze_trend, analyze_momentum, analyze_volatility, analyze_patterns
    )

    symbol = args.get("symbol", "")
    warnings: List[str] = []
    success_count = 0

    # Fetch all data in parallel using asyncio.gather
    # Fetch 200+ periods for 1h to support all indicators (EMA 200 needs 200 periods)
    results = await asyncio.gather(
        fetch_market_data_internal(symbol, "15m", limit=200),
        fetch_market_data_internal(symbol, "1h", limit=200),
        fetch_market_data_internal(symbol, "4h", limit=200),
        get_current_price_internal(symbol),
        return_exceptions=True
    )

    # Process results with error handling
    ohlcv_data = {}
    current_price = 0.0

    # 15m data
    if isinstance(results[0], Exception):
        warnings.append(f"15m data fetch failed: {results[0]}")
        ohlcv_data["15m"] = None
    else:
        ohlcv_data["15m"] = results[0]
        success_count += 1

    # 1h data
    if isinstance(results[1], Exception):
        warnings.append(f"1h data fetch failed: {results[1]}")
        ohlcv_data["1h"] = None
    else:
        ohlcv_data["1h"] = results[1]
        success_count += 1

    # 4h data
    if isinstance(results[2], Exception):
        warnings.append(f"4h data fetch failed: {results[2]}")
        ohlcv_data["4h"] = None
    else:
        ohlcv_data["4h"] = results[2]
        success_count += 1

    # Current price
    if isinstance(results[3], Exception):
        warnings.append(f"Current price fetch failed: {results[3]}")
        current_price = 0.0
    else:
        current_price = results[3]
        success_count += 1

    # Now analyze each timeframe that has data
    analyzed_timeframes = {}

    for timeframe, ohlcv in ohlcv_data.items():
        if ohlcv is None or not ohlcv:
            analyzed_timeframes[timeframe] = {
                "status": "failed",
                "error": "No OHLCV data available"
            }
            continue

        # Run all analyses in parallel for this timeframe
        analyses = await asyncio.gather(
            analyze_trend.handler({"ohlcv_data": ohlcv, "symbol": symbol, "timeframe": timeframe}),
            analyze_momentum.handler({"ohlcv_data": ohlcv, "symbol": symbol, "timeframe": timeframe}),
            analyze_volatility.handler({"ohlcv_data": ohlcv, "symbol": symbol, "timeframe": timeframe}),
            analyze_patterns.handler({"ohlcv_data": ohlcv, "symbol": symbol, "timeframe": timeframe}),
            return_exceptions=True
        )

        # Extract results
        trend_result = analyses[0] if not isinstance(analyses[0], Exception) else None
        momentum_result = analyses[1] if not isinstance(analyses[1], Exception) else None
        volatility_result = analyses[2] if not isinstance(analyses[2], Exception) else None
        pattern_result = analyses[3] if not isinstance(analyses[3], Exception) else None

        # Build analyzed data for this timeframe
        timeframe_analysis = {
            "status": "success",
            "trend": {
                "score": trend_result.get("trend_score", 0.5) if trend_result else None,
                "signals": trend_result.get("signals", []) if trend_result else [],
                "interpretation": trend_result.get("interpretation", "N/A") if trend_result else "Analysis failed"
            },
            "momentum": {
                "score": momentum_result.get("momentum_score", 0.0) if momentum_result else None,
                "signals": momentum_result.get("signals", []) if momentum_result else [],
                "interpretation": momentum_result.get("interpretation", "N/A") if momentum_result else "Analysis failed"
            },
            "volatility": {
                "score": volatility_result.get("volatility_score", 0.5) if volatility_result else None,
                "atr_percent": volatility_result.get("indicators", {}).get("atr_percent", 0.0) if volatility_result else None,
                "signals": volatility_result.get("signals", []) if volatility_result else []
            },
            "patterns": {
                "current_level": pattern_result.get("current_level", "50.0") if pattern_result else None,
                "support_levels": pattern_result.get("support_levels", []) if pattern_result else [],
                "resistance_levels": pattern_result.get("resistance_levels", []) if pattern_result else [],
                "signals": pattern_result.get("signals", []) if pattern_result else []
            }
        }

        # Track any analysis failures
        if isinstance(analyses[0], Exception):
            warnings.append(f"{timeframe} trend analysis failed: {analyses[0]}")
        if isinstance(analyses[1], Exception):
            warnings.append(f"{timeframe} momentum analysis failed: {analyses[1]}")
        if isinstance(analyses[2], Exception):
            warnings.append(f"{timeframe} volatility analysis failed: {analyses[2]}")
        if isinstance(analyses[3], Exception):
            warnings.append(f"{timeframe} pattern analysis failed: {analyses[3]}")

        analyzed_timeframes[timeframe] = timeframe_analysis

    # Build comprehensive response
    response_data = {
        "symbol": symbol,
        "current_price": current_price,
        "timeframes": analyzed_timeframes,
        "warnings": warnings,
        "data_fetch_success": success_count,
        "summary": {
            "overall_trend": _calculate_overall_trend(analyzed_timeframes),
            "overall_momentum": _calculate_overall_momentum(analyzed_timeframes),
            "volatility_level": _get_volatility_level(analyzed_timeframes)
        }
    }

    return {
        "content": [{
            "type": "text",
            "text": json.dumps(response_data, indent=2)
        }]
    }


def _calculate_overall_trend(timeframes: Dict[str, Any]) -> str:
    """Calculate overall trend from multiple timeframes."""
    scores = []
    for tf_data in timeframes.values():
        if tf_data.get("status") == "success" and tf_data.get("trend", {}).get("score") is not None:
            scores.append(tf_data["trend"]["score"])

    if not scores:
        return "unknown"

    avg_score = sum(scores) / len(scores)
    if avg_score > 0.7:
        return "strong_uptrend"
    elif avg_score > 0.55:
        return "uptrend"
    elif avg_score >= 0.45:
        return "neutral"
    elif avg_score >= 0.3:
        return "downtrend"
    else:
        return "strong_downtrend"


def _calculate_overall_momentum(timeframes: Dict[str, Any]) -> str:
    """Calculate overall momentum from multiple timeframes."""
    scores = []
    for tf_data in timeframes.values():
        if tf_data.get("status") == "success" and tf_data.get("momentum", {}).get("score") is not None:
            scores.append(tf_data["momentum"]["score"])

    if not scores:
        return "unknown"

    avg_score = sum(scores) / len(scores)
    if avg_score > 0.5:
        return "strong_bullish"
    elif avg_score > 0.2:
        return "bullish"
    elif avg_score >= -0.2:
        return "neutral"
    elif avg_score >= -0.5:
        return "bearish"
    else:
        return "strong_bearish"


def _get_volatility_level(timeframes: Dict[str, Any]) -> str:
    """Get average volatility level from multiple timeframes."""
    scores = []
    for tf_data in timeframes.values():
        if tf_data.get("status") == "success" and tf_data.get("volatility", {}).get("score") is not None:
            scores.append(tf_data["volatility"]["score"])

    if not scores:
        return "unknown"

    avg_score = sum(scores) / len(scores)
    if avg_score > 0.7:
        return "high"
    elif avg_score > 0.4:
        return "normal"
    else:
        return "low"


async def generate_sentiment_query_internal(symbol: str, context: str = "") -> str:
    """Internal function to generate sentiment query."""
    from src.agent.tools.sentiment import analyze_market_sentiment
    result = await analyze_market_sentiment.handler({
        "symbol": symbol,
        "context": context
    })
    # Extract query from root field instead of parsing JSON
    return result.get("search_query", f"{symbol} cryptocurrency news")


async def execute_web_search_internal(query: str) -> List[Dict[str, str]]:
    """Internal function to execute web search via MCP.

    Calls the web-search MCP HTTP endpoint using aiohttp.

    Args:
        query: Search query string

    Returns:
        List of search results with keys: title, snippet, url

    Raises:
        RuntimeError: On connection error, timeout, or empty results
    """
    url = get_web_search_url()
    timeout_seconds = get_web_search_timeout()

    # Build MCP request payload
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "search",
            "arguments": {
                "query": query,
                "engines": ["duckduckgo", "bing"],
                "limit": 10
            }
        }
    }

    try:
        timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, json=payload) as response:
                if response.status != 200:
                    raise RuntimeError(f"Web search HTTP error: status={response.status}")

                data = await response.json()

                # Check for JSON-RPC error
                if "error" in data:
                    error_msg = data["error"].get("message", "Unknown error")
                    raise RuntimeError(f"Web search RPC error: {error_msg}")

                # Extract results from response
                if "result" not in data:
                    raise RuntimeError("Web search response missing 'result' field")

                result = data["result"]

                # Result contains content array with text field containing JSON
                if "content" not in result or not result["content"]:
                    raise RuntimeError("Web search response missing 'content' field")

                content_text = result["content"][0].get("text", "{}")
                results_data = json.loads(content_text)

                # Extract results array
                results = results_data.get("results", [])

                if not results:
                    raise RuntimeError("Web search returned empty results")

                # Normalize result format: title, snippet, url
                normalized_results = []
                for item in results:
                    normalized_results.append({
                        "title": item.get("title", ""),
                        "snippet": item.get("description", item.get("snippet", "")),
                        "url": item.get("url", "")
                    })

                return normalized_results

    except aiohttp.ClientError as e:
        raise RuntimeError(f"Web search connection error: {e}")
    except asyncio.TimeoutError:
        raise RuntimeError(f"Web search timeout after {timeout_seconds}s")
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Web search JSON parse error: {e}")
    except Exception as e:
        raise RuntimeError(f"Web search failed: {e}")


async def analyze_sentiment_with_llm(
    symbol: str,
    web_results: List[Dict[str, str]],
    context: str = ""
) -> Dict[str, Any]:
    """
    Analyze sentiment from web results using Claude.

    Args:
        symbol: Trading symbol (e.g., "BTCUSDT")
        web_results: List of web search results with title, snippet, url
        context: Optional context about the price move

    Returns:
        Dict with sentiment_summary (str), sentiment_score (0-30), key_findings (list)

    Raises:
        RuntimeError: If Claude API call fails or response cannot be parsed
    """
    # Format web results for Claude
    results_text = "\n\n".join([
        f"Title: {r.get('title', 'N/A')}\nSnippet: {r.get('snippet', 'N/A')}\nURL: {r.get('url', 'N/A')}"
        for r in web_results[:10]  # Limit to top 10 results
    ])

    # Build analysis prompt
    prompt = f"""Analyze the sentiment for {symbol} based on these recent web search results:

{results_text}

{f'Context: {context}' if context else ''}

Provide a JSON response with:
1. sentiment_summary: A 2-3 sentence summary of the overall sentiment
2. sentiment_score: A score from 0-30 where:
   - 0 = Extremely bearish (major negative catalysts, fear)
   - 15 = Neutral (mixed signals or no strong catalysts)
   - 30 = Extremely bullish (major positive catalysts, euphoria)
3. key_findings: A list of exactly 3 key findings that justify the score

Return ONLY valid JSON, no other text."""

    try:
        # Get API key from environment
        import os
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY not found in environment. "
                "Please set it in your .env file or export it: "
                "export ANTHROPIC_API_KEY='your-key-here'"
            )

        # Make async Claude API call
        client = anthropic.AsyncAnthropic(api_key=api_key)

        response = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )

        # Extract text from response
        if not response.content or len(response.content) == 0:
            raise RuntimeError("Empty response from Claude API")

        response_text = response.content[0].text

        # Parse JSON response
        try:
            result = json.loads(response_text)
        except json.JSONDecodeError:
            # Try to extract JSON if wrapped in markdown code blocks
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                result = json.loads(response_text[json_start:json_end].strip())
            elif "```" in response_text:
                json_start = response_text.find("```") + 3
                json_end = response_text.find("```", json_start)
                result = json.loads(response_text[json_start:json_end].strip())
            else:
                raise

        # Validate required fields
        if "sentiment_summary" not in result:
            raise RuntimeError("Response missing 'sentiment_summary' field")
        if "sentiment_score" not in result:
            raise RuntimeError("Response missing 'sentiment_score' field")
        if "key_findings" not in result:
            raise RuntimeError("Response missing 'key_findings' field")

        # Clamp score to 0-30 range
        score = result["sentiment_score"]
        if not isinstance(score, (int, float)):
            raise RuntimeError(f"sentiment_score must be numeric, got {type(score)}")

        score = max(0, min(30, int(score)))
        result["sentiment_score"] = score

        # Ensure key_findings is a list
        if not isinstance(result["key_findings"], list):
            raise RuntimeError("key_findings must be a list")

        return result

    except anthropic.APIError as e:
        raise RuntimeError(f"Claude API error: {e}")
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse Claude response as JSON: {e}")
    except Exception as e:
        raise RuntimeError(f"Sentiment analysis failed: {e}")


@tool(
    name="fetch_sentiment_data",
    description="""
    Fetch and analyze market sentiment for a trading symbol.

    Executes web search for recent news and uses LLM to analyze sentiment.
    Returns sentiment score (0-30) and summary.

    IMPORTANT: This tool will FAIL if web search is unavailable.
    The scanner will skip analysis for this symbol if sentiment cannot be determined.

    Args:
        symbol: Trading pair (e.g., "BTCUSDT")
        context: Optional context about the move (e.g., "5% up in last hour")

    Returns:
        JSON with web_results, sentiment_summary, sentiment_score (0-30), key_findings
    """,
    input_schema={
        "symbol": str,
        "context": str
    }
)
async def fetch_sentiment_data(args: Dict[str, Any]) -> Dict[str, Any]:
    """Fetch and analyze sentiment data using web search + LLM."""
    symbol = args.get("symbol", "")
    context = args.get("context", "")

    # Step 1: Generate search query
    try:
        sentiment_query = await generate_sentiment_query_internal(symbol, context)
        logger.info(f"Generated sentiment query: {sentiment_query}")
    except Exception as e:
        logger.error(f"Failed to generate sentiment query: {e}")
        raise RuntimeError(f"Sentiment query generation failed: {e}")

    # Step 2: Execute web search (WILL RAISE if fails)
    try:
        web_results = await execute_web_search_internal(sentiment_query)
        logger.info(f"Web search returned {len(web_results)} results")
    except RuntimeError as e:
        logger.error(f"Web search failed: {e}")
        raise RuntimeError(f"Web search failed for {symbol}: {e}")

    # Step 3: Analyze sentiment with LLM (WILL RAISE if fails)
    try:
        sentiment_analysis = await analyze_sentiment_with_llm(symbol, web_results, context)
        logger.info(f"Sentiment analysis complete: score={sentiment_analysis['sentiment_score']}")
    except RuntimeError as e:
        logger.error(f"Sentiment analysis failed: {e}")
        raise RuntimeError(f"Sentiment analysis failed for {symbol}: {e}")

    # Build successful response
    response_data = {
        "sentiment_query": sentiment_query,
        "web_results": web_results,
        "sentiment_summary": sentiment_analysis["sentiment_summary"],
        "sentiment_score": sentiment_analysis["sentiment_score"],
        "key_findings": sentiment_analysis.get("key_findings", []),
        "success": True
    }

    return {
        "content": [{
            "type": "text",
            "text": json.dumps(response_data)
        }]
    }
