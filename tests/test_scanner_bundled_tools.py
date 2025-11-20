"""Tests for scanner bundled tools."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.agent.scanner.tools import fetch_technical_snapshot, fetch_sentiment_data


def generate_mock_ohlcv(periods=200, start_price=100):
    """Generate mock OHLCV data."""
    data = []
    price = start_price
    for i in range(periods):
        price += (i % 10 - 5) * 0.5
        data.append({
            'timestamp': i * 3600000,
            'open': price - 0.5,
            'high': price + 1,
            'low': price - 1,
            'close': price,
            'volume': 1000000 + (i * 1000)
        })
    return data


@pytest.mark.asyncio
async def test_fetch_technical_snapshot_success():
    """Test successful fetch and analysis of all technical data."""
    # Mock the internal fetch functions
    mock_15m_data = generate_mock_ohlcv(200, 100)
    mock_1h_data = generate_mock_ohlcv(200, 105)
    mock_4h_data = generate_mock_ohlcv(200, 110)
    mock_price = 93500.0

    with patch('src.agent.scanner.tools.fetch_market_data_internal') as mock_fetch, \
         patch('src.agent.scanner.tools.get_current_price_internal') as mock_price_fn:

        # Setup mocks to return successful data
        mock_fetch.side_effect = [mock_15m_data, mock_1h_data, mock_4h_data]
        mock_price_fn.return_value = mock_price

        # Call the tool handler function
        result = await fetch_technical_snapshot.handler({"symbol": "BTCUSDT"})

        # Verify structure
        assert "content" in result
        content = result["content"][0]
        assert content["type"] == "text"

        import json
        data = json.loads(content["text"])

        # Verify all timeframes present with analyzed data
        assert "timeframes" in data
        assert "15m" in data["timeframes"]
        assert "1h" in data["timeframes"]
        assert "4h" in data["timeframes"]

        # Verify each timeframe has analysis
        for tf in ["15m", "1h", "4h"]:
            tf_data = data["timeframes"][tf]
            assert tf_data["status"] == "success"
            assert "trend" in tf_data
            assert "momentum" in tf_data
            assert "volatility" in tf_data
            assert "patterns" in tf_data

            # Verify scores exist
            assert "score" in tf_data["trend"]
            assert "score" in tf_data["momentum"]
            assert "score" in tf_data["volatility"]

        # Verify current price
        assert data["current_price"] == mock_price

        # Verify symbol
        assert data["symbol"] == "BTCUSDT"

        # Verify summary exists
        assert "summary" in data
        assert "overall_trend" in data["summary"]
        assert "overall_momentum" in data["summary"]
        assert "volatility_level" in data["summary"]

        # Verify success count
        assert data["data_fetch_success"] == 4


@pytest.mark.asyncio
async def test_fetch_technical_snapshot_partial_failure():
    """Test fetch with one timeframe failing."""
    mock_15m_data = generate_mock_ohlcv(200, 100)
    mock_1h_data = generate_mock_ohlcv(200, 105)
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

        # Verify partial success - 15m and 1h should have analyzed data
        assert data["timeframes"]["15m"]["status"] == "success"
        assert data["timeframes"]["1h"]["status"] == "success"

        # 4h should show failure
        assert data["timeframes"]["4h"]["status"] == "failed"
        assert "error" in data["timeframes"]["4h"]

        assert data["current_price"] == mock_price

        # Verify warning present
        assert len(data["warnings"]) >= 1
        assert any("4h data fetch failed" in w for w in data["warnings"])
        assert data["data_fetch_success"] == 3  # 3 out of 4 succeeded


@pytest.mark.asyncio
async def test_fetch_technical_snapshot_insufficient_data():
    """Test fetch with insufficient data for analysis."""
    # Only 50 periods - may be enough for some indicators but not all
    mock_15m_data = generate_mock_ohlcv(50, 100)
    mock_1h_data = generate_mock_ohlcv(50, 105)
    mock_4h_data = generate_mock_ohlcv(50, 110)
    mock_price = 93500.0

    with patch('src.agent.scanner.tools.fetch_market_data_internal') as mock_fetch, \
         patch('src.agent.scanner.tools.get_current_price_internal') as mock_price_fn:

        mock_fetch.side_effect = [mock_15m_data, mock_1h_data, mock_4h_data]
        mock_price_fn.return_value = mock_price

        result = await fetch_technical_snapshot.handler({"symbol": "BTCUSDT"})

        import json
        data = json.loads(result["content"][0]["text"])

        # Data fetch should succeed
        assert data["data_fetch_success"] == 4

        # With 50 periods, analysis should still succeed for most indicators
        # Verify at least one timeframe has successful analysis
        assert any(tf["status"] == "success" for tf in data["timeframes"].values())


@pytest.mark.asyncio
async def test_fetch_sentiment_data_success():
    """Test successful fetch of sentiment data."""
    mock_query = "Bitcoin BTC price analysis catalysts"
    mock_web_results = [
        {"title": "BTC ETF Approved", "snippet": "SEC approves...", "url": "https://..."},
        {"title": "Institutional Demand", "snippet": "Major funds...", "url": "https://..."}
    ]

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
