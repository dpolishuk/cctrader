import pytest
from src.agent.scanner.confidence import ConfidenceCalculator

def test_calculate_technical_score():
    """Test technical analysis score calculation."""
    calculator = ConfidenceCalculator()

    # Mock technical data for 5 timeframes
    technical_data = {
        '4h': {'rsi': 55, 'macd_signal': 'bullish_cross', 'bb_position': 'upper', 'volume_ratio': 2.1},
        '1h': {'rsi': 62, 'macd_signal': 'histogram_positive', 'bb_position': 'upper', 'volume_ratio': 2.3},
        '15m': {'rsi': 58, 'macd_signal': 'histogram_positive', 'bb_position': 'middle', 'volume_ratio': 1.8},
        '5m': {'rsi': 65, 'macd_signal': 'histogram_positive', 'bb_position': 'middle', 'volume_ratio': 1.2},
        '1m': {'rsi': 70, 'macd_signal': 'histogram_positive', 'bb_position': 'middle', 'volume_ratio': 2.0},
    }

    score = calculator.calculate_technical_score(technical_data)

    assert 0 <= score <= 40
    assert score >= 30  # Strong alignment should score high

def test_calculate_sentiment_score_positive():
    """Test sentiment score for positive catalyst."""
    calculator = ConfidenceCalculator()

    sentiment_data = {
        'classification': 'STRONG_POSITIVE',
        'summary': 'Major partnership announced',
    }

    score = calculator.calculate_sentiment_score(sentiment_data, direction='LONG')

    assert 25 <= score <= 30

def test_calculate_sentiment_score_inverted_for_short():
    """Test sentiment score inverted for SHORT positions."""
    calculator = ConfidenceCalculator()

    sentiment_data = {
        'classification': 'STRONG_NEGATIVE',
        'summary': 'Hack reported',
    }

    score = calculator.calculate_sentiment_score(sentiment_data, direction='SHORT')

    assert 25 <= score <= 30  # Negative news good for shorts

def test_calculate_liquidity_score():
    """Test liquidity score calculation."""
    calculator = ConfidenceCalculator()

    liquidity_data = {
        'volume_ratio': 2.3,  # 2.3x average → 20 points
        'bid_ask_spread_pct': 0.03,  # <0.05% → +5 bonus
        'order_book_depth_usd': 680000,  # >500k → +3 bonus
    }

    score = calculator.calculate_liquidity_score(liquidity_data)

    assert score == 20  # Base 20, bonuses included but capped

def test_calculate_correlation_score():
    """Test BTC correlation score calculation."""
    calculator = ConfidenceCalculator()

    correlation_data = {
        'btc_change_1h': 2.1,
        'symbol_change_1h': 7.2,
    }

    score = calculator.calculate_correlation_score(correlation_data)

    # Moving with BTC uptrend + outperforming by >3% = 10 points
    assert score == 10

def test_calculate_final_confidence():
    """Test final confidence score calculation."""
    calculator = ConfidenceCalculator()

    score = calculator.calculate_final_confidence(
        technical=34,
        sentiment=25,
        liquidity=20,
        correlation=10
    )

    assert score == 89
    assert 0 <= score <= 100
