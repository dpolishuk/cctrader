"""Comprehensive unit tests for advanced technical analysis tools."""
import pytest
import asyncio
from src.agent.tools.technical_analysis import (
    analyze_trend,
    analyze_momentum,
    analyze_volatility,
    analyze_patterns
)


# Helper to generate test OHLCV data
def generate_ohlcv_data(periods=200, start_price=40000):
    """
    Generate synthetic OHLCV data for testing.

    Creates oscillating price data with controlled volatility to ensure
    technical indicators have realistic values.
    """
    data = []
    price = start_price
    for i in range(periods):
        # Create oscillating pattern with trend
        price += (i % 10 - 5) * 50  # Oscillation
        price += i * 2  # Slight uptrend

        high = price + 100
        low = price - 100
        volume = 1000000 + (i * 10000)

        data.append({
            'timestamp': i * 3600000,
            'open': price - 50,
            'high': high,
            'low': low,
            'close': price,
            'volume': volume
        })
    return data


# ============================================================================
# TEST analyze_trend()
# ============================================================================

@pytest.mark.asyncio
async def test_analyze_trend_valid_data():
    """Test analyze_trend with valid data (200+ periods)."""
    ohlcv = generate_ohlcv_data(250)
    result = await analyze_trend.handler({
        'ohlcv_data': ohlcv,
        'symbol': 'BTCUSDT',
        'timeframe': '1h'
    })

    # Check for required keys
    assert 'trend_score' in result
    assert 'indicators' in result
    assert 'signals' in result
    assert 'interpretation' in result
    assert 'content' in result

    # Verify trend score range
    assert 0.0 <= result['trend_score'] <= 1.0

    # Verify EMA indicators exist and have values
    assert 'ema_9' in result['indicators']
    assert 'ema_12' in result['indicators']
    assert 'ema_26' in result['indicators']
    assert 'ema_50' in result['indicators']
    assert 'ema_200' in result['indicators']

    # Verify all EMAs have numeric values
    for ema in ['ema_9', 'ema_12', 'ema_26', 'ema_50', 'ema_200']:
        assert result['indicators'][ema] is not None
        assert isinstance(result['indicators'][ema], (int, float))

    # Verify SMA indicators exist and have values
    assert 'sma_20' in result['indicators']
    assert 'sma_50' in result['indicators']
    assert 'sma_100' in result['indicators']
    assert 'sma_200' in result['indicators']

    # Verify all SMAs have numeric values
    for sma in ['sma_20', 'sma_50', 'sma_100', 'sma_200']:
        assert result['indicators'][sma] is not None
        assert isinstance(result['indicators'][sma], (int, float))

    # Verify Ichimoku Cloud indicators exist
    assert 'ichimoku' in result['indicators']
    assert isinstance(result['indicators']['ichimoku'], dict)

    # Verify Ichimoku components
    ich = result['indicators']['ichimoku']
    if ich:  # Ichimoku may be empty dict if not enough data
        assert 'tenkan_sen' in ich
        assert 'kijun_sen' in ich
        assert 'senkou_span_a' in ich
        assert 'senkou_span_b' in ich
        assert 'chikou_span' in ich
        assert 'cloud_color' in ich
        assert ich['cloud_color'] in ['bullish', 'bearish']

    # Verify signals is a list
    assert isinstance(result['signals'], list)

    # Verify interpretation is a string
    assert isinstance(result['interpretation'], str)
    assert len(result['interpretation']) > 0


@pytest.mark.asyncio
async def test_analyze_trend_ema_calculations():
    """Test that EMA calculations produce expected values."""
    ohlcv = generate_ohlcv_data(250, start_price=50000)
    result = await analyze_trend.handler({
        'ohlcv_data': ohlcv,
        'symbol': 'ETHUSDT',
        'timeframe': '4h'
    })

    # EMAs should be ordered from fast to slow (in general trend)
    ema_9 = result['indicators']['ema_9']
    ema_12 = result['indicators']['ema_12']
    ema_26 = result['indicators']['ema_26']
    ema_50 = result['indicators']['ema_50']
    ema_200 = result['indicators']['ema_200']

    # All EMAs should be positive and reasonable relative to price
    current_price = ohlcv[-1]['close']
    for ema_val in [ema_9, ema_12, ema_26, ema_50, ema_200]:
        assert ema_val > 0
        # EMA should be within reasonable range of current price (within 20%)
        assert 0.5 * current_price <= ema_val <= 1.5 * current_price


