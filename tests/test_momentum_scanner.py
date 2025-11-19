import pytest
from unittest.mock import AsyncMock
from src.agent.scanner.momentum_scanner import MomentumScanner

@pytest.mark.asyncio
async def test_scan_for_movers_identifies_gainers():
    """Test scanner identifies symbols with ≥5% gains."""
    mock_exchange = AsyncMock()

    # BTC: +6% in 1h, +4% in 4h → Max +6% (gainer)
    # 1h: from 100 to 106 = +6%
    # 4h: from 100 to 104 = +4%
    mock_exchange.fetch_ohlcv = AsyncMock(side_effect=[
        [[0, 100, 105, 99, 100, 1000], [0, 100, 108, 99, 106, 1000]],  # 1h: +6%
        [[0, 100, 104, 99, 100, 1000], [0, 100, 106, 99, 104, 1000]],  # 4h: +4%
    ])

    scanner = MomentumScanner(mock_exchange, threshold_pct=5.0)
    movers = await scanner.scan_symbol('BTC/USDT')

    assert movers is not None
    assert movers['symbol'] == 'BTC/USDT'
    assert movers['direction'] == 'LONG'
    assert movers['max_change'] >= 5.0
    assert movers['change_1h'] == pytest.approx(6.0, abs=0.1)

@pytest.mark.asyncio
async def test_scan_for_movers_identifies_losers():
    """Test scanner identifies symbols with ≥5% losses."""
    mock_exchange = AsyncMock()

    # ETH: -7% in 1h
    # 1h: from 100 to 93 = -7%
    # 4h: from 95 to 95 = 0%
    mock_exchange.fetch_ohlcv = AsyncMock(side_effect=[
        [[0, 100, 102, 92, 100, 1000], [0, 100, 94, 91, 93, 1000]],  # 1h: -7%
        [[0, 95, 98, 93, 95, 1000], [0, 95, 96, 94, 95, 1000]],    # 4h: 0%
    ])

    scanner = MomentumScanner(mock_exchange, threshold_pct=5.0)
    movers = await scanner.scan_symbol('ETH/USDT')

    assert movers is not None
    assert movers['direction'] == 'SHORT'
    assert movers['max_change'] >= 5.0

@pytest.mark.asyncio
async def test_scan_for_movers_filters_below_threshold():
    """Test scanner filters symbols below threshold."""
    mock_exchange = AsyncMock()

    # SOL: +3% in 1h (below 5% threshold)
    # 1h: from 100 to 103 = +3%
    # 4h: from 100 to 102 = +2%
    mock_exchange.fetch_ohlcv = AsyncMock(side_effect=[
        [[0, 100, 103, 99, 100, 1000], [0, 100, 104, 102, 103, 1000]],  # +3%
        [[0, 100, 102, 99, 100, 1000], [0, 100, 103, 101, 102, 1000]],  # +2%
    ])

    scanner = MomentumScanner(mock_exchange, threshold_pct=5.0)
    movers = await scanner.scan_symbol('SOL/USDT')

    assert movers is None

@pytest.mark.asyncio
async def test_scan_all_symbols():
    """Test scanning multiple symbols in batch."""
    mock_exchange = AsyncMock()

    # Setup different responses for different symbols
    # BTC: from 100 to 106 = +6%
    # ETH: from 100 to 102 = +2%
    responses = {
        'BTC/USDT': [
            [[0, 100, 105, 99, 100, 1000], [0, 100, 108, 105, 106, 1000]],  # 1h: +6%
            [[0, 100, 104, 99, 100, 1000], [0, 100, 106, 103, 104, 1000]],  # 4h: +4%
        ],
        'ETH/USDT': [
            [[0, 100, 102, 99, 100, 1000], [0, 100, 103, 101, 102, 1000]],  # 1h: +2%
            [[0, 100, 101, 99, 100, 1000], [0, 100, 102, 100, 101, 1000]],  # 4h: +1%
        ],
    }

    call_count = 0
    async def fetch_ohlcv_side_effect(symbol, timeframe, limit):
        nonlocal call_count
        result = responses[symbol][call_count % 2]
        call_count += 1
        return result

    mock_exchange.fetch_ohlcv = AsyncMock(side_effect=fetch_ohlcv_side_effect)

    scanner = MomentumScanner(mock_exchange, threshold_pct=5.0)
    movers = await scanner.scan_all_symbols(['BTC/USDT', 'ETH/USDT'])

    assert len(movers['gainers']) == 1
    assert movers['gainers'][0]['symbol'] == 'BTC/USDT'
    assert len(movers['losers']) == 0
