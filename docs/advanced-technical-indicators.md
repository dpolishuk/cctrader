# Advanced Technical Indicators

Comprehensive guide to the advanced technical analysis tools in CCTrader.

## Overview

The CCTrader agent now includes 9+ advanced technical indicators organized into four specialized analysis tools:

1. **Trend Analysis** - EMA, SMA variations, Ichimoku Cloud
2. **Momentum Analysis** - RSI, Stochastic, Elder Force Index, Elder Impulse System
3. **Volatility Analysis** - ATR, Bollinger Bands
4. **Pattern Analysis** - Fibonacci retracements and extensions

## Tools

### analyze_trend()

Analyzes market trend using multiple moving averages and Ichimoku Cloud.

**Indicators included:**
- EMA (9, 12, 26, 50, 200)
- SMA (20, 50, 100, 200)
- Ichimoku Cloud (full system)

**Output:**
- Trend score (0.0-1.0)
- All indicator values
- Detected signals (crossovers, cloud position)
- Interpretation text

**Usage example:**
```python
from src.agent.tools.technical_analysis import analyze_trend

result = await analyze_trend({
    'ohlcv_data': [...],  # OHLCV data
    'symbol': 'BTCUSDT',
    'timeframe': '1h'
})

print(f"Trend Score: {result['trend_score']}")
print(f"Signals: {result['signals']}")
```

**Interpretation:**
- Score > 0.75: Strong uptrend
- Score 0.55-0.75: Moderate uptrend
- Score 0.45-0.55: Neutral/consolidation
- Score 0.25-0.45: Moderate downtrend
- Score < 0.25: Strong downtrend

---

### analyze_momentum()

Analyzes momentum using RSI, Stochastic, and Elder systems.

**Indicators included:**
- RSI (14)
- Stochastic Oscillator (%K 14, %D 3)
- Elder Force Index (13-period EMA)
- Elder Impulse System (blue/red/gray)

**Output:**
- Momentum score (-1.0 to 1.0)
- All indicator values
- Detected signals (overbought/oversold, impulse color)
- Interpretation text

**Usage example:**
```python
result = await analyze_momentum({
    'ohlcv_data': [...],
    'symbol': 'BTCUSDT',
    'timeframe': '1h'
})

print(f"Momentum Score: {result['momentum_score']}")
print(f"Elder Impulse: {result['indicators']['elder_impulse']}")
```

**Interpretation:**
- Score > 0.5: Strong bullish momentum
- Score 0.2 to 0.5: Moderate bullish
- Score -0.2 to 0.2: Neutral
- Score -0.5 to -0.2: Moderate bearish
- Score < -0.5: Strong bearish momentum

---

### analyze_volatility()

Analyzes volatility using ATR and Bollinger Bands.

**Indicators included:**
- ATR (14-period)
- ATR Percentage (ATR / price)
- Bollinger Bands (20, 2 std)
- BB Width and BB Width %

**Output:**
- Volatility score (0.0-1.0)
- All indicator values
- Detected signals (volatility level, BB position)
- Interpretation text

**Usage example:**
```python
result = await analyze_volatility({
    'ohlcv_data': [...],
    'symbol': 'BTCUSDT',
    'timeframe': '1h'
})

print(f"ATR: {result['indicators']['atr']}")
print(f"ATR%: {result['indicators']['atr_percent']}%")
```

**Interpretation:**
- ATR% < 0.5%: Very low volatility
- ATR% 0.5-1.0%: Low volatility
- ATR% 1.0-2.0%: Normal volatility
- ATR% 2.0-3.0%: High volatility
- ATR% > 3.0%: Very high volatility

---

### analyze_patterns()

Analyzes Fibonacci retracement and extension levels.

**Indicators included:**
- Fibonacci retracements (0%, 23.6%, 38.2%, 50%, 61.8%, 78.6%, 100%)
- Fibonacci extensions (127.2%, 161.8%)
- Support/resistance level identification

**Output:**
- All Fibonacci levels
- Current level (closest to price)
- Support and resistance levels
- Detected signals
- Interpretation text

**Usage example:**
```python
result = await analyze_patterns({
    'ohlcv_data': [...],
    'symbol': 'BTCUSDT',
    'timeframe': '1h',
    'lookback_periods': 50  # Optional, default 50
})

print(f"Current Level: {result['current_level']}%")
print(f"Support Levels: {result['support_levels']}")
```