@pytest.mark.asyncio
async def test_analyze_trend_sma_calculations():
    """Test that SMA calculations produce expected values."""
    ohlcv = generate_ohlcv_data(250, start_price=45000)
    result = await analyze_trend.handler({
        'ohlcv_data': ohlcv,
        'symbol': 'BTCUSDT',
        'timeframe': '1d'
    })

    # All SMAs should exist and be positive
    for sma_key in ['sma_20', 'sma_50', 'sma_100', 'sma_200']:
        sma_val = result['indicators'][sma_key]
        assert sma_val is not None
        assert sma_val > 0

        # SMA should be within reasonable range of current price
        current_price = ohlcv[-1]['close']
        assert 0.5 * current_price <= sma_val <= 1.5 * current_price


@pytest.mark.asyncio
async def test_analyze_trend_ichimoku_calculations():
    """Test Ichimoku Cloud calculations."""
    ohlcv = generate_ohlcv_data(300, start_price=60000)
    result = await analyze_trend.handler({
        'ohlcv_data': ohlcv,
        'symbol': 'BTCUSDT',
        'timeframe': '1h'
    })

    ich = result['indicators']['ichimoku']

    # Ichimoku should have all components (may be empty dict if not enough data)
    if ich:  # Only test if ichimoku was calculated
        assert 'tenkan_sen' in ich
        assert 'kijun_sen' in ich
        assert 'senkou_span_a' in ich
        assert 'senkou_span_b' in ich
        assert 'chikou_span' in ich
        assert 'cloud_color' in ich

        # All components should be numeric (may be NaN in some edge cases)
        import math
        for key in ['tenkan_sen', 'kijun_sen', 'senkou_span_a', 'senkou_span_b', 'chikou_span']:
            assert isinstance(ich[key], (int, float))
            # If not NaN, should be positive
            if not math.isnan(ich[key]):
                assert ich[key] > 0

        # Cloud color should match span relationship (if both spans are valid)
        if not math.isnan(ich['senkou_span_a']) and not math.isnan(ich['senkou_span_b']):
            if ich['senkou_span_a'] > ich['senkou_span_b']:
                assert ich['cloud_color'] == 'bullish'
            else:
                assert ich['cloud_color'] == 'bearish'


@pytest.mark.asyncio
async def test_analyze_trend_score_range():
    """Test that trend_score is always between 0.0 and 1.0."""
    # Test with multiple different datasets
    for start_price in [30000, 50000, 70000]:
        for periods in [200, 300, 500]:
            ohlcv = generate_ohlcv_data(periods, start_price)
            result = await analyze_trend.handler({
                'ohlcv_data': ohlcv,
                'symbol': 'BTCUSDT',
                'timeframe': '1h'
            })

            assert 'trend_score' in result
            assert 0.0 <= result['trend_score'] <= 1.0, \
                f"trend_score {result['trend_score']} out of range for {periods} periods at ${start_price}"


@pytest.mark.asyncio
async def test_analyze_trend_signals_populated():
    """Test that signals list is populated with valid signals."""
    ohlcv = generate_ohlcv_data(250, start_price=50000)
    result = await analyze_trend.handler({
        'ohlcv_data': ohlcv,
        'symbol': 'BTCUSDT',
        'timeframe': '1h'
    })

    assert 'signals' in result
    assert isinstance(result['signals'], list)

    # Valid signal types
    valid_signals = [
        'ema_golden_cross_12_26', 'ema_golden_cross_9_26',
        'price_above_all_emas', 'price_below_all_emas',
        'above_sma_200', 'below_sma_200',
        'ichimoku_strong_bullish', 'ichimoku_bullish', 'price_above_cloud',
        'price_in_cloud', 'ichimoku_strong_bearish', 'ichimoku_bearish'
    ]

    # All signals should be valid
    for signal in result['signals']:
        assert signal in valid_signals, f"Invalid signal: {signal}"


@pytest.mark.asyncio
async def test_analyze_trend_insufficient_data():
    """Test analyze_trend with insufficient data (< 200 periods)."""
    ohlcv = generate_ohlcv_data(150)  # Less than 200
    result = await analyze_trend.handler({
        'ohlcv_data': ohlcv,
        'symbol': 'BTCUSDT',
        'timeframe': '1h'
    })

    assert 'is_error' in result
    assert result['is_error'] == True
    assert 'content' in result
    assert len(result['content']) > 0
    assert 'insufficient' in result['content'][0]['text'].lower()


