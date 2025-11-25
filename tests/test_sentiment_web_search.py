"""Tests for sentiment web search functionality."""
import sys
import pytest
import json
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, Mock

# Mock anthropic module before importing tools
sys.modules['anthropic'] = MagicMock()

from src.agent.scanner.tools import (
    execute_web_search_internal,
    analyze_sentiment_with_llm,
    fetch_sentiment_data,
    set_scanner_config,
    get_web_search_url,
    get_web_search_timeout
)
from src.agent.scanner.config import ScannerConfig


@pytest.mark.asyncio
async def test_execute_web_search_success():
    """Test successful web search execution with valid results."""
    query = "Bitcoin crypto news"

    # Mock DuckDuckGo search results
    mock_ddg_results = [
        {
            "title": "Bitcoin hits new high",
            "body": "BTC surges to $100k",
            "href": "https://example.com/btc-news"
        },
        {
            "title": "Crypto rally continues",
            "body": "Markets bullish",
            "href": "https://example.com/crypto"
        }
    ]

    # Mock DDGS context manager
    mock_ddgs = MagicMock()
    mock_ddgs.__enter__ = MagicMock(return_value=mock_ddgs)
    mock_ddgs.__exit__ = MagicMock(return_value=None)
    mock_ddgs.text = MagicMock(return_value=mock_ddg_results)

    # Patch where DDGS is imported (in tools module)
    import src.agent.scanner.tools as tools_module
    original_ddgs = tools_module.DDGS
    tools_module.DDGS = lambda: mock_ddgs
    try:
        results = await execute_web_search_internal(query)
    finally:
        tools_module.DDGS = original_ddgs

    # Verify results
    assert len(results) == 2
    assert results[0]["title"] == "Bitcoin hits new high"
    assert results[0]["snippet"] == "BTC surges to $100k"
    assert results[0]["url"] == "https://example.com/btc-news"
    assert results[1]["title"] == "Crypto rally continues"
    assert results[1]["snippet"] == "Markets bullish"


@pytest.mark.asyncio
async def test_execute_web_search_connection_error():
    """Test web search handles connection errors properly."""
    query = "Bitcoin news"

    # Mock DDGS that raises exception
    mock_ddgs = MagicMock()
    mock_ddgs.__enter__ = MagicMock(return_value=mock_ddgs)
    mock_ddgs.__exit__ = MagicMock(return_value=None)
    mock_ddgs.text = MagicMock(side_effect=Exception("Connection failed"))

    import src.agent.scanner.tools as tools_module
    original_ddgs = tools_module.DDGS
    tools_module.DDGS = lambda: mock_ddgs
    try:
        with pytest.raises(RuntimeError, match="Web search failed"):
            await execute_web_search_internal(query)
    finally:
        tools_module.DDGS = original_ddgs


@pytest.mark.asyncio
async def test_execute_web_search_timeout():
    """Test web search handles timeout errors properly."""
    query = "Bitcoin news"

    # Mock asyncio.wait_for to raise TimeoutError
    with patch('src.agent.scanner.tools.asyncio.wait_for', side_effect=asyncio.TimeoutError()):
        with pytest.raises(RuntimeError, match="Web search timeout"):
            await execute_web_search_internal(query)


@pytest.mark.asyncio
async def test_execute_web_search_empty_results():
    """Test web search raises error on empty results."""
    query = "Bitcoin news"

    # Mock DDGS that returns empty results
    mock_ddgs = MagicMock()
    mock_ddgs.__enter__ = MagicMock(return_value=mock_ddgs)
    mock_ddgs.__exit__ = MagicMock(return_value=None)
    mock_ddgs.text = MagicMock(return_value=[])

    import src.agent.scanner.tools as tools_module
    original_ddgs = tools_module.DDGS
    tools_module.DDGS = lambda: mock_ddgs
    try:
        with pytest.raises(RuntimeError, match="Web search returned empty results"):
            await execute_web_search_internal(query)
    finally:
        tools_module.DDGS = original_ddgs


