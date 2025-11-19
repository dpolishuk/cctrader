"""Tests for scanner bundled tools."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.agent.scanner.tools import fetch_technical_snapshot, fetch_sentiment_data


@pytest.mark.asyncio
async def test_fetch_technical_snapshot_success():
    """Test successful fetch of all technical data."""
    # Mock the internal fetch functions
    mock_15m_data = {"ohlcv": [[1, 2, 3, 4, 5]], "indicators": {"rsi": 50}}
    mock_1h_data = {"ohlcv": [[6, 7, 8, 9, 10]], "indicators": {"rsi": 55}}
    mock_4h_data = {"ohlcv": [[11, 12, 13, 14, 15]], "indicators": {"rsi": 60}}
    mock_price = 93500.0

    with patch('src.agent.scanner.tools.fetch_market_data_internal') as mock_fetch, \
         patch('src.agent.scanner.tools.get_current_price_internal') as mock_price_fn:

        # Setup mocks to return successful data
        mock_fetch.side_effect = [mock_15m_data, mock_1h_data, mock_4h_data]
        mock_price_fn.return_value = mock_price

        # Call the tool handler function (the @tool decorator wraps it)
        result = await fetch_technical_snapshot.handler({"symbol": "BTCUSDT"})

        # Verify structure
        assert "content" in result
        content = result["content"][0]
        assert content["type"] == "text"

        import json
        data = json.loads(content["text"])

        # Verify all timeframes present
        assert "timeframes" in data
        assert "15m" in data["timeframes"]
        assert "1h" in data["timeframes"]
        assert "4h" in data["timeframes"]
        assert data["timeframes"]["15m"] == mock_15m_data
        assert data["timeframes"]["1h"] == mock_1h_data
        assert data["timeframes"]["4h"] == mock_4h_data

        # Verify current price
        assert data["current_price"] == mock_price

        # Verify no warnings
        assert data["warnings"] == []
        assert data["success_count"] == 4


@pytest.mark.asyncio
async def test_fetch_technical_snapshot_partial_failure():
    """Test fetch with one timeframe failing."""
    mock_15m_data = {"ohlcv": [[1, 2, 3, 4, 5]], "indicators": {"rsi": 50}}
    mock_1h_data = {"ohlcv": [[6, 7, 8, 9, 10]], "indicators": {"rsi": 55}}
    mock_price = 93500.0

    with patch('src.agent.scanner.tools.fetch_market_data_internal') as mock_fetch, \
         patch('src.agent.scanner.tools.get_current_price_internal') as mock_price_fn:

        # 4h fetch fails, others succeed
        mock_fetch.side_effect = [
            mock_15m_data,
            mock_1h_data,
            Exception("API rate limit exceeded")  # 4h fails
        ]
        mock_price_fn.return_value = mock_price

        result = await fetch_technical_snapshot.handler({"symbol": "BTCUSDT"})

        import json
        data = json.loads(result["content"][0]["text"])

        # Verify partial success
        assert data["timeframes"]["15m"] == mock_15m_data
        assert data["timeframes"]["1h"] == mock_1h_data
        assert data["timeframes"]["4h"] is None  # Failed
        assert data["current_price"] == mock_price

        # Verify warning present
        assert len(data["warnings"]) == 1
        assert "4h data fetch failed" in data["warnings"][0]
        assert data["success_count"] == 3  # 3 out of 4 succeeded


@pytest.mark.asyncio
async def test_fetch_sentiment_data_success():
    """Test successful fetch of sentiment data."""
    mock_query = "Bitcoin BTC price analysis catalysts"
    mock_web_results = [
        {"title": "BTC ETF Approved", "snippet": "SEC approves...", "url": "https://..."},
        {"title": "Institutional Demand", "snippet": "Major funds...", "url": "https://..."}
    ]
    mock_summary = "Positive catalysts: ETF approval, institutional demand"

    with patch('src.agent.scanner.tools.generate_sentiment_query_internal') as mock_query_fn, \
         patch('src.agent.scanner.tools.execute_web_search_internal') as mock_search:

        mock_query_fn.return_value = mock_query
        mock_search.return_value = mock_web_results

        result = await fetch_sentiment_data.handler({"symbol": "BTCUSDT", "context": "5% up"})

        import json
        data = json.loads(result["content"][0]["text"])

        # Verify query generated
        assert data["sentiment_query"] == mock_query

        # Verify web results
        assert data["web_results"] == mock_web_results

        # Verify summary exists
        assert "sentiment_summary" in data
        assert len(data["sentiment_summary"]) > 0

        # Verify sentiment score suggested
        assert "suggested_sentiment_score" in data
        assert 0 <= data["suggested_sentiment_score"] <= 30

        # Verify no warnings
        assert data["warnings"] == []
        assert data["success"] is True


@pytest.mark.asyncio
async def test_fetch_sentiment_data_web_search_failure():
    """Test fetch_sentiment_data with web search failure."""
    mock_query = "Bitcoin BTC price analysis catalysts"

    with patch('src.agent.scanner.tools.generate_sentiment_query_internal') as mock_query_fn, \
         patch('src.agent.scanner.tools.execute_web_search_internal') as mock_search:

        mock_query_fn.return_value = mock_query
        mock_search.side_effect = Exception("Web search API error")

        result = await fetch_sentiment_data.handler({"symbol": "BTCUSDT", "context": "5% up"})

        import json
        data = json.loads(result["content"][0]["text"])

        # Verify query still generated
        assert data["sentiment_query"] == mock_query

        # Verify web results empty due to failure
        assert data["web_results"] == []

        # Verify warning generated
        assert len(data["warnings"]) == 1
        assert "Web search failed" in data["warnings"][0]

        # Verify success is False
        assert data["success"] is False

        # Verify neutral sentiment score (15/30) when no results
        assert data["suggested_sentiment_score"] == 15
        assert "No web results" in data["sentiment_summary"]