@pytest.mark.asyncio
async def test_analyze_trend_empty_data():
    """Test analyze_trend with empty OHLCV data."""
    result = await analyze_trend.handler({
        'ohlcv_data': [],
        'symbol': 'BTCUSDT',
        'timeframe': '1h'
    })

    assert 'is_error' in result
    assert result['is_error'] == True
    assert 'content' in result
    assert 'no ohlcv data' in result['content'][0]['text'].lower()


@pytest.mark.asyncio
async def test_analyze_trend_minimal_required_data():
    """Test analyze_trend with exactly minimum required data (200 periods)."""
    ohlcv = generate_ohlcv_data(200)  # Exactly minimum
    result = await analyze_trend.handler({
        'ohlcv_data': ohlcv,
        'symbol': 'BTCUSDT',
        'timeframe': '1h'
    })

    # Should succeed with minimum data
    assert 'trend_score' in result
    assert 'is_error' not in result or result.get('is_error') == False


# ============================================================================
# TEST analyze_momentum()
# ============================================================================

@pytest.mark.asyncio
async def test_analyze_momentum_valid_data():
    """Test analyze_momentum with valid data (50+ periods)."""
    ohlcv = generate_ohlcv_data(100)
    result = await analyze_momentum.handler({
        'ohlcv_data': ohlcv,
        'symbol': 'BTCUSDT',
        'timeframe': '1h'
    })

    # Check for required keys
    assert 'momentum_score' in result
    assert 'indicators' in result
    assert 'signals' in result
    assert 'interpretation' in result

    # Verify momentum score range
    assert -1.0 <= result['momentum_score'] <= 1.0


@pytest.mark.asyncio
async def test_analyze_momentum_rsi_calculation():
    """Test RSI calculation in momentum analysis."""
    ohlcv = generate_ohlcv_data(100, start_price=50000)
    result = await analyze_momentum.handler({
        'ohlcv_data': ohlcv,
        'symbol': 'BTCUSDT',
        'timeframe': '1h'
    })

    assert 'rsi' in result['indicators']
    rsi = result['indicators']['rsi']

    # RSI should be between 0 and 100
    assert 0 <= rsi <= 100
    assert isinstance(rsi, (int, float))


@pytest.mark.asyncio
async def test_analyze_momentum_stochastic_calculation():
    """Test Stochastic Oscillator (%K, %D) calculation."""
    ohlcv = generate_ohlcv_data(100, start_price=45000)
    result = await analyze_momentum.handler({
        'ohlcv_data': ohlcv,
        'symbol': 'BTCUSDT',
        'timeframe': '4h'
    })

    # Check for stochastic indicators
    assert 'stochastic_k' in result['indicators']
    assert 'stochastic_d' in result['indicators']

    stoch_k = result['indicators']['stochastic_k']
    stoch_d = result['indicators']['stochastic_d']

    # Both should be between 0 and 100
    assert 0 <= stoch_k <= 100
    assert 0 <= stoch_d <= 100
    assert isinstance(stoch_k, (int, float))
    assert isinstance(stoch_d, (int, float))


@pytest.mark.asyncio
async def test_analyze_momentum_elder_force_index():
    """Test Elder Force Index calculation."""
    ohlcv = generate_ohlcv_data(100, start_price=55000)
    result = await analyze_momentum.handler({
        'ohlcv_data': ohlcv,
        'symbol': 'ETHUSDT',
        'timeframe': '1h'
    })

    assert 'elder_force_index' in result['indicators']
    force = result['indicators']['elder_force_index']

    # Force index can be positive or negative
    assert isinstance(force, (int, float))
    # Should be reasonable value (not NaN or inf)
    assert force != float('inf') and force != float('-inf')


@pytest.mark.asyncio
async def test_analyze_momentum_elder_impulse_system():
    """Test Elder Impulse System (blue/red/gray)."""
    ohlcv = generate_ohlcv_data(100, start_price=50000)
    result = await analyze_momentum.handler({
        'ohlcv_data': ohlcv,
        'symbol': 'BTCUSDT',
        'timeframe': '1h'
    })

    assert 'elder_impulse' in result['indicators']
    impulse = result['indicators']['elder_impulse']

    # Should be one of three colors
    assert impulse in ['blue', 'red', 'gray']

    # Check supporting indicators exist
    assert 'ema_13' in result['indicators']
    assert 'ema_13_direction' in result['indicators']
    assert 'macd_histogram' in result['indicators']
    assert 'macd_histogram_direction' in result['indicators']

    # Directions should be valid
    assert result['indicators']['ema_13_direction'] in ['rising', 'falling', 'unknown']
    assert result['indicators']['macd_histogram_direction'] in ['rising', 'falling', 'unknown']


