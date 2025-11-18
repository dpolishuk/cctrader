import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from agent.scanner.main_loop import MarketMoversScanner
from agent.scanner.config import ScannerConfig
from agent.scanner.risk_config import RiskConfig

@pytest.mark.asyncio
async def test_scanner_initialization():
    """Test scanner initializes with dependencies."""
    mock_exchange = AsyncMock()
    mock_agent = AsyncMock()
    mock_portfolio = AsyncMock()
    mock_db = AsyncMock()

    scanner = MarketMoversScanner(
        exchange=mock_exchange,
        agent=mock_agent,
        portfolio=mock_portfolio,
        db=mock_db
    )

    assert scanner.exchange == mock_exchange
    assert scanner.agent == mock_agent
    assert scanner.portfolio == mock_portfolio
    assert scanner.db == mock_db
    assert isinstance(scanner.config, ScannerConfig)
    assert isinstance(scanner.risk_config, RiskConfig)

@pytest.mark.asyncio
async def test_pre_filter_movers_by_volume():
    """Test pre-filtering movers by volume threshold."""
    mock_exchange = AsyncMock()
    mock_exchange.fetch_ticker = AsyncMock(side_effect=[
        {'quoteVolume': 10_000_000},  # BTC - high volume
        {'quoteVolume': 1_000_000},    # ETH - low volume (below 5M)
    ])

    scanner = MarketMoversScanner(
        exchange=mock_exchange,
        agent=AsyncMock(),
        portfolio=AsyncMock(),
        db=AsyncMock()
    )

    movers = {
        'gainers': [
            {'symbol': 'BTC/USDT', 'max_change': 8.0},
            {'symbol': 'ETH/USDT', 'max_change': 6.0},
        ],
        'losers': []
    }

    filtered = await scanner.pre_filter_movers(movers)

    assert len(filtered) == 1
    assert filtered[0]['symbol'] == 'BTC/USDT'

@pytest.mark.asyncio
async def test_scanner_respects_max_movers_limit():
    """Test scanner limits to max_movers_per_scan."""
    mock_exchange = AsyncMock()
    mock_exchange.fetch_ticker = AsyncMock(return_value={'quoteVolume': 10_000_000})

    scanner = MarketMoversScanner(
        exchange=mock_exchange,
        agent=AsyncMock(),
        portfolio=AsyncMock(),
        db=AsyncMock()
    )
    scanner.config.max_movers_per_scan = 2

    # Create 5 movers
    movers = {
        'gainers': [
            {'symbol': f'SYM{i}/USDT', 'max_change': 10 - i}
            for i in range(5)
        ],
        'losers': []
    }

    filtered = await scanner.pre_filter_movers(movers)

    assert len(filtered) == 2
    # Should take highest % change
    assert filtered[0]['max_change'] == 10
    assert filtered[1]['max_change'] == 9

@pytest.mark.asyncio
async def test_scan_cycle_with_no_movers():
    """Test scan cycle when no movers are detected."""
    mock_exchange = AsyncMock()
    mock_agent = AsyncMock()
    mock_portfolio = AsyncMock()
    mock_portfolio.count_open_positions = MagicMock(return_value=0)
    mock_portfolio.get_total_value = MagicMock(return_value=10000.0)
    mock_portfolio.calculate_exposure_pct = MagicMock(return_value=0.0)
    mock_db = AsyncMock()

    scanner = MarketMoversScanner(
        exchange=mock_exchange,
        agent=mock_agent,
        portfolio=mock_portfolio,
        db=mock_db
    )

    # Mock momentum scanner to return no movers
    scanner.momentum_scanner.scan_all_symbols = AsyncMock(return_value={
        'gainers': [],
        'losers': []
    })

    await scanner.scan_cycle()

    # Should not call agent if no movers
    mock_agent.run.assert_not_called()
    # Should save metrics
    mock_db.save_movers_metrics.assert_called_once()

@pytest.mark.asyncio
async def test_scan_cycle_with_low_confidence_signal():
    """Test scan cycle rejects signals with confidence < 60."""
    mock_exchange = AsyncMock()
    mock_exchange.fetch_ticker = AsyncMock(return_value={'quoteVolume': 10_000_000})

    # Agent returns low confidence signal
    mock_agent = AsyncMock()
    mock_agent.run = AsyncMock(return_value={
        'confidence': 45,
        'symbol': 'BTC/USDT',
        'direction': 'LONG',
    })

    mock_portfolio = AsyncMock()
    mock_portfolio.count_open_positions = MagicMock(return_value=0)
    mock_portfolio.get_total_value = MagicMock(return_value=10000.0)
    mock_portfolio.calculate_exposure_pct = MagicMock(return_value=0.0)
    mock_db = AsyncMock()

    scanner = MarketMoversScanner(
        exchange=mock_exchange,
        agent=mock_agent,
        portfolio=mock_portfolio,
        db=mock_db
    )

    # Mock momentum scanner to return one mover
    scanner.momentum_scanner.scan_all_symbols = AsyncMock(return_value={
        'gainers': [
            {
                'symbol': 'BTC/USDT',
                'change_1h': 6.5,
                'change_4h': 5.2,
                'max_change': 6.5,
                'direction': 'LONG',
                'current_price': 50000.0,
            }
        ],
        'losers': []
    })

    await scanner.scan_cycle()

    # Should call agent
    assert mock_agent.run.called
    # Should save rejection (low confidence)
    mock_db.save_mover_rejection.assert_called_once()
    # Should not execute trade
    mock_portfolio.execute_paper_trade.assert_not_called()

