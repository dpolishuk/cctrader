"""Comprehensive integration tests for enhanced generate_trading_signal() function."""
import pytest
from src.agent.tools.signals import generate_trading_signal, calculate_pattern_score


class TestPatternScoreCalculation:
    """Test the calculate_pattern_score helper function."""

    def test_near_swing_low_0_percent(self):
        """Test score at 0% Fibonacci level (strong support)."""
        pattern_data = {"current_level": "0.0"}
        score = calculate_pattern_score(pattern_data)
        assert score == 0.7, "0% level should return 0.7 (strong bullish)"

    def test_near_swing_low_23_6_percent(self):
        """Test score at 23.6% Fibonacci level (strong support)."""
        pattern_data = {"current_level": "23.6"}
        score = calculate_pattern_score(pattern_data)
        assert score == 0.7, "23.6% level should return 0.7 (strong bullish)"

    def test_moderate_support_38_2_percent(self):
        """Test score at 38.2% Fibonacci level (moderate support)."""
        pattern_data = {"current_level": "38.2"}
        score = calculate_pattern_score(pattern_data)
        assert score == 0.3, "38.2% level should return 0.3 (moderate bullish)"

    def test_neutral_50_percent(self):
        """Test score at 50% Fibonacci level (neutral)."""
        pattern_data = {"current_level": "50.0"}
        score = calculate_pattern_score(pattern_data)
        assert score == 0.0, "50% level should return 0.0 (neutral)"

    def test_moderate_resistance_61_8_percent(self):
        """Test score at 61.8% Fibonacci level (moderate resistance)."""
        pattern_data = {"current_level": "61.8"}
        score = calculate_pattern_score(pattern_data)
        assert score == -0.3, "61.8% level should return -0.3 (moderate bearish)"

    def test_near_swing_high_78_6_percent(self):
        """Test score at 78.6% Fibonacci level (strong resistance)."""
        pattern_data = {"current_level": "78.6"}
        score = calculate_pattern_score(pattern_data)
        assert score == -0.7, "78.6% level should return -0.7 (strong bearish)"

    def test_near_swing_high_100_percent(self):
        """Test score at 100% Fibonacci level (strong resistance)."""
        pattern_data = {"current_level": "100.0"}
        score = calculate_pattern_score(pattern_data)
        assert score == -0.7, "100% level should return -0.7 (strong bearish)"

    def test_empty_pattern_data(self):
        """Test with empty pattern data."""
        score = calculate_pattern_score({})
        assert score == 0.0, "Empty pattern data should return 0.0"

    def test_none_pattern_data(self):
        """Test with None pattern data."""
        score = calculate_pattern_score(None)
        assert score == 0.0, "None pattern data should return 0.0"

    def test_invalid_level_format(self):
        """Test with invalid level format."""
        pattern_data = {"current_level": "invalid"}
        score = calculate_pattern_score(pattern_data)
        assert score == 0.0, "Invalid level format should return 0.0"


class TestBackwardCompatibility:
    """Test backward compatibility with existing calls."""

    @pytest.mark.asyncio
    async def test_basic_call_without_new_indicators(self):
        """Test existing calls still work without new indicators."""
        result = await generate_trading_signal.handler({
            'symbol': 'BTCUSDT',
            'technical_data': {
                'indicators': {
                    'rsi': 55.0,
                    'macd': 100.0,
                    'macd_signal': 80.0,
                    'macd_hist': 20.0
                },
                'interpretation': {
                    'rsi_status': 'Neutral',
                    'macd_status': 'Bullish',
                    'bb_status': 'Near Middle'
                }
            },
            'sentiment_data': {
                'sentiment_score': 0.3
            },
            'current_price': 45000.0
        })

        assert 'signal' in result
        assert result['signal']['type'] in ['STRONG_BUY', 'BUY', 'HOLD', 'SELL', 'STRONG_SELL']
        assert 'confidence' in result['signal']
        assert 0.0 <= result['signal']['confidence'] <= 1.0
        assert 'content' in result
        assert len(result['content']) > 0

    @pytest.mark.asyncio
    async def test_signal_generation_works(self):
        """Verify signal generation works with basic data."""
        result = await generate_trading_signal.handler({
            'symbol': 'ETHUSDT',
            'technical_data': {
                'indicators': {
                    'rsi': 45.0,
                    'macd_hist': -10.0
                },
                'interpretation': {
                    'rsi_status': 'Neutral',
                    'macd_status': 'Bearish'
                }
            },
            'sentiment_data': {
                'sentiment_score': -0.2
            },
            'current_price': 3000.0
        })

        assert result['signal']['type'] in ['HOLD', 'SELL']
        assert 'classic_score' in result['signal']
        assert 'technical_score' in result['signal']
        assert 'sentiment_score' in result['signal']

    @pytest.mark.asyncio
    async def test_confidence_calculation_works(self):
        """Verify confidence calculation works correctly."""
        result = await generate_trading_signal.handler({
            'symbol': 'BTCUSDT',
            'technical_data': {
                'indicators': {
                    'rsi': 75.0,  # Overbought
                    'macd_hist': -50.0  # Bearish
                },
                'interpretation': {
                    'rsi_status': 'Overbought',
                    'macd_status': 'Bearish',
                    'bb_status': 'Near Upper'
                }
            },
            'sentiment_data': {
                'sentiment_score': -0.5  # Negative
            },
            'current_price': 45000.0
        })

        # Should be SELL or STRONG_SELL with reasonable confidence
        assert result['signal']['type'] in ['SELL', 'STRONG_SELL']
        assert result['signal']['confidence'] > 0.3