@pytest.mark.asyncio
async def test_analyze_sentiment_with_llm_success():
    """Test successful sentiment analysis with Claude."""
    symbol = "BTCUSDT"
    web_results = [
        {"title": "Bitcoin rally", "snippet": "BTC up 10%", "url": "https://example.com/1"},
        {"title": "Crypto boom", "snippet": "Markets soaring", "url": "https://example.com/2"}
    ]
    context = "5% up in last hour"

    # Mock Claude API response
    mock_response = MagicMock()
    mock_response.content = [
        MagicMock(text=json.dumps({
            "sentiment_summary": "Very bullish sentiment with strong upward momentum",
            "sentiment_score": 25,
            "key_findings": [
                "Bitcoin surged 10% on institutional buying",
                "ETF inflows reached record highs",
                "Technical indicators show strong buy signals"
            ]
        }))
    ]

    # Mock Anthropic client
    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)

    with patch('src.agent.scanner.tools.anthropic.AsyncAnthropic', return_value=mock_client):
        with patch('os.getenv', return_value='test-api-key'):
            result = await analyze_sentiment_with_llm(symbol, web_results, context)

    # Verify result
    assert result["sentiment_score"] == 25
    assert "bullish" in result["sentiment_summary"].lower()
    assert len(result["key_findings"]) == 3
    assert "Bitcoin surged" in result["key_findings"][0]


@pytest.mark.asyncio
async def test_analyze_sentiment_with_llm_invalid_json():
    """Test sentiment analysis handles invalid JSON response."""
    symbol = "BTCUSDT"
    web_results = [{"title": "Test", "snippet": "Test", "url": "https://example.com"}]

    # Mock Claude API response with invalid JSON
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="This is not valid JSON")]

    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)

    # Create mock APIError as a proper Exception subclass
    class MockAPIError(Exception):
        pass

    with patch('src.agent.scanner.tools.anthropic.AsyncAnthropic', return_value=mock_client):
        with patch('src.agent.scanner.tools.anthropic.APIError', MockAPIError):
            with patch('os.getenv', return_value='test-api-key'):
                with pytest.raises(RuntimeError, match="Failed to parse Claude response as JSON"):
                    await analyze_sentiment_with_llm(symbol, web_results)


@pytest.mark.asyncio
async def test_analyze_sentiment_with_llm_missing_fields():
    """Test sentiment analysis validates required fields."""
    symbol = "BTCUSDT"
    web_results = [{"title": "Test", "snippet": "Test", "url": "https://example.com"}]

    # Mock Claude API response missing required fields
    mock_response = MagicMock()
    mock_response.content = [
        MagicMock(text=json.dumps({
            "sentiment_summary": "Test summary"
            # Missing sentiment_score and key_findings
        }))
    ]

    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)

    # Create mock APIError as a proper Exception subclass
    class MockAPIError(Exception):
        pass

    with patch('src.agent.scanner.tools.anthropic.AsyncAnthropic', return_value=mock_client):
        with patch('src.agent.scanner.tools.anthropic.APIError', MockAPIError):
            with patch('os.getenv', return_value='test-api-key'):
                with pytest.raises(RuntimeError, match="Response missing 'sentiment_score' field|Sentiment analysis failed"):
                    await analyze_sentiment_with_llm(symbol, web_results)


@pytest.mark.asyncio
async def test_analyze_sentiment_with_llm_score_clamping():
    """Test sentiment score is clamped to 0-30 range."""
    symbol = "BTCUSDT"
    web_results = [{"title": "Test", "snippet": "Test", "url": "https://example.com"}]

    # Mock Claude API response with out-of-range score
    mock_response = MagicMock()
    mock_response.content = [
        MagicMock(text=json.dumps({
            "sentiment_summary": "Test",
            "sentiment_score": 50,  # Over max
            "key_findings": ["Test"]
        }))
    ]

    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)

    with patch('src.agent.scanner.tools.anthropic.AsyncAnthropic', return_value=mock_client):
        with patch('os.getenv', return_value='test-api-key'):
            result = await analyze_sentiment_with_llm(symbol, web_results)

    # Verify score was clamped to 30
    assert result["sentiment_score"] == 30