**Interpretation:**
- Near 0-30%: Strong support zone (bullish)
- Near 38.2%: Moderate support
- Near 50%: Neutral pivot
- Near 61.8%: Moderate resistance
- Near 78.6-100%: Strong resistance zone (bearish)

---

## Enhanced Signal Generation

The `generate_trading_signal()` function now integrates all indicators.

**New scoring system:**

| Component | Weight | Range |
|-----------|--------|-------|
| Classic (RSI/MACD/BB) | 30% | -1.0 to 1.0 |
| Trend | 25% | -1.0 to 1.0 |
| Momentum | 25% | -1.0 to 1.0 |
| Patterns | 10% | -1.0 to 1.0 |
| **Technical Total** | **60%** | -1.0 to 1.0 |
| Sentiment | 40% | -1.0 to 1.0 |
| **Combined** | **100%** | -1.0 to 1.0 |

**Volatility adjustment:**
- High volatility (>0.7): Reduces confidence by 20%
- Normal volatility (≤0.7): No adjustment

**Signal thresholds:**
- STRONG_BUY: combined_score > 0.5
- BUY: combined_score > 0.2
- HOLD: -0.2 ≤ combined_score ≤ 0.2
- SELL: combined_score < -0.2
- STRONG_SELL: combined_score < -0.5

**Usage example:**
```python
from src.agent.tools.signals import generate_trading_signal

result = await generate_trading_signal({
    'symbol': 'BTCUSDT',
    'technical_data': {...},  # from analyze_technicals()
    'trend_data': {...},      # from analyze_trend()
    'momentum_data': {...},   # from analyze_momentum()
    'volatility_data': {...}, # from analyze_volatility()
    'pattern_data': {...},    # from analyze_patterns()
    'sentiment_data': {...},
    'current_price': 45000.0
})

print(f"Signal: {result['signal']['type']}")
print(f"Confidence: {result['signal']['confidence']:.1%}")
```

---

## Best Practices

### Data Requirements
- **Trend analysis**: Minimum 200 periods (for EMA 200)
- **Momentum analysis**: Minimum 50 periods
- **Volatility analysis**: Minimum 20 periods
- **Pattern analysis**: Minimum 50 periods (configurable)

### Timeframe Selection
- **Short-term trading**: 5m, 15m, 1h
- **Swing trading**: 4h, 1d
- **Position trading**: 1d, 1w

### Combining Indicators
1. **Trend confirmation**: Use EMA/Ichimoku to confirm overall direction
2. **Entry timing**: Use Stochastic/RSI for overbought/oversold
3. **Stop placement**: Use ATR for volatility-adjusted stops
4. **Target levels**: Use Fibonacci for support/resistance targets

### Risk Management
- High volatility: Use wider stops, reduce position size
- Low volatility: Potential breakout setups, tighter stops
- Check volatility before every trade

---

## Examples

### Bullish Setup Example
```
Trend Score: 0.85 (strong uptrend)
Momentum Score: 0.70 (bullish)
Volatility: ATR 1.5% (normal)
Pattern: At 38.2% Fibonacci (support)

Signal: STRONG_BUY
Confidence: 78%
```

### Bearish Setup Example
```
Trend Score: 0.25 (strong downtrend)
Momentum Score: -0.65 (bearish)
Volatility: ATR 2.8% (high)
Pattern: At 78.6% Fibonacci (resistance)

Signal: STRONG_SELL
Confidence: 62% (reduced due to high volatility)
```

---

## Technical Details

### pandas-ta Library
All indicators use the `pandas-ta` library (v0.3.14b+):
- Vectorized calculations for performance
- Industry-standard implementations
- 130+ indicators available (we use 12)

### Calculation Methods
- **EMA**: Exponential weighting, more responsive to recent prices
- **SMA**: Simple average, smoother but lags more
- **Ichimoku**: Multi-component cloud system
- **Stochastic**: Momentum oscillator (0-100 range)
- **Elder Force**: Price change × volume, EMA smoothed
- **ATR**: True Range average, volatility measure
- **Fibonacci**: Based on recent swing high/low

---

## References

- pandas-ta documentation: https://github.com/twopirllc/pandas-ta
- Elder-Ray Index: Dr. Alexander Elder, "Trading for a Living"
- Ichimoku Cloud: Goichi Hosoda, 1960s
- Fibonacci: Leonardo Fibonacci, 13th century

---

## See Also

- [Token Interval Tracking](./token-interval-tracking.md)
- [Technical Analysis Design](./plans/2025-11-20-token-interval-tracking-design.md)