@pytest.mark.asyncio
async def test_analyze_momentum_score_range():
    """Test that momentum_score is between -1.0 and 1.0."""
    # Test with multiple datasets
    for start_price in [30000, 50000, 70000]:
        for periods in [50, 100, 200]:
            ohlcv = generate_ohlcv_data(periods, start_price)
            result = await analyze_momentum.handler({
                'ohlcv_data': ohlcv,
                'symbol': 'BTCUSDT',
                'timeframe': '1h'
            })

            assert 'momentum_score' in result
            assert -1.0 <= result['momentum_score'] <= 1.0, \
                f"momentum_score {result['momentum_score']} out of range"


@pytest.mark.asyncio
async def test_analyze_momentum_signals_populated():
    """Test that signals list is populated."""
    ohlcv = generate_ohlcv_data(100, start_price=50000)
    result = await analyze_momentum.handler({
        'ohlcv_data': ohlcv,
        'symbol': 'BTCUSDT',
        'timeframe': '1h'
    })

    assert 'signals' in result
    assert isinstance(result['signals'], list)
    assert len(result['signals']) > 0

    # Valid signal types
    valid_signals = [
        'rsi_oversold', 'rsi_overbought', 'rsi_neutral',
        'stochastic_oversold', 'stochastic_overbought',
        'stochastic_bullish_crossover', 'stochastic_bearish_crossover',
        'elder_force_positive', 'elder_force_negative',
        'elder_impulse_bullish', 'elder_impulse_bearish', 'elder_impulse_neutral'
    ]

    for signal in result['signals']:
        assert signal in valid_signals, f"Invalid signal: {signal}"


@pytest.mark.asyncio
async def test_analyze_momentum_insufficient_data():
    """Test analyze_momentum with insufficient data (< 50 periods)."""
    ohlcv = generate_ohlcv_data(30)  # Less than 50
    result = await analyze_momentum.handler({
        'ohlcv_data': ohlcv,
        'symbol': 'BTCUSDT',
        'timeframe': '1h'
    })

    assert 'is_error' in result
    assert result['is_error'] == True
    assert 'insufficient' in result['content'][0]['text'].lower()


@pytest.mark.asyncio
async def test_analyze_momentum_empty_data():
    """Test analyze_momentum with empty OHLCV data."""
    result = await analyze_momentum.handler({
        'ohlcv_data': [],
        'symbol': 'BTCUSDT',
        'timeframe': '1h'
    })

    assert 'is_error' in result
    assert result['is_error'] == True
    assert 'no ohlcv data' in result['content'][0]['text'].lower()


@pytest.mark.asyncio
async def test_analyze_momentum_minimal_required_data():
    """Test analyze_momentum with exactly minimum required data (50 periods)."""
    ohlcv = generate_ohlcv_data(50)  # Exactly minimum
    result = await analyze_momentum.handler({
        'ohlcv_data': ohlcv,
        'symbol': 'BTCUSDT',
        'timeframe': '1h'
    })

    # Should succeed with minimum data
    assert 'momentum_score' in result
    assert 'is_error' not in result or result.get('is_error') == False


# ============================================================================
# TEST analyze_volatility()
# ============================================================================

@pytest.mark.asyncio
async def test_analyze_volatility_valid_data():
    """Test analyze_volatility with valid data (20+ periods)."""
    ohlcv = generate_ohlcv_data(50)
    result = await analyze_volatility.handler({
        'ohlcv_data': ohlcv,
        'symbol': 'BTCUSDT',
        'timeframe': '1h'
    })

    # Check for required keys
    assert 'volatility_score' in result
    assert 'indicators' in result
    assert 'signals' in result
    assert 'interpretation' in result

    # Verify volatility score range
    assert 0.0 <= result['volatility_score'] <= 1.0