@pytest.mark.asyncio
async def test_analyze_sentiment_with_llm_markdown_wrapped_json():
    """Test sentiment analysis handles JSON wrapped in markdown code blocks."""
    symbol = "BTCUSDT"
    web_results = [{"title": "Test", "snippet": "Test", "url": "https://example.com"}]

    # Mock Claude API response with markdown-wrapped JSON
    mock_response = MagicMock()
    mock_response.content = [
        MagicMock(text=f"""Here's the analysis:

```json
{json.dumps({
    "sentiment_summary": "Test summary",
    "sentiment_score": 20,
    "key_findings": ["Finding 1", "Finding 2", "Finding 3"]
})}
```

Hope this helps!""")
    ]

    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)

    with patch('src.agent.scanner.tools.anthropic.AsyncAnthropic', return_value=mock_client):
        with patch('os.getenv', return_value='test-api-key'):
            result = await analyze_sentiment_with_llm(symbol, web_results)

    # Verify result was parsed correctly
    assert result["sentiment_score"] == 20
    assert result["sentiment_summary"] == "Test summary"
    assert len(result["key_findings"]) == 3


@pytest.mark.asyncio
async def test_analyze_sentiment_with_llm_api_error():
    """Test sentiment analysis handles Anthropic API errors."""
    symbol = "BTCUSDT"
    web_results = [{"title": "Test", "snippet": "Test", "url": "https://example.com"}]

    # Create a custom exception for API error
    class MockAPIError(Exception):
        pass

    # Mock Anthropic client to raise API error
    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(side_effect=MockAPIError("API rate limit exceeded"))

    # Patch the APIError class in the tools module
    with patch('src.agent.scanner.tools.anthropic.AsyncAnthropic', return_value=mock_client):
        with patch('src.agent.scanner.tools.anthropic.APIError', MockAPIError):
            with patch('os.getenv', return_value='test-api-key'):
                with pytest.raises(RuntimeError, match="Claude API error|Sentiment analysis failed"):
                    await analyze_sentiment_with_llm(symbol, web_results)


@pytest.mark.asyncio
async def test_analyze_sentiment_with_llm_empty_response():
    """Test sentiment analysis handles empty Claude response."""
    symbol = "BTCUSDT"
    web_results = [{"title": "Test", "snippet": "Test", "url": "https://example.com"}]

    # Mock Claude API response with empty content
    mock_response = MagicMock()
    mock_response.content = []

    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)

    # Create mock APIError as a proper Exception subclass
    class MockAPIError(Exception):
        pass

    with patch('src.agent.scanner.tools.anthropic.AsyncAnthropic', return_value=mock_client):
        with patch('src.agent.scanner.tools.anthropic.APIError', MockAPIError):
            with patch('os.getenv', return_value='test-api-key'):
                with pytest.raises(RuntimeError, match="Empty response from Claude API|Sentiment analysis failed"):
                    await analyze_sentiment_with_llm(symbol, web_results)


@pytest.mark.asyncio
async def test_fetch_sentiment_data_success():
    """Test full integration of fetch_sentiment_data with all components."""
    symbol = "BTCUSDT"
    context = "5% up in last hour"

    # Mock web search results
    web_results = [
        {"title": "Bitcoin surge", "snippet": "BTC up significantly", "url": "https://example.com/1"}
    ]

    # Mock sentiment analysis result
    sentiment_result = {
        "sentiment_summary": "Bullish sentiment",
        "sentiment_score": 22,
        "key_findings": ["Strong momentum", "High volume", "Positive news"]
    }

    # Patch internal functions
    with patch('src.agent.scanner.tools.generate_sentiment_query_internal', new=AsyncMock(return_value="Bitcoin crypto news")):
        with patch('src.agent.scanner.tools.execute_web_search_internal', new=AsyncMock(return_value=web_results)):
            with patch('src.agent.scanner.tools.analyze_sentiment_with_llm', new=AsyncMock(return_value=sentiment_result)):
                # Call the handler directly
                result = await fetch_sentiment_data.handler({"symbol": symbol, "context": context})

    # Extract data from tool response format
    response_data = json.loads(result["content"][0]["text"])

    # Verify response structure
    assert response_data["success"] is True
    assert response_data["sentiment_score"] == 22
    assert response_data["sentiment_summary"] == "Bullish sentiment"
    assert len(response_data["key_findings"]) == 3
    assert len(response_data["web_results"]) == 1
    assert "Bitcoin crypto news" in response_data["sentiment_query"]


