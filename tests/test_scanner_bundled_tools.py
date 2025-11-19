"""Tests for scanner bundled tools."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from agent.scanner.tools import fetch_technical_snapshot


@pytest.mark.asyncio
async def test_fetch_technical_snapshot_success():
    """Test successful fetch of all technical data."""
    # Mock the internal fetch functions
    mock_15m_data = {"ohlcv": [[1, 2, 3, 4, 5]], "indicators": {"rsi": 50}}
    mock_1h_data = {"ohlcv": [[6, 7, 8, 9, 10]], "indicators": {"rsi": 55}}
    mock_4h_data = {"ohlcv": [[11, 12, 13, 14, 15]], "indicators": {"rsi": 60}}
    mock_price = 93500.0

    with patch('agent.scanner.tools.fetch_market_data_internal') as mock_fetch, \
         patch('agent.scanner.tools.get_current_price_internal') as mock_price_fn:

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