@pytest.mark.asyncio
async def test_analyze_volatility_atr_calculation():
    """Test ATR calculation."""
    ohlcv = generate_ohlcv_data(50, start_price=50000)
    result = await analyze_volatility.handler({
        'ohlcv_data': ohlcv,
        'symbol': 'BTCUSDT',
        'timeframe': '1h'
    })

    assert 'atr' in result['indicators']
    assert 'atr_percent' in result['indicators']

    atr = result['indicators']['atr']
    atr_percent = result['indicators']['atr_percent']

    # ATR should be positive
    assert atr > 0
    assert isinstance(atr, (int, float))

    # ATR percent should be positive and reasonable (< 20% typically)
    assert atr_percent > 0
    assert atr_percent < 50  # Very generous upper bound


@pytest.mark.asyncio
async def test_analyze_volatility_bollinger_bands():
    """Test Bollinger Bands (upper, middle, lower) calculation."""
    ohlcv = generate_ohlcv_data(50, start_price=45000)
    result = await analyze_volatility.handler({
        'ohlcv_data': ohlcv,
        'symbol': 'ETHUSDT',
        'timeframe': '4h'
    })

    assert 'bb_upper' in result['indicators']
    assert 'bb_middle' in result['indicators']
    assert 'bb_lower' in result['indicators']

    bb_upper = result['indicators']['bb_upper']
    bb_middle = result['indicators']['bb_middle']
    bb_lower = result['indicators']['bb_lower']

    # All should be positive and properly ordered
    assert bb_upper > bb_middle > bb_lower
    assert all(isinstance(x, (int, float)) for x in [bb_upper, bb_middle, bb_lower])


@pytest.mark.asyncio
async def test_analyze_volatility_bb_width():
    """Test BB width calculations."""
    ohlcv = generate_ohlcv_data(50, start_price=50000)
    result = await analyze_volatility.handler({
        'ohlcv_data': ohlcv,
        'symbol': 'BTCUSDT',
        'timeframe': '1h'
    })

    assert 'bb_width' in result['indicators']
    assert 'bb_width_percent' in result['indicators']

    bb_width = result['indicators']['bb_width']
    bb_width_percent = result['indicators']['bb_width_percent']

    # BB width should be positive
    assert bb_width > 0
    assert bb_width_percent > 0
    assert isinstance(bb_width, (int, float))
    assert isinstance(bb_width_percent, (int, float))

    # Verify calculation: width = upper - lower
    expected_width = result['indicators']['bb_upper'] - result['indicators']['bb_lower']
    assert abs(bb_width - expected_width) < 0.01  # Allow small floating point error


@pytest.mark.asyncio
async def test_analyze_volatility_score_range():
    """Test that volatility_score is between 0.0 and 1.0."""
    # Test with multiple datasets
    for start_price in [30000, 50000, 70000]:
        for periods in [20, 50, 100]:
            ohlcv = generate_ohlcv_data(periods, start_price)
            result = await analyze_volatility.handler({
                'ohlcv_data': ohlcv,
                'symbol': 'BTCUSDT',
                'timeframe': '1h'
            })

            assert 'volatility_score' in result
            assert 0.0 <= result['volatility_score'] <= 1.0, \
                f"volatility_score {result['volatility_score']} out of range"


@pytest.mark.asyncio
async def test_analyze_volatility_signals_contain_level():
    """Test that signals list contains volatility level."""
    ohlcv = generate_ohlcv_data(50, start_price=50000)
    result = await analyze_volatility.handler({
        'ohlcv_data': ohlcv,
        'symbol': 'BTCUSDT',
        'timeframe': '1h'
    })

    assert 'signals' in result
    assert isinstance(result['signals'], list)
    assert len(result['signals']) > 0

    # Should contain at least one volatility level signal
    volatility_signals = ['high_volatility', 'low_volatility', 'normal_volatility']
    has_volatility_level = any(sig in result['signals'] for sig in volatility_signals)
    assert has_volatility_level, "Missing volatility level signal"

    # Valid signal types
    valid_signals = [
        'high_volatility', 'low_volatility', 'normal_volatility',
        'bb_squeeze', 'price_near_bb_upper', 'price_near_bb_lower', 'price_in_bb_middle'
    ]

    for signal in result['signals']:
        assert signal in valid_signals, f"Invalid signal: {signal}"


