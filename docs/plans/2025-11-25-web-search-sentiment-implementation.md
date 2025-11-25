# Implementation Plan: Web Search MCP for Sentiment Analysis

**Date:** 2025-11-25
**Status:** Ready for implementation

## Summary

Fix the scanner's `fetch_sentiment_data()` bundled tool to:
1. Actually execute web search via MCP HTTP call
2. Use nested Claude API call for LLM-based sentiment analysis
3. Fail the analysis entirely if web search fails (no silent fallbacks)

## Current State

- `fetch_sentiment_data()` in `src/agent/scanner/tools.py:512-540` is stubbed
- `execute_web_search_internal()` at line 443-448 returns empty list
- Web-search MCP is configured at `localhost:3000/mcp` in `.mcp.json`
- Sentiment scores are calculated without actual web data

## Implementation Tasks

### Task 1: Add MCP HTTP client for web search

**File:** `src/agent/scanner/tools.py`

**Changes:**
1. Add `aiohttp` import at top of file
2. Add config import for web search URL
3. Implement `execute_web_search_internal()` to call MCP HTTP endpoint

**Code:**
```python
import aiohttp

# Add near top of file
WEB_SEARCH_MCP_URL = "http://localhost:3000/mcp"

async def execute_web_search_internal(query: str) -> List[Dict[str, str]]:
    """
    Execute web search via MCP HTTP endpoint.

    Raises:
        RuntimeError: If web search fails (connection error, timeout, invalid response)
    """
    try:
        async with aiohttp.ClientSession() as session:
            # MCP tool call format
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

            async with session.post(
                WEB_SEARCH_MCP_URL,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status != 200:
                    raise RuntimeError(f"Web search MCP returned status {response.status}")

                result = await response.json()

                # Check for MCP error
                if "error" in result:
                    raise RuntimeError(f"Web search MCP error: {result['error']}")

                # Extract results from MCP response
                content = result.get("result", {}).get("content", [])
                if not content:
                    raise RuntimeError("Web search returned empty content")

                # Parse the text content (MCP returns results as JSON text)
                import json
                text_content = content[0].get("text", "{}")
                search_data = json.loads(text_content)

                # Extract results array
                results = search_data.get("results", [])
                if not results:
                    raise RuntimeError("Web search returned no results")

                # Transform to standard format
                return [
                    {
                        "title": r.get("title", ""),
                        "snippet": r.get("description", r.get("snippet", "")),
                        "url": r.get("url", "")
                    }
                    for r in results
                ]

    except aiohttp.ClientError as e:
        raise RuntimeError(f"Web search connection failed: {e}")
    except asyncio.TimeoutError:
        raise RuntimeError("Web search timed out after 30 seconds")
```

**Verification:**
- Unit test with mocked aiohttp response
- Integration test with running web-search daemon

---

### Task 2: Add LLM-based sentiment analysis function

**File:** `src/agent/scanner/tools.py`

**Changes:**
Add `analyze_sentiment_with_llm()` function that makes a nested Claude API call.

**Code:**
```python
import anthropic

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
        RuntimeError: If Claude API call fails
    """
    # Format web results for prompt
    results_text = "\n".join([
        f"- {r.get('title', 'No title')}: {r.get('snippet', 'No snippet')}"
        for r in web_results[:10]  # Limit to top 10
    ])

    prompt = f"""Analyze the sentiment of these news results for {symbol} cryptocurrency.

Context: {context if context else 'No additional context'}

News Results:
{results_text}

Provide your analysis in the following JSON format exactly:
{{
    "sentiment_summary": "2-3 sentence summary of overall sentiment and key catalysts/risks",
    "sentiment_score": <number 0-30 where 0=extremely bearish, 15=neutral, 30=extremely bullish>,
    "key_findings": ["finding 1", "finding 2", "finding 3"]
}}

Scoring guide:
- 0-5: Extremely bearish (hacks, bans, major crashes)
- 6-10: Bearish (regulatory concerns, declining metrics)
- 11-14: Slightly bearish
- 15: Neutral (mixed or no significant news)
- 16-19: Slightly bullish
- 20-24: Bullish (positive adoption, upgrades)
- 25-30: Extremely bullish (major institutional adoption, ETF approvals)

Respond ONLY with the JSON, no other text."""

    try:
        client = anthropic.AsyncAnthropic()

        response = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )

        # Extract text content
        text = response.content[0].text.strip()

        # Parse JSON response
        # Handle potential markdown code blocks
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()

        result = json.loads(text)

        # Validate required fields
        if "sentiment_score" not in result:
            raise ValueError("Missing sentiment_score in response")

        # Clamp score to valid range
        score = max(0, min(30, int(result["sentiment_score"])))

        return {
            "sentiment_summary": result.get("sentiment_summary", "Analysis complete"),
            "sentiment_score": score,
            "key_findings": result.get("key_findings", [])
        }

    except anthropic.APIError as e:
        raise RuntimeError(f"Claude API error: {e}")
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse Claude response as JSON: {e}")
```