@pytest.mark.asyncio
async def test_fetch_sentiment_data_web_search_fails():
    """Test fetch_sentiment_data propagates web search errors."""
    symbol = "BTCUSDT"
    context = ""

    # Patch to raise error during web search
    with patch('src.agent.scanner.tools.generate_sentiment_query_internal', new=AsyncMock(return_value="Bitcoin news")):
        with patch('src.agent.scanner.tools.execute_web_search_internal', new=AsyncMock(side_effect=RuntimeError("Web search timeout"))):
            with pytest.raises(RuntimeError, match="Web search failed for BTCUSDT"):
                await fetch_sentiment_data.handler({"symbol": symbol, "context": context})


@pytest.mark.asyncio
async def test_fetch_sentiment_data_llm_fails():
    """Test fetch_sentiment_data propagates LLM analysis errors."""
    symbol = "BTCUSDT"
    context = ""

    web_results = [{"title": "Test", "snippet": "Test", "url": "https://example.com"}]

    # Patch to raise error during LLM analysis
    with patch('src.agent.scanner.tools.generate_sentiment_query_internal', new=AsyncMock(return_value="Bitcoin news")):
        with patch('src.agent.scanner.tools.execute_web_search_internal', new=AsyncMock(return_value=web_results)):
            with patch('src.agent.scanner.tools.analyze_sentiment_with_llm', new=AsyncMock(side_effect=RuntimeError("Claude API error"))):
                with pytest.raises(RuntimeError, match="Sentiment analysis failed for BTCUSDT"):
                    await fetch_sentiment_data.handler({"symbol": symbol, "context": context})


@pytest.mark.asyncio
async def test_fetch_sentiment_data_query_generation_fails():
    """Test fetch_sentiment_data handles query generation failures."""
    symbol = "BTCUSDT"
    context = ""

    # Patch to raise error during query generation
    with patch('src.agent.scanner.tools.generate_sentiment_query_internal', new=AsyncMock(side_effect=Exception("Query generation failed"))):
        with pytest.raises(RuntimeError, match="Sentiment query generation failed"):
            await fetch_sentiment_data.handler({"symbol": symbol, "context": context})


def test_get_web_search_url_default():
    """Test get_web_search_url returns default when no config set."""
    # Clear any existing config
    set_scanner_config(None)

    url = get_web_search_url()
    assert url == "http://localhost:3000/mcp"


def test_get_web_search_url_from_config():
    """Test get_web_search_url uses config value when set."""
    config = ScannerConfig(web_search_mcp_url="http://custom:4000/mcp")
    set_scanner_config(config)

    url = get_web_search_url()
    assert url == "http://custom:4000/mcp"

    # Cleanup
    set_scanner_config(None)


def test_get_web_search_timeout_default():
    """Test get_web_search_timeout returns default when no config set."""
    # Clear any existing config
    set_scanner_config(None)

    timeout = get_web_search_timeout()
    assert timeout == 30


def test_get_web_search_timeout_from_config():
    """Test get_web_search_timeout uses config value when set."""
    config = ScannerConfig(web_search_timeout_seconds=60)
    set_scanner_config(config)

    timeout = get_web_search_timeout()
    assert timeout == 60

    # Cleanup
    set_scanner_config(None)