class TestFullIntegration:
    """Test with all indicators provided."""

    @pytest.mark.asyncio
    async def test_all_indicators_bullish(self):
        """Test with all indicators showing bullish signals."""
        result = await generate_trading_signal.handler({
            'symbol': 'BTCUSDT',
            'technical_data': {
                'indicators': {'rsi': 45.0, 'macd_hist': 25.0},
                'interpretation': {
                    'rsi_status': 'Neutral',
                    'macd_status': 'Bullish',
                    'bb_status': 'Near Lower'
                }
            },
            'trend_data': {
                'trend_score': 0.8  # Strong uptrend
            },
            'momentum_data': {
                'momentum_score': 0.7  # Bullish momentum
            },
            'volatility_data': {
                'volatility_score': 0.4  # Low volatility
            },
            'pattern_data': {
                'current_level': '23.6'  # Near support
            },
            'sentiment_data': {
                'sentiment_score': 0.5  # Positive sentiment
            },
            'current_price': 45000.0
        })

        assert 'signal' in result
        assert result['signal']['type'] in ['STRONG_BUY', 'BUY']
        assert 'trend_score' in result['signal']
        assert 'momentum_score' in result['signal']
        assert 'pattern_score' in result['signal']
        assert 'combined_score' in result['signal']

        # Verify score breakdown is included
        signal = result['signal']
        assert abs(signal['trend_score'] - 0.6) < 0.01  # (0.8-0.5)*2 = 0.6
        assert signal['momentum_score'] == 0.7
        assert signal['pattern_score'] == 0.7  # Near swing low
        assert signal['combined_score'] > 0.3  # Should be positive

    @pytest.mark.asyncio
    async def test_all_indicators_bearish(self):
        """Test with all indicators showing bearish signals."""
        result = await generate_trading_signal.handler({
            'symbol': 'BTCUSDT',
            'technical_data': {
                'indicators': {'rsi': 75.0, 'macd_hist': -30.0},
                'interpretation': {
                    'rsi_status': 'Overbought',
                    'macd_status': 'Bearish',
                    'bb_status': 'Near Upper'
                }
            },
            'trend_data': {
                'trend_score': 0.2  # Strong downtrend
            },
            'momentum_data': {
                'momentum_score': -0.8  # Bearish momentum
            },
            'volatility_data': {
                'volatility_score': 0.5  # Normal volatility
            },
            'pattern_data': {
                'current_level': '85.0'  # Near resistance
            },
            'sentiment_data': {
                'sentiment_score': -0.6  # Negative sentiment
            },
            'current_price': 45000.0
        })

        assert result['signal']['type'] in ['STRONG_SELL', 'SELL']
        assert result['signal']['combined_score'] < -0.2  # Should be negative

    @pytest.mark.asyncio
    async def test_combined_score_calculation(self):
        """Verify combined score is calculated correctly (60% tech, 40% sentiment)."""
        result = await generate_trading_signal.handler({
            'symbol': 'BTCUSDT',
            'technical_data': {
                'indicators': {'rsi': 50.0, 'macd_hist': 0.0},
                'interpretation': {
                    'rsi_status': 'Neutral',
                    'macd_status': 'Neutral'
                }
            },
            'trend_data': {'trend_score': 0.7},  # normalized to 0.4
            'momentum_data': {'momentum_score': 0.5},
            'volatility_data': {'volatility_score': 0.5},
            'pattern_data': {'current_level': '50.0'},  # neutral = 0.0
            'sentiment_data': {'sentiment_score': 0.5},
            'current_price': 45000.0
        })

        signal = result['signal']
        # Technical score = classic*0.3 + trend*0.25 + momentum*0.25 + pattern*0.10
        # Combined = tech*0.6 + sentiment*0.4
        expected_tech = signal['technical_score']
        expected_combined = expected_tech * 0.6 + 0.5 * 0.4

        assert abs(signal['combined_score'] - expected_combined) < 0.01

    @pytest.mark.asyncio
    async def test_all_component_scores_in_output(self):
        """Verify all component scores are included in output."""
        result = await generate_trading_signal.handler({
            'symbol': 'BTCUSDT',
            'technical_data': {
                'indicators': {'rsi': 55.0, 'macd_hist': 10.0},
                'interpretation': {'rsi_status': 'Neutral', 'macd_status': 'Bullish'}
            },
            'trend_data': {'trend_score': 0.6},
            'momentum_data': {'momentum_score': 0.4},
            'volatility_data': {'volatility_score': 0.5},
            'pattern_data': {'current_level': '40.0'},
            'sentiment_data': {'sentiment_score': 0.2},
            'current_price': 45000.0
        })

        signal = result['signal']
        assert 'classic_score' in signal
        assert 'trend_score' in signal
        assert 'momentum_score' in signal
        assert 'pattern_score' in signal
        assert 'technical_score' in signal
        assert 'sentiment_score' in signal
        assert 'combined_score' in signal
        assert 'volatility_adjustment' in signal

    @pytest.mark.asyncio
    async def test_signal_reasoning_includes_all_indicators(self):
        """Verify signal reasoning includes all indicators when provided."""
        result = await generate_trading_signal.handler({
            'symbol': 'BTCUSDT',
            'technical_data': {
                'indicators': {'rsi': 75.0, 'macd_hist': 20.0},
                'interpretation': {'rsi_status': 'Overbought', 'macd_status': 'Bullish'}
            },
            'trend_data': {'trend_score': 0.8},  # Strong uptrend
            'momentum_data': {'momentum_score': 0.6},  # Bullish momentum
            'volatility_data': {'volatility_score': 0.8},  # High volatility
            'pattern_data': {'current_level': '38.2'},
            'sentiment_data': {'sentiment_score': 0.5},  # Positive sentiment
            'current_price': 45000.0
        })

        reason = result['signal']['reason']
        assert 'RSI' in reason or 'Overbought' in reason
        assert 'MACD' in reason or 'Bullish' in reason
        assert 'uptrend' in reason or 'EMA' in reason or 'Ichimoku' in reason
        assert 'momentum' in reason or 'Stochastic' in reason or 'Elder' in reason
        assert 'volatility' in reason.lower()
        assert 'Fibonacci' in reason or '38.2' in reason
        assert 'sentiment' in reason.lower()