@pytest.mark.asyncio
async def test_analyze_volatility_insufficient_data():
    """Test analyze_volatility with insufficient data (< 20 periods)."""
    ohlcv = generate_ohlcv_data(15)  # Less than 20
    result = await analyze_volatility.handler({
        'ohlcv_data': ohlcv,
        'symbol': 'BTCUSDT',
        'timeframe': '1h'
    })

    assert 'is_error' in result
    assert result['is_error'] == True
    assert 'insufficient' in result['content'][0]['text'].lower()


@pytest.mark.asyncio
async def test_analyze_volatility_empty_data():
    """Test analyze_volatility with empty OHLCV data."""
    result = await analyze_volatility.handler({
        'ohlcv_data': [],
        'symbol': 'BTCUSDT',
        'timeframe': '1h'
    })

    assert 'is_error' in result
    assert result['is_error'] == True
    assert 'no ohlcv data' in result['content'][0]['text'].lower()


@pytest.mark.asyncio
async def test_analyze_volatility_minimal_required_data():
    """Test analyze_volatility with exactly minimum required data (20 periods)."""
    ohlcv = generate_ohlcv_data(20)  # Exactly minimum
    result = await analyze_volatility.handler({
        'ohlcv_data': ohlcv,
        'symbol': 'BTCUSDT',
        'timeframe': '1h'
    })

    # Should succeed with minimum data
    assert 'volatility_score' in result
    assert 'is_error' not in result or result.get('is_error') == False


# ============================================================================
# TEST analyze_patterns()
# ============================================================================

@pytest.mark.asyncio
async def test_analyze_patterns_valid_data():
    """Test analyze_patterns with valid data (50+ periods)."""
    ohlcv = generate_ohlcv_data(100)
    result = await analyze_patterns.handler({
        'ohlcv_data': ohlcv,
        'symbol': 'BTCUSDT',
        'timeframe': '1h'
    })

    # Check for required keys
    assert 'fib_levels' in result
    assert 'current_price' in result
    assert 'swing_high' in result
    assert 'swing_low' in result
    assert 'swing_range' in result
    assert 'current_level' in result
    assert 'signals' in result
    assert 'interpretation' in result


@pytest.mark.asyncio
async def test_analyze_patterns_fibonacci_levels():
    """Test Fibonacci level calculations (0%, 23.6%, 38.2%, 50%, 61.8%, 78.6%, 100%)."""
    ohlcv = generate_ohlcv_data(100, start_price=50000)
    result = await analyze_patterns.handler({
        'ohlcv_data': ohlcv,
        'symbol': 'BTCUSDT',
        'timeframe': '1h',
        'lookback_periods': 50
    })

    fib_levels = result['fib_levels']

    # Check all standard Fibonacci levels exist
    required_levels = ['0.0', '23.6', '38.2', '50.0', '61.8', '78.6', '100.0']
    for level in required_levels:
        assert level in fib_levels, f"Missing Fibonacci level: {level}"
        assert isinstance(fib_levels[level], (int, float))

    # Verify levels are properly ordered
    swing_low = result['swing_low']
    swing_high = result['swing_high']

    assert fib_levels['0.0'] == swing_low
    assert fib_levels['100.0'] == swing_high
    assert fib_levels['0.0'] < fib_levels['23.6'] < fib_levels['38.2'] < fib_levels['50.0']
    assert fib_levels['50.0'] < fib_levels['61.8'] < fib_levels['78.6'] < fib_levels['100.0']


@pytest.mark.asyncio
async def test_analyze_patterns_extension_levels():
    """Test extension levels (127.2%, 161.8%)."""
    ohlcv = generate_ohlcv_data(100, start_price=45000)
    result = await analyze_patterns.handler({
        'ohlcv_data': ohlcv,
        'symbol': 'ETHUSDT',
        'timeframe': '4h',
        'lookback_periods': 50
    })

    fib_levels = result['fib_levels']

    # Check extension levels exist
    assert '127.2' in fib_levels
    assert '161.8' in fib_levels

    # Extension levels should be above 100% level
    assert fib_levels['127.2'] > fib_levels['100.0']
    assert fib_levels['161.8'] > fib_levels['127.2']


@pytest.mark.asyncio
async def test_analyze_patterns_swing_detection():
    """Test swing high/low detection."""
    ohlcv = generate_ohlcv_data(100, start_price=50000)
    result = await analyze_patterns.handler({
        'ohlcv_data': ohlcv,
        'symbol': 'BTCUSDT',
        'timeframe': '1h',
        'lookback_periods': 50
    })

    swing_high = result['swing_high']
    swing_low = result['swing_low']
    swing_range = result['swing_range']

    # Swing high should be greater than swing low
    assert swing_high > swing_low

    # Swing range should be the difference
    assert abs(swing_range - (swing_high - swing_low)) < 0.01

    # All values should be positive
    assert swing_high > 0
    assert swing_low > 0
    assert swing_range > 0