**Verification:**
- Unit test with mocked anthropic client
- Test JSON parsing edge cases

---

### Task 3: Update fetch_sentiment_data() to use new functions

**File:** `src/agent/scanner/tools.py`

**Changes:**
Replace the stubbed implementation with real web search + LLM analysis.

**Code:**
```python
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

    Raises:
        Error if web search fails or sentiment cannot be analyzed
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
        # Re-raise to fail the analysis
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
```

**Verification:**
- Integration test with mocked web search + mocked Claude
- Test error propagation for both failure modes

---

### Task 4: Add web search URL to scanner config

**File:** `src/agent/scanner/config.py`

**Changes:**
Add web search MCP URL configuration.

**Code:**
```python
@dataclass
class ScannerConfig:
    """Configuration for market movers scanner."""

    # ... existing fields ...

    # Web search configuration
    web_search_mcp_url: str = field(
        default_factory=lambda: os.getenv('WEB_SEARCH_MCP_URL', 'http://localhost:3000/mcp')
    )
    web_search_timeout_seconds: int = field(
        default_factory=lambda: int(os.getenv('WEB_SEARCH_TIMEOUT', '30'))
    )
```

**Verification:**
- Verify config loads correctly from environment

---

### Task 5: Update tools.py to use config

**File:** `src/agent/scanner/tools.py`

**Changes:**
Import config and use configurable URL instead of hardcoded value.

**Code:**
```python
from .config import ScannerConfig

# At module level
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
```

Then update `execute_web_search_internal()` to use `get_web_search_url()`.

**Verification:**
- Test config override works

---

### Task 6: Remove old keyword-based analysis

**File:** `src/agent/scanner/tools.py`

**Changes:**
Remove or deprecate `analyze_sentiment_from_results()` function (lines 451-486) since we're now using LLM-based analysis.

Option: Keep it as fallback but mark deprecated, or remove entirely.

**Recommendation:** Remove entirely since we're failing on errors, not falling back.

---

### Task 7: Add aiohttp to dependencies

**File:** `requirements.txt` or `pyproject.toml`

**Changes:**
Add `aiohttp>=3.9.0` if not already present.

**Verification:**
- `pip install -e .` succeeds

---

### Task 8: Write tests

**File:** `tests/test_sentiment_web_search.py`

**Tests to write:**
1. `test_execute_web_search_success` - Mock aiohttp, verify result parsing
2. `test_execute_web_search_connection_error` - Verify RuntimeError raised
3. `test_execute_web_search_timeout` - Verify RuntimeError raised
4. `test_execute_web_search_empty_results` - Verify RuntimeError raised
5. `test_analyze_sentiment_with_llm_success` - Mock anthropic, verify score
6. `test_analyze_sentiment_with_llm_invalid_json` - Verify RuntimeError raised
7. `test_fetch_sentiment_data_success` - Full integration with mocks
8. `test_fetch_sentiment_data_web_search_fails` - Verify error propagates
9. `test_fetch_sentiment_data_llm_fails` - Verify error propagates

---

## Execution Order

1. Task 7: Add aiohttp dependency
2. Task 4: Add config
3. Task 5: Add config usage to tools
4. Task 1: Implement web search HTTP client
5. Task 2: Implement LLM sentiment analysis
6. Task 3: Update fetch_sentiment_data
7. Task 6: Remove old keyword analysis
8. Task 8: Write tests

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Web search daemon not running | Clear error message: "Web search MCP not available at {url}" |
| Claude API rate limits | Use claude-sonnet-4-20250514 for cost efficiency |
| Slow web search | 30 second timeout with clear error |
| Invalid JSON from Claude | Retry once with stricter prompt, then fail |

## Rollback Plan

If issues arise:
1. Revert `fetch_sentiment_data()` to return stubbed response
2. Keep new functions but don't call them
3. Investigate and fix before re-enabling
