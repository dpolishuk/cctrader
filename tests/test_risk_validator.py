import pytest
from unittest.mock import AsyncMock, MagicMock
from src.agent.scanner.risk_validator import RiskValidator
from src.agent.scanner.risk_config import RiskConfig

@pytest.mark.asyncio
async def test_validate_all_checks_pass():
    """Test validation when all risk checks pass."""
    mock_portfolio = AsyncMock()
    mock_portfolio.count_open_positions = AsyncMock(return_value=2)
    mock_portfolio.calculate_exposure_pct = AsyncMock(return_value=10.0)
    mock_portfolio.calculate_daily_pnl_pct = AsyncMock(return_value=-2.0)
    mock_portfolio.calculate_weekly_pnl_pct = AsyncMock(return_value=3.0)
    mock_portfolio.get_open_positions = AsyncMock(return_value=[])

    config = RiskConfig()
    validator = RiskValidator(config, mock_portfolio)

    signal = {
        'symbol': 'BTC/USDT',
        'confidence': 75,
        'position_size_pct': 2.0,
        'risk_amount_pct': 1.5,
    }

    result = await validator.validate_signal(signal)

    assert result['valid'] is True
    assert result['reason'] is None

@pytest.mark.asyncio
async def test_reject_low_confidence():
    """Test rejection when confidence below threshold."""
    mock_portfolio = AsyncMock()
    config = RiskConfig()
    validator = RiskValidator(config, mock_portfolio)

    signal = {'confidence': 50}

    result = await validator.validate_signal(signal)

    assert result['valid'] is False
    assert 'confidence' in result['reason'].lower()

@pytest.mark.asyncio
async def test_reject_max_positions():
    """Test rejection when at max positions."""
    mock_portfolio = AsyncMock()
    mock_portfolio.count_open_positions = AsyncMock(return_value=5)

    config = RiskConfig()
    validator = RiskValidator(config, mock_portfolio)

    signal = {'confidence': 75}

    result = await validator.validate_signal(signal)

    assert result['valid'] is False
    assert 'position' in result['reason'].lower()

@pytest.mark.asyncio
async def test_reject_exposure_limit():
    """Test rejection when exposure limit exceeded."""
    mock_portfolio = AsyncMock()
    mock_portfolio.count_open_positions = AsyncMock(return_value=2)
    mock_portfolio.calculate_exposure_pct = AsyncMock(return_value=20.0)
    mock_portfolio.total_value = 10000

    config = RiskConfig()
    validator = RiskValidator(config, mock_portfolio)

    signal = {
        'confidence': 75,
        'position_size_usd': 800,  # Would push total to 28%
    }

    result = await validator.validate_signal(signal)

    assert result['valid'] is False
    assert 'exposure' in result['reason'].lower()

@pytest.mark.asyncio
async def test_reject_daily_loss_limit():
    """Test rejection when daily loss limit hit."""
    mock_portfolio = AsyncMock()
    mock_portfolio.count_open_positions = AsyncMock(return_value=2)
    mock_portfolio.calculate_exposure_pct = AsyncMock(return_value=10.0)
    mock_portfolio.calculate_daily_pnl_pct = AsyncMock(return_value=-8.5)

    config = RiskConfig()
    validator = RiskValidator(config, mock_portfolio)

    signal = {'confidence': 75, 'position_size_pct': 2.0}

    result = await validator.validate_signal(signal)

    assert result['valid'] is False
    assert 'daily' in result['reason'].lower()

@pytest.mark.asyncio
async def test_reject_correlation_limit():
    """Test rejection when too many correlated positions."""
    mock_portfolio = AsyncMock()
    mock_portfolio.count_open_positions = AsyncMock(return_value=2)
    mock_portfolio.calculate_exposure_pct = AsyncMock(return_value=10.0)
    mock_portfolio.calculate_daily_pnl_pct = AsyncMock(return_value=-2.0)
    mock_portfolio.calculate_weekly_pnl_pct = AsyncMock(return_value=1.0)

    # Already have 2 BTC-correlated positions
    mock_portfolio.get_open_positions = AsyncMock(return_value=[
        {'symbol': 'ETHUSDT'},
        {'symbol': 'SOLUSDT'},
    ])

    config = RiskConfig()
    validator = RiskValidator(config, mock_portfolio)

    signal = {
        'symbol': 'ADAUSDT',  # Also BTC-correlated
        'confidence': 75,
        'position_size_pct': 2.0,
        'risk_amount_pct': 1.5,
    }

    result = await validator.validate_signal(signal)

    assert result['valid'] is False
    assert 'group' in result['reason'].lower() or 'correlated' in result['reason'].lower()