@pytest.mark.asyncio
async def test_scan_cycle_executes_high_confidence_signal():
    """Test scan cycle executes signal with confidence >= 60."""
    mock_exchange = AsyncMock()
    mock_exchange.fetch_ticker = AsyncMock(return_value={'quoteVolume': 10_000_000})

    # Agent returns high confidence signal
    mock_agent = AsyncMock()
    mock_agent.run = AsyncMock(return_value={
        'confidence': 85,
        'symbol': 'BTC/USDT',
        'direction': 'LONG',
        'entry_price': 50000.0,
        'stop_loss': 48000.0,
        'tp1': 54000.0,
        'technical_score': 35.0,
        'sentiment_score': 25.0,
        'liquidity_score': 18.0,
        'correlation_score': 7.0,
        'analysis': 'Strong bullish setup',
    })

    mock_portfolio = AsyncMock()
    mock_portfolio.count_open_positions = MagicMock(return_value=0)
    mock_portfolio.get_total_value = MagicMock(return_value=10000.0)
    mock_portfolio.calculate_exposure_pct = MagicMock(return_value=0.0)

    mock_db = AsyncMock()
    mock_db.save_mover_signal = AsyncMock(return_value=123)  # signal_id

    scanner = MarketMoversScanner(
        exchange=mock_exchange,
        agent=mock_agent,
        portfolio=mock_portfolio,
        db=mock_db
    )

    # Mock momentum scanner to return one mover
    scanner.momentum_scanner.scan_all_symbols = AsyncMock(return_value={
        'gainers': [
            {
                'symbol': 'BTC/USDT',
                'change_1h': 6.5,
                'change_4h': 5.2,
                'max_change': 6.5,
                'direction': 'LONG',
                'current_price': 50000.0,
            }
        ],
        'losers': []
    })

    # Mock risk validator to pass
    scanner.risk_validator.validate_signal = AsyncMock(return_value={
        'valid': True,
        'reason': None
    })

    await scanner.scan_cycle()

    # Should call agent
    assert mock_agent.run.called
    # Should save signal
    assert mock_db.save_mover_signal.called
    # Should execute trade
    assert mock_portfolio.execute_paper_trade.called
    # Should save metrics
    assert mock_db.save_movers_metrics.called

@pytest.mark.asyncio
async def test_scan_cycle_rejects_signal_failing_risk_check():
    """Test scan cycle rejects signal that fails risk validation."""
    mock_exchange = AsyncMock()
    mock_exchange.fetch_ticker = AsyncMock(return_value={'quoteVolume': 10_000_000})

    # Agent returns high confidence signal
    mock_agent = AsyncMock()
    mock_agent.run = AsyncMock(return_value={
        'confidence': 75,
        'symbol': 'BTC/USDT',
        'direction': 'LONG',
        'entry_price': 50000.0,
        'stop_loss': 48000.0,
        'tp1': 54000.0,
    })

    mock_portfolio = AsyncMock()
    mock_portfolio.count_open_positions = MagicMock(return_value=5)  # At max
    mock_portfolio.get_total_value = MagicMock(return_value=10000.0)
    mock_portfolio.calculate_exposure_pct = MagicMock(return_value=0.0)
    mock_db = AsyncMock()

    scanner = MarketMoversScanner(
        exchange=mock_exchange,
        agent=mock_agent,
        portfolio=mock_portfolio,
        db=mock_db
    )

    # Mock momentum scanner
    scanner.momentum_scanner.scan_all_symbols = AsyncMock(return_value={
        'gainers': [
            {
                'symbol': 'BTC/USDT',
                'change_1h': 6.5,
                'change_4h': 5.2,
                'max_change': 6.5,
                'direction': 'LONG',
                'current_price': 50000.0,
            }
        ],
        'losers': []
    })

    # Mock risk validator to fail (max positions)
    scanner.risk_validator.validate_signal = AsyncMock(return_value={
        'valid': False,
        'reason': 'At maximum positions'
    })

    await scanner.scan_cycle()

    # Should call agent
    assert mock_agent.run.called
    # Should save rejection
    mock_db.save_mover_rejection.assert_called_once()
    # Should not execute trade
    mock_portfolio.execute_paper_trade.assert_not_called()