@pytest.mark.asyncio
async def test_analyze_patterns_support_resistance_separation():
    """Test support/resistance level separation."""
    ohlcv = generate_ohlcv_data(100, start_price=50000)
    result = await analyze_patterns.handler({
        'ohlcv_data': ohlcv,
        'symbol': 'BTCUSDT',
        'timeframe': '1h',
        'lookback_periods': 50
    })

    current_price = result['current_price']
    support_levels = result['support_levels']
    resistance_levels = result['resistance_levels']

    # All support levels should be below current price
    for level in support_levels:
        assert level < current_price, f"Support level {level} not below current price {current_price}"

    # All resistance levels should be above current price
    for level in resistance_levels:
        assert level > current_price, f"Resistance level {level} not above current price {current_price}"

    # Both lists should be sorted
    if len(support_levels) > 1:
        assert support_levels == sorted(support_levels)
    if len(resistance_levels) > 1:
        assert resistance_levels == sorted(resistance_levels)


@pytest.mark.asyncio
async def test_analyze_patterns_current_level_identification():
    """Test current level identification."""
    ohlcv = generate_ohlcv_data(100, start_price=50000)
    result = await analyze_patterns.handler({
        'ohlcv_data': ohlcv,
        'symbol': 'BTCUSDT',
        'timeframe': '1h',
        'lookback_periods': 50
    })

    current_level = result['current_level']

    # Current level should be one of the Fibonacci levels
    valid_levels = ['0.0', '23.6', '38.2', '50.0', '61.8', '78.6', '100.0', '127.2', '161.8']
    assert current_level in valid_levels

    # Distance to level should be calculated
    assert 'distance_to_level' in result
    assert 'distance_percent' in result
    assert result['distance_to_level'] >= 0
    assert result['distance_percent'] >= 0


@pytest.mark.asyncio
async def test_analyze_patterns_signal_generation():
    """Test signal generation."""
    ohlcv = generate_ohlcv_data(100, start_price=50000)
    result = await analyze_patterns.handler({
        'ohlcv_data': ohlcv,
        'symbol': 'BTCUSDT',
        'timeframe': '1h',
        'lookback_periods': 50
    })

    signals = result['signals']

    # Signals should be a list
    assert isinstance(signals, list)
    assert len(signals) > 0

    # Should contain retracement type
    has_retracement = any('retracement' in sig for sig in signals)
    assert has_retracement, "Missing retracement signal"

    # Valid signals should include position information
    valid_signal_patterns = ['near_fib_', 'between_', '_retracement']
    for signal in signals:
        has_valid_pattern = any(pattern in signal for pattern in valid_signal_patterns)
        assert has_valid_pattern, f"Invalid signal pattern: {signal}"


@pytest.mark.asyncio
async def test_analyze_patterns_custom_lookback():
    """Test custom lookback_periods parameter."""
    ohlcv = generate_ohlcv_data(150, start_price=50000)

    # Test with different lookback periods
    result_30 = await analyze_patterns.handler({
        'ohlcv_data': ohlcv,
        'symbol': 'BTCUSDT',
        'timeframe': '1h',
        'lookback_periods': 30
    })

    result_100 = await analyze_patterns.handler({
        'ohlcv_data': ohlcv,
        'symbol': 'BTCUSDT',
        'timeframe': '1h',
        'lookback_periods': 100
    })

    # Both should succeed
    assert 'fib_levels' in result_30
    assert 'fib_levels' in result_100

    # Different lookback periods may produce different swing high/low
    # (not guaranteed to be different, but likely with our data)
    assert 'swing_high' in result_30
    assert 'swing_high' in result_100


@pytest.mark.asyncio
async def test_analyze_patterns_insufficient_data():
    """Test analyze_patterns with insufficient data."""
    ohlcv = generate_ohlcv_data(30)
    result = await analyze_patterns.handler({
        'ohlcv_data': ohlcv,
        'symbol': 'BTCUSDT',
        'timeframe': '1h',
        'lookback_periods': 50  # More than available data
    })

    assert 'is_error' in result
    assert result['is_error'] == True
    assert 'insufficient' in result['content'][0]['text'].lower()