class TestSignalThresholds:
    """Test signal type thresholds."""

    @pytest.mark.asyncio
    async def test_strong_bullish_signal(self):
        """Test STRONG_BUY signal (combined_score > 0.5)."""
        result = await generate_trading_signal.handler({
            'symbol': 'BTCUSDT',
            'technical_data': {
                'indicators': {'rsi': 30.0, 'macd_hist': 50.0},
                'interpretation': {'rsi_status': 'Oversold', 'macd_status': 'Bullish'}
            },
            'trend_data': {'trend_score': 0.9},
            'momentum_data': {'momentum_score': 0.8},
            'pattern_data': {'current_level': '10.0'},
            'sentiment_data': {'sentiment_score': 0.7},
            'current_price': 45000.0
        })

        assert result['signal']['type'] == 'STRONG_BUY'
        assert result['signal']['combined_score'] > 0.5

    @pytest.mark.asyncio
    async def test_moderate_bullish_signal(self):
        """Test BUY signal (0.2 < combined_score < 0.5)."""
        result = await generate_trading_signal.handler({
            'symbol': 'BTCUSDT',
            'technical_data': {
                'indicators': {'rsi': 45.0, 'macd_hist': 15.0},
                'interpretation': {'rsi_status': 'Neutral', 'macd_status': 'Bullish'}
            },
            'trend_data': {'trend_score': 0.6},
            'momentum_data': {'momentum_score': 0.3},
            'pattern_data': {'current_level': '40.0'},
            'sentiment_data': {'sentiment_score': 0.3},
            'current_price': 45000.0
        })

        assert result['signal']['type'] == 'BUY'
        assert 0.2 < result['signal']['combined_score'] <= 0.5

    @pytest.mark.asyncio
    async def test_neutral_signal(self):
        """Test HOLD signal (-0.2 < combined_score < 0.2)."""
        result = await generate_trading_signal.handler({
            'symbol': 'BTCUSDT',
            'technical_data': {
                'indicators': {'rsi': 50.0, 'macd_hist': 0.0},
                'interpretation': {'rsi_status': 'Neutral', 'macd_status': 'Neutral'}
            },
            'trend_data': {'trend_score': 0.5},
            'momentum_data': {'momentum_score': 0.0},
            'pattern_data': {'current_level': '50.0'},
            'sentiment_data': {'sentiment_score': 0.0},
            'current_price': 45000.0
        })

        assert result['signal']['type'] == 'HOLD'
        assert -0.2 <= result['signal']['combined_score'] <= 0.2

    @pytest.mark.asyncio
    async def test_moderate_bearish_signal(self):
        """Test SELL signal (-0.5 < combined_score < -0.2)."""
        result = await generate_trading_signal.handler({
            'symbol': 'BTCUSDT',
            'technical_data': {
                'indicators': {'rsi': 60.0, 'macd_hist': -20.0},
                'interpretation': {'rsi_status': 'Neutral', 'macd_status': 'Bearish'}
            },
            'trend_data': {'trend_score': 0.3},
            'momentum_data': {'momentum_score': -0.4},
            'pattern_data': {'current_level': '65.0'},
            'sentiment_data': {'sentiment_score': -0.3},
            'current_price': 45000.0
        })

        assert result['signal']['type'] == 'SELL'
        assert -0.5 <= result['signal']['combined_score'] < -0.2

    @pytest.mark.asyncio
    async def test_strong_bearish_signal(self):
        """Test STRONG_SELL signal (combined_score < -0.5)."""
        result = await generate_trading_signal.handler({
            'symbol': 'BTCUSDT',
            'technical_data': {
                'indicators': {'rsi': 80.0, 'macd_hist': -60.0},
                'interpretation': {'rsi_status': 'Overbought', 'macd_status': 'Bearish'}
            },
            'trend_data': {'trend_score': 0.1},
            'momentum_data': {'momentum_score': -0.9},
            'pattern_data': {'current_level': '90.0'},
            'sentiment_data': {'sentiment_score': -0.8},
            'current_price': 45000.0
        })

        assert result['signal']['type'] == 'STRONG_SELL'
        assert result['signal']['combined_score'] < -0.5


