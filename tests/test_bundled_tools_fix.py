"""Test that bundled tools correctly parse market data responses."""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch
from src.agent.scanner.tools import fetch_market_data_internal, get_current_price_internal


@pytest.mark.asyncio
async def test_fetch_market_data_internal_parses_response_correctly():
    """Test that fetch_market_data_internal extracts data from correct field."""
    # Mock response matching actual fetch_market_data format
    mock_response = {
        "content": [{
            "type": "text",
            "text": "Fetched 10 candles for BTC/USDT (15m)\nLatest price: 89336.80"
        }],
        "data": [
            {
                "timestamp": "2025-11-19T18:15:00",
                "open": 89300.0,
                "high": 89400.0,
                "low": 89200.0,
                "close": 89336.80,
                "volume": 1234.5
            }
        ]
    }

    with patch('src.agent.tools.market_data.fetch_market_data') as mock_tool:
        mock_tool.handler = AsyncMock(return_value=mock_response)

        result = await fetch_market_data_internal("BTC/USDT", "15m", 10)

        # Should return the data array, not empty dict
        assert result is not None
        assert len(result) > 0
        assert "timestamp" in result[0]
        assert result[0]["close"] == 89336.80


@pytest.mark.asyncio
async def test_get_current_price_internal_parses_response_correctly():
    """Test that get_current_price_internal extracts price from correct field."""
    # Mock response matching actual get_current_price format
    mock_response = {
        "content": [{
            "type": "text",
            "text": "BTC/USDT Current Price: $89336.80\n24h Change: 2.5%"
        }],
        "price": 89336.80,
        "change_24h": 2.5,
        "volume_24h": 1234567890.0
    }

    with patch('src.agent.tools.market_data.get_current_price') as mock_tool:
        mock_tool.handler = AsyncMock(return_value=mock_response)

        result = await get_current_price_internal("BTC/USDT")

        # Should return the price, not 0.0
        assert result == 89336.80