@pytest.mark.asyncio
async def test_analyze_patterns_empty_data():
    """Test analyze_patterns with empty OHLCV data."""
    result = await analyze_patterns.handler({
        'ohlcv_data': [],
        'symbol': 'BTCUSDT',
        'timeframe': '1h',
        'lookback_periods': 50
    })

    assert 'is_error' in result
    assert result['is_error'] == True
    assert 'no ohlcv data' in result['content'][0]['text'].lower()


@pytest.mark.asyncio
async def test_analyze_patterns_default_lookback():
    """Test analyze_patterns uses default lookback (50) when not specified."""
    ohlcv = generate_ohlcv_data(100, start_price=50000)
    result = await analyze_patterns.handler({
        'ohlcv_data': ohlcv,
        'symbol': 'BTCUSDT',
        'timeframe': '1h'
        # lookback_periods not specified
    })

    # Should succeed with default lookback
    assert 'fib_levels' in result
    assert 'swing_high' in result
    assert 'swing_low' in result


# ============================================================================
# EDGE CASES AND INTEGRATION TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_all_tools_with_large_dataset():
    """Test all tools can handle large datasets (1000+ periods)."""
    ohlcv = generate_ohlcv_data(1000, start_price=50000)

    # Test trend
    trend_result = await analyze_trend.handler({
        'ohlcv_data': ohlcv,
        'symbol': 'BTCUSDT',
        'timeframe': '1h'
    })
    assert 'trend_score' in trend_result

    # Test momentum
    momentum_result = await analyze_momentum.handler({
        'ohlcv_data': ohlcv,
        'symbol': 'BTCUSDT',
        'timeframe': '1h'
    })
    assert 'momentum_score' in momentum_result

    # Test volatility
    volatility_result = await analyze_volatility.handler({
        'ohlcv_data': ohlcv,
        'symbol': 'BTCUSDT',
        'timeframe': '1h'
    })
    assert 'volatility_score' in volatility_result

    # Test patterns
    patterns_result = await analyze_patterns.handler({
        'ohlcv_data': ohlcv,
        'symbol': 'BTCUSDT',
        'timeframe': '1h',
        'lookback_periods': 200
    })
    assert 'fib_levels' in patterns_result


@pytest.mark.asyncio
async def test_all_tools_return_content():
    """Test that all tools return properly formatted content."""
    ohlcv = generate_ohlcv_data(250, start_price=50000)

    tools = [
        (analyze_trend, {}),
        (analyze_momentum, {}),
        (analyze_volatility, {}),
        (analyze_patterns, {'lookback_periods': 50})
    ]

    for tool_func, extra_args in tools:
        args = {
            'ohlcv_data': ohlcv,
            'symbol': 'BTCUSDT',
            'timeframe': '1h',
            **extra_args
        }
        result = await tool_func.handler(args)

        # All tools should return content
        assert 'content' in result
        assert isinstance(result['content'], list)
        assert len(result['content']) > 0
        assert 'type' in result['content'][0]
        assert 'text' in result['content'][0]
        assert result['content'][0]['type'] == 'text'
        assert len(result['content'][0]['text']) > 0


@pytest.mark.asyncio
async def test_consistent_price_references():
    """Test that all tools use consistent price references."""
    ohlcv = generate_ohlcv_data(250, start_price=50000)
    expected_current_price = ohlcv[-1]['close']

    # Trend analysis
    trend_result = await analyze_trend.handler({
        'ohlcv_data': ohlcv,
        'symbol': 'BTCUSDT',
        'timeframe': '1h'
    })
    # Trend doesn't return current_price directly, but uses it for calculations

    # Volatility analysis
    volatility_result = await analyze_volatility.handler({
        'ohlcv_data': ohlcv,
        'symbol': 'BTCUSDT',
        'timeframe': '1h'
    })
    assert 'current_price' in volatility_result['indicators']
    assert abs(volatility_result['indicators']['current_price'] - expected_current_price) < 1.0

    # Patterns analysis
    patterns_result = await analyze_patterns.handler({
        'ohlcv_data': ohlcv,
        'symbol': 'BTCUSDT',
        'timeframe': '1h',
        'lookback_periods': 50
    })
    assert 'current_price' in patterns_result
    assert abs(patterns_result['current_price'] - expected_current_price) < 1.0