class TestVolatilityAdjustment:
    """Test volatility-based confidence adjustment."""

    @pytest.mark.asyncio
    async def test_high_volatility_reduces_confidence(self):
        """Test with high volatility (>0.7) reduces confidence by 20%."""
        result = await generate_trading_signal.handler({
            'symbol': 'BTCUSDT',
            'technical_data': {
                'indicators': {'rsi': 30.0, 'macd_hist': 40.0},
                'interpretation': {'rsi_status': 'Oversold', 'macd_status': 'Bullish'}
            },
            'trend_data': {'trend_score': 0.8},
            'momentum_data': {'momentum_score': 0.7},
            'volatility_data': {'volatility_score': 0.8},  # High volatility
            'sentiment_data': {'sentiment_score': 0.6},
            'current_price': 45000.0
        })

        assert result['signal']['volatility_adjustment'] == 0.8
        # Confidence should be reduced
        base_confidence = abs(result['signal']['combined_score'])
        expected_confidence = base_confidence * 0.8
        assert abs(result['signal']['confidence'] - expected_confidence) < 0.01

    @pytest.mark.asyncio
    async def test_normal_volatility_no_reduction(self):
        """Test with normal volatility (≤0.7) has no confidence reduction."""
        result = await generate_trading_signal.handler({
            'symbol': 'BTCUSDT',
            'technical_data': {
                'indicators': {'rsi': 30.0, 'macd_hist': 40.0},
                'interpretation': {'rsi_status': 'Oversold', 'macd_status': 'Bullish'}
            },
            'trend_data': {'trend_score': 0.8},
            'momentum_data': {'momentum_score': 0.7},
            'volatility_data': {'volatility_score': 0.5},  # Normal volatility
            'sentiment_data': {'sentiment_score': 0.6},
            'current_price': 45000.0
        })

        assert result['signal']['volatility_adjustment'] == 1.0
        # Confidence should not be reduced
        base_confidence = min(abs(result['signal']['combined_score']), 1.0)
        assert abs(result['signal']['confidence'] - base_confidence) < 0.01

    @pytest.mark.asyncio
    async def test_volatility_threshold_boundary(self):
        """Test volatility exactly at 0.7 threshold."""
        result = await generate_trading_signal.handler({
            'symbol': 'BTCUSDT',
            'technical_data': {
                'indicators': {'rsi': 40.0, 'macd_hist': 20.0},
                'interpretation': {'rsi_status': 'Neutral', 'macd_status': 'Bullish'}
            },
            'volatility_data': {'volatility_score': 0.7},  # Exactly at threshold
            'sentiment_data': {'sentiment_score': 0.3},
            'current_price': 45000.0
        })

        # At 0.7, should not trigger reduction (only > 0.7)
        assert result['signal']['volatility_adjustment'] == 1.0


class TestComponentWeighting:
    """Test component weighting in score calculation."""

    @pytest.mark.asyncio
    async def test_classic_indicators_contribution(self):
        """Verify classic indicators contribute 30% to technical score."""
        result = await generate_trading_signal.handler({
            'symbol': 'BTCUSDT',
            'technical_data': {
                'indicators': {'rsi': 30.0, 'macd_hist': 50.0},
                'interpretation': {
                    'rsi_status': 'Oversold',
                    'macd_status': 'Bullish',
                    'bb_status': 'Near Lower'
                }
            },
            'trend_data': {'trend_score': 0.5},  # Neutral
            'momentum_data': {'momentum_score': 0.0},  # Neutral
            'pattern_data': {'current_level': '50.0'},  # Neutral
            'sentiment_data': {'sentiment_score': 0.0},
            'current_price': 45000.0
        })

        signal = result['signal']
        # Classic score should be: RSI(0.2) + MACD(0.3) + BB(0.3) = 0.8
        # (RSI at 30.0 is exactly at boundary, uses neutral formula: (50-30)/100 = 0.2)
        # Technical score = 0.8 * 0.30 + 0 * 0.25 + 0 * 0.25 + 0 * 0.10 = 0.24
        assert abs(signal['classic_score'] - 0.8) < 0.01
        assert abs(signal['technical_score'] - 0.24) < 0.01

    @pytest.mark.asyncio
    async def test_trend_contribution(self):
        """Verify trend contributes 25% to technical score."""
        result = await generate_trading_signal.handler({
            'symbol': 'BTCUSDT',
            'technical_data': {
                'indicators': {'rsi': 50.0, 'macd_hist': 0.0},
                'interpretation': {'rsi_status': 'Neutral', 'macd_status': 'Neutral'}
            },
            'trend_data': {'trend_score': 1.0},  # Max uptrend (normalized to 1.0)
            'momentum_data': {'momentum_score': 0.0},
            'pattern_data': {'current_level': '50.0'},
            'sentiment_data': {'sentiment_score': 0.0},
            'current_price': 45000.0
        })

        signal = result['signal']
        # Trend normalized = (1.0 - 0.5) * 2 = 1.0
        # Technical score = 0 * 0.30 + 1.0 * 0.25 + 0 * 0.25 + 0 * 0.10 = 0.25
        assert abs(signal['trend_score'] - 1.0) < 0.01
        assert abs(signal['technical_score'] - 0.25) < 0.01

    @pytest.mark.asyncio
    async def test_momentum_contribution(self):
        """Verify momentum contributes 25% to technical score."""
        result = await generate_trading_signal.handler({
            'symbol': 'BTCUSDT',
            'technical_data': {
                'indicators': {'rsi': 50.0, 'macd_hist': 0.0},
                'interpretation': {'rsi_status': 'Neutral', 'macd_status': 'Neutral'}
            },
            'trend_data': {'trend_score': 0.5},  # Neutral
            'momentum_data': {'momentum_score': 1.0},  # Max bullish
            'pattern_data': {'current_level': '50.0'},
            'sentiment_data': {'sentiment_score': 0.0},
            'current_price': 45000.0
        })

        signal = result['signal']
        # Technical score = 0 * 0.30 + 0 * 0.25 + 1.0 * 0.25 + 0 * 0.10 = 0.25
        assert signal['momentum_score'] == 1.0
        assert abs(signal['technical_score'] - 0.25) < 0.01

    @pytest.mark.asyncio
    async def test_pattern_contribution(self):
        """Verify patterns contribute 10% to technical score."""
        result = await generate_trading_signal.handler({
            'symbol': 'BTCUSDT',
            'technical_data': {
                'indicators': {'rsi': 50.0, 'macd_hist': 0.0},
                'interpretation': {'rsi_status': 'Neutral', 'macd_status': 'Neutral'}
            },
            'trend_data': {'trend_score': 0.5},
            'momentum_data': {'momentum_score': 0.0},
            'pattern_data': {'current_level': '0.0'},  # Max support = 0.7
            'sentiment_data': {'sentiment_score': 0.0},
            'current_price': 45000.0
        })

        signal = result['signal']
        # Technical score = 0 * 0.30 + 0 * 0.25 + 0 * 0.25 + 0.7 * 0.10 = 0.07
        assert signal['pattern_score'] == 0.7
        assert abs(signal['technical_score'] - 0.07) < 0.01

    @pytest.mark.asyncio
    async def test_technical_total_weight(self):
        """Verify technical total is 60% weight in combined score."""
        result = await generate_trading_signal.handler({
            'symbol': 'BTCUSDT',
            'technical_data': {
                'indicators': {'rsi': 30.0, 'macd_hist': 40.0},
                'interpretation': {'rsi_status': 'Oversold', 'macd_status': 'Bullish'}
            },
            'trend_data': {'trend_score': 0.8},
            'momentum_data': {'momentum_score': 0.6},
            'pattern_data': {'current_level': '20.0'},
            'sentiment_data': {'sentiment_score': 0.0},  # No sentiment
            'current_price': 45000.0
        })

        signal = result['signal']
        # Combined = tech * 0.6 + sentiment * 0.4
        expected_combined = signal['technical_score'] * 0.6 + 0.0 * 0.4
        assert abs(signal['combined_score'] - expected_combined) < 0.01

    @pytest.mark.asyncio
    async def test_sentiment_weight(self):
        """Verify sentiment is 40% weight in combined score."""
        result = await generate_trading_signal.handler({
            'symbol': 'BTCUSDT',
            'technical_data': {
                'indicators': {'rsi': 50.0, 'macd_hist': 0.0},
                'interpretation': {'rsi_status': 'Neutral', 'macd_status': 'Neutral'}
            },
            'trend_data': {'trend_score': 0.5},
            'momentum_data': {'momentum_score': 0.0},
            'pattern_data': {'current_level': '50.0'},
            'sentiment_data': {'sentiment_score': 1.0},  # Max positive sentiment
            'current_price': 45000.0
        })

        signal = result['signal']
        # Combined = tech * 0.6 + sentiment * 0.4
        expected_combined = signal['technical_score'] * 0.6 + 1.0 * 0.4
        assert abs(signal['combined_score'] - expected_combined) < 0.01
        # With mostly neutral technicals, sentiment should dominate
        assert signal['combined_score'] > 0.35  # 0.4 * 1.0 = 0.4 (minus small tech contrib)


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_missing_indicator_data(self):
        """Test with missing/None indicator data."""
        result = await generate_trading_signal.handler({
            'symbol': 'BTCUSDT',
            'technical_data': {
                'indicators': {},
                'interpretation': {}
            },
            'sentiment_data': {'sentiment_score': 0.3},
            'current_price': 45000.0
        })

        assert 'signal' in result
        assert result['signal']['type'] in ['STRONG_BUY', 'BUY', 'HOLD', 'SELL', 'STRONG_SELL']

    @pytest.mark.asyncio
    async def test_partial_indicator_data(self):
        """Test with partial indicator data (some provided, some missing)."""
        result = await generate_trading_signal.handler({
            'symbol': 'BTCUSDT',
            'technical_data': {
                'indicators': {'rsi': 55.0},  # Only RSI
                'interpretation': {'rsi_status': 'Neutral'}
            },
            'trend_data': {'trend_score': 0.7},  # Only trend
            'sentiment_data': {'sentiment_score': 0.2},
            'current_price': 45000.0
        })

        assert 'signal' in result
        signal = result['signal']
        assert 'classic_score' in signal
        assert 'trend_score' in signal
        # Missing indicators should default to neutral values
        assert signal['momentum_score'] == 0.0  # Default
        assert signal['pattern_score'] == 0.0  # Default

    @pytest.mark.asyncio
    async def test_extreme_values(self):
        """Test with extreme values."""
        result = await generate_trading_signal.handler({
            'symbol': 'BTCUSDT',
            'technical_data': {
                'indicators': {'rsi': 100.0, 'macd_hist': 1000.0},
                'interpretation': {'rsi_status': 'Overbought', 'macd_status': 'Bullish'}
            },
            'trend_data': {'trend_score': 1.0},
            'momentum_data': {'momentum_score': 1.0},
            'volatility_data': {'volatility_score': 1.0},
            'pattern_data': {'current_level': '0.0'},
            'sentiment_data': {'sentiment_score': 1.0},
            'current_price': 45000.0
        })

        assert 'signal' in result
        # Should handle extreme values gracefully
        assert 0.0 <= result['signal']['confidence'] <= 1.0

    @pytest.mark.asyncio
    async def test_none_values_in_data(self):
        """Test with None values in data structures."""
        result = await generate_trading_signal.handler({
            'symbol': 'BTCUSDT',
            'technical_data': {
                'indicators': {},  # Empty dict instead of None values
                'interpretation': {}
            },
            'trend_data': None,
            'momentum_data': None,
            'volatility_data': None,
            'pattern_data': None,
            'sentiment_data': {'sentiment_score': 0.0},
            'current_price': 45000.0
        })

        assert 'signal' in result
        # Should default to neutral/hold when data is None
        assert result['signal']['type'] in ['HOLD', 'BUY', 'SELL']

    @pytest.mark.asyncio
    async def test_empty_dict_values(self):
        """Test with empty dictionaries."""
        result = await generate_trading_signal.handler({
            'symbol': 'BTCUSDT',
            'technical_data': {},
            'trend_data': {},
            'momentum_data': {},
            'volatility_data': {},
            'pattern_data': {},
            'sentiment_data': {},
            'current_price': 45000.0
        })

        assert 'signal' in result
        assert result['signal']['type'] == 'HOLD'
        # All scores should default to neutral
        assert abs(result['signal']['combined_score']) < 0.2

    @pytest.mark.asyncio
    async def test_negative_price(self):
        """Test with negative price (should still work)."""
        result = await generate_trading_signal.handler({
            'symbol': 'BTCUSDT',
            'technical_data': {
                'indicators': {'rsi': 50.0, 'macd_hist': 0.0},
                'interpretation': {'rsi_status': 'Neutral', 'macd_status': 'Neutral'}
            },
            'sentiment_data': {'sentiment_score': 0.0},
            'current_price': -1000.0  # Invalid but should not crash
        })

        assert 'signal' in result
        assert result['signal']['price'] == -1000.0

    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Test error handling with invalid input."""
        result = await generate_trading_signal.handler({})

        # Should return error structure
        assert 'is_error' in result or 'signal' in result
        # Either returns error or handles gracefully with defaults


class TestRealisticScenarios:
    """Test realistic market scenarios."""

    @pytest.mark.asyncio
    async def test_strong_bullish_market(self):
        """Test strong bullish market scenario."""
        result = await generate_trading_signal.handler({
            'symbol': 'BTCUSDT',
            'technical_data': {
                'indicators': {'rsi': 35.0, 'macd_hist': 45.0},
                'interpretation': {
                    'rsi_status': 'Oversold',
                    'macd_status': 'Bullish',
                    'bb_status': 'Near Lower'
                }
            },
            'trend_data': {'trend_score': 0.85},  # Strong uptrend
            'momentum_data': {'momentum_score': 0.75},  # Strong momentum
            'volatility_data': {'volatility_score': 0.45},  # Normal
            'pattern_data': {'current_level': '23.6'},  # Strong support
            'sentiment_data': {'sentiment_score': 0.65},  # Positive
            'current_price': 45000.0
        })

        assert result['signal']['type'] == 'STRONG_BUY'
        assert result['signal']['confidence'] > 0.5
        assert result['signal']['combined_score'] > 0.5

    @pytest.mark.asyncio
    async def test_strong_bearish_market(self):
        """Test strong bearish market scenario."""
        result = await generate_trading_signal.handler({
            'symbol': 'BTCUSDT',
            'technical_data': {
                'indicators': {'rsi': 78.0, 'macd_hist': -55.0},
                'interpretation': {
                    'rsi_status': 'Overbought',
                    'macd_status': 'Bearish',
                    'bb_status': 'Near Upper'
                }
            },
            'trend_data': {'trend_score': 0.15},  # Strong downtrend
            'momentum_data': {'momentum_score': -0.85},  # Bearish momentum
            'volatility_data': {'volatility_score': 0.55},  # Normal
            'pattern_data': {'current_level': '88.0'},  # Strong resistance
            'sentiment_data': {'sentiment_score': -0.7},  # Negative
            'current_price': 45000.0
        })

        assert result['signal']['type'] == 'STRONG_SELL'
        assert result['signal']['confidence'] > 0.5
        assert result['signal']['combined_score'] < -0.5

    @pytest.mark.asyncio
    async def test_choppy_uncertain_market(self):
        """Test choppy/uncertain market scenario."""
        result = await generate_trading_signal.handler({
            'symbol': 'BTCUSDT',
            'technical_data': {
                'indicators': {'rsi': 52.0, 'macd_hist': -5.0},
                'interpretation': {
                    'rsi_status': 'Neutral',
                    'macd_status': 'Neutral',
                    'bb_status': 'Near Middle'
                }
            },
            'trend_data': {'trend_score': 0.48},  # Unclear trend
            'momentum_data': {'momentum_score': 0.05},  # Weak momentum
            'volatility_data': {'volatility_score': 0.75},  # High volatility
            'pattern_data': {'current_level': '51.0'},  # Neutral zone
            'sentiment_data': {'sentiment_score': -0.05},  # Neutral
            'current_price': 45000.0
        })

        assert result['signal']['type'] == 'HOLD'
        assert -0.2 <= result['signal']['combined_score'] <= 0.2
        # High volatility should reduce confidence
        assert result['signal']['volatility_adjustment'] == 0.8

    @pytest.mark.asyncio
    async def test_mixed_signals_bullish_lean(self):
        """Test mixed signals with slight bullish lean."""
        result = await generate_trading_signal.handler({
            'symbol': 'ETHUSDT',
            'technical_data': {
                'indicators': {'rsi': 48.0, 'macd_hist': 10.0},
                'interpretation': {
                    'rsi_status': 'Neutral',
                    'macd_status': 'Bullish'
                }
            },
            'trend_data': {'trend_score': 0.55},  # Slight uptrend
            'momentum_data': {'momentum_score': 0.25},  # Weak bullish
            'volatility_data': {'volatility_score': 0.6},
            'pattern_data': {'current_level': '42.0'},  # Moderate support
            'sentiment_data': {'sentiment_score': 0.15},  # Slightly positive
            'current_price': 3000.0
        })

        assert result['signal']['type'] in ['BUY', 'HOLD']
        assert result['signal']['combined_score'] > 0.0

    @pytest.mark.asyncio
    async def test_mixed_signals_bearish_lean(self):
        """Test mixed signals with slight bearish lean."""
        result = await generate_trading_signal.handler({
            'symbol': 'ETHUSDT',
            'technical_data': {
                'indicators': {'rsi': 58.0, 'macd_hist': -12.0},
                'interpretation': {
                    'rsi_status': 'Neutral',
                    'macd_status': 'Bearish'
                }
            },
            'trend_data': {'trend_score': 0.42},  # Slight downtrend
            'momentum_data': {'momentum_score': -0.3},  # Weak bearish
            'volatility_data': {'volatility_score': 0.55},
            'pattern_data': {'current_level': '62.0'},  # Moderate resistance
            'sentiment_data': {'sentiment_score': -0.2},  # Slightly negative
            'current_price': 3000.0
        })

        assert result['signal']['type'] in ['SELL', 'HOLD']
        assert result['signal']['combined_score'] < 0.0
