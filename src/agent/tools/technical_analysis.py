"""Technical analysis tools using pandas-ta."""
import pandas as pd
import pandas_ta as ta
from typing import Any, Dict
from claude_agent_sdk import tool

@tool(
    name="analyze_technicals",
    description="Perform technical analysis on OHLCV data with RSI, MACD, Bollinger Bands",
    input_schema={
        "ohlcv_data": list,
        "symbol": str,
        "timeframe": str
    }
)
async def analyze_technicals(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate technical indicators: RSI, MACD, Bollinger Bands, Volume analysis.

    Returns analysis results with indicator values and interpretation.
    """
    try:
        ohlcv_data = args.get("ohlcv_data", [])
        symbol = args.get("symbol", "Unknown")
        timeframe = args.get("timeframe", "Unknown")

        if not ohlcv_data:
            return {
                "content": [{"type": "text", "text": "No OHLCV data provided"}],
                "is_error": True
            }

        # Convert to DataFrame
        df = pd.DataFrame(ohlcv_data)

        # Calculate indicators
        # RSI (14-period)
        df['rsi'] = ta.rsi(df['close'], length=14)

        # MACD
        macd = ta.macd(df['close'])
        df['macd'] = macd['MACD_12_26_9']
        df['macd_signal'] = macd['MACDs_12_26_9']
        df['macd_hist'] = macd['MACDh_12_26_9']

        # Bollinger Bands
        bbands = ta.bbands(df['close'], length=20, std=2)
        # pandas-ta column names may vary by version
        try:
            df['bb_upper'] = bbands['BBU_20_2.0_2.0']
            df['bb_middle'] = bbands['BBM_20_2.0_2.0']
            df['bb_lower'] = bbands['BBL_20_2.0_2.0']
        except KeyError:
            df['bb_upper'] = bbands['BBU_20_2.0']
            df['bb_middle'] = bbands['BBM_20_2.0']
            df['bb_lower'] = bbands['BBL_20_2.0']

        # Volume SMA
        df['volume_sma'] = ta.sma(df['volume'], length=20)

        # Get latest values
        latest = df.iloc[-1]

        # Interpretation
        rsi_status = "Oversold" if latest['rsi'] < 30 else "Overbought" if latest['rsi'] > 70 else "Neutral"
        macd_status = "Bullish" if latest['macd'] > latest['macd_signal'] else "Bearish"
        bb_status = "Near Upper Band" if latest['close'] > latest['bb_middle'] else "Near Lower Band"

        indicators = {
            "rsi": float(latest['rsi']),
            "macd": float(latest['macd']),
            "macd_signal": float(latest['macd_signal']),
            "macd_hist": float(latest['macd_hist']),
            "bb_upper": float(latest['bb_upper']),
            "bb_middle": float(latest['bb_middle']),
            "bb_lower": float(latest['bb_lower']),
            "price": float(latest['close']),
            "volume": float(latest['volume']),
            "volume_sma": float(latest['volume_sma'])
        }

        analysis_text = f"""Technical Analysis for {symbol} ({timeframe}):

RSI (14): {latest['rsi']:.2f} - {rsi_status}
MACD: {latest['macd']:.4f} (Signal: {latest['macd_signal']:.4f}) - {macd_status}
Bollinger Bands: {bb_status}
  Upper: {latest['bb_upper']:.2f}
  Middle: {latest['bb_middle']:.2f}
  Lower: {latest['bb_lower']:.2f}
Current Price: {latest['close']:.2f}
Volume: {latest['volume']:.2f} (SMA: {latest['volume_sma']:.2f})
"""

        return {
            "content": [{"type": "text", "text": analysis_text}],
            "indicators": indicators,
            "interpretation": {
                "rsi_status": rsi_status,
                "macd_status": macd_status,
                "bb_status": bb_status
            }
        }

    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Error in technical analysis: {str(e)}"}],
            "is_error": True
        }

@tool(
    name="analyze_trend",
    description="Analyze trend using EMA, SMA variations and Ichimoku Cloud",
    input_schema={
        "ohlcv_data": list,
        "symbol": str,
        "timeframe": str
    }
)
async def analyze_trend(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate trend indicators: EMAs (9,12,26,50,200), SMAs (20,50,100,200), Ichimoku Cloud.
    Returns trend score (0.0-1.0) based on alignment and signals.
    """
    try:
        ohlcv_data = args.get("ohlcv_data", [])
        symbol = args.get("symbol", "Unknown")
        timeframe = args.get("timeframe", "Unknown")

        if not ohlcv_data:
            return {
                "content": [{"type": "text", "text": "No OHLCV data provided"}],
                "is_error": True
            }

        # Convert to DataFrame
        df = pd.DataFrame(ohlcv_data)

        # Check for sufficient data
        min_required = 200
        if len(df) < min_required:
            return {
                "content": [{"type": "text", "text": f"Insufficient data: need at least {min_required} periods, got {len(df)}"}],
                "is_error": True
            }

        # Calculate EMAs
        ema_periods = [9, 12, 26, 50, 200]
        for period in ema_periods:
            df[f'ema_{period}'] = ta.ema(df['close'], length=period)

        # Calculate SMAs
        sma_periods = [20, 50, 100, 200]
        for period in sma_periods:
            df[f'sma_{period}'] = ta.sma(df['close'], length=period)

        # Calculate Ichimoku Cloud
        ichimoku = ta.ichimoku(df['high'], df['low'], df['close'])
        if ichimoku is not None and len(ichimoku[0]) > 0:
            # ichimoku returns tuple of DataFrames
            ich_df = ichimoku[0]
            df['tenkan_sen'] = ich_df['ISA_9']  # Conversion Line
            df['kijun_sen'] = ich_df['ISB_26']  # Base Line
            df['senkou_span_a'] = ich_df['ITS_9']  # Leading Span A
            df['senkou_span_b'] = ich_df['IKS_26']  # Leading Span B
            df['chikou_span'] = ich_df['ICS_26']  # Lagging Span

        # Get latest values (drop NaN rows)
        latest = df.iloc[-1]
        current_price = float(latest['close'])

        # Extract indicator values
        indicators = {
            "ema_9": float(latest['ema_9']) if pd.notna(latest['ema_9']) else None,
            "ema_12": float(latest['ema_12']) if pd.notna(latest['ema_12']) else None,
            "ema_26": float(latest['ema_26']) if pd.notna(latest['ema_26']) else None,
            "ema_50": float(latest['ema_50']) if pd.notna(latest['ema_50']) else None,
            "ema_200": float(latest['ema_200']) if pd.notna(latest['ema_200']) else None,
            "sma_20": float(latest['sma_20']) if pd.notna(latest['sma_20']) else None,
            "sma_50": float(latest['sma_50']) if pd.notna(latest['sma_50']) else None,
            "sma_100": float(latest['sma_100']) if pd.notna(latest['sma_100']) else None,
            "sma_200": float(latest['sma_200']) if pd.notna(latest['sma_200']) else None,
            "ichimoku": {}
        }

        # Ichimoku indicators
        if pd.notna(latest.get('tenkan_sen')):
            tenkan = float(latest['tenkan_sen'])
            kijun = float(latest['kijun_sen'])
            span_a = float(latest['senkou_span_a'])
            span_b = float(latest['senkou_span_b'])
            chikou = float(latest['chikou_span'])

            cloud_color = "bullish" if span_a > span_b else "bearish"

            indicators["ichimoku"] = {
                "tenkan_sen": tenkan,
                "kijun_sen": kijun,
                "senkou_span_a": span_a,
                "senkou_span_b": span_b,
                "chikou_span": chikou,
                "cloud_color": cloud_color
            }

        # Calculate trend score components
        scores = []
        signals = []

        # 1. EMA Alignment Score (0.3 weight)
        ema_alignment_score = 0.0
        ema_count = 0
        if all(indicators[f'ema_{p}'] is not None for p in ema_periods):
            # Check if EMAs are in ascending order (bullish)
            ema_values = [indicators[f'ema_{p}'] for p in ema_periods]
            alignments = sum(1 for i in range(len(ema_values)-1) if ema_values[i] > ema_values[i+1])
            ema_alignment_score = alignments / (len(ema_values) - 1)
            ema_count = alignments

            # Check for golden crosses
            if indicators['ema_12'] > indicators['ema_26']:
                signals.append("ema_golden_cross_12_26")
            if indicators['ema_9'] > indicators['ema_26']:
                signals.append("ema_golden_cross_9_26")

        scores.append(ema_alignment_score * 0.3)

        # 2. Price Position vs EMAs (0.25 weight)
        price_position_score = 0.0
        if all(indicators[f'ema_{p}'] is not None for p in ema_periods):
            above_emas = sum(1 for p in ema_periods if current_price > indicators[f'ema_{p}'])
            price_position_score = above_emas / len(ema_periods)

            if above_emas == len(ema_periods):
                signals.append("price_above_all_emas")
            elif above_emas == 0:
                signals.append("price_below_all_emas")

        scores.append(price_position_score * 0.25)

        # 3. SMA Alignment and Position (0.2 weight)
        sma_score = 0.0
        if all(indicators[f'sma_{p}'] is not None for p in sma_periods):
            # Check SMA alignment
            sma_values = [indicators[f'sma_{p}'] for p in sma_periods]
            sma_alignments = sum(1 for i in range(len(sma_values)-1) if sma_values[i] > sma_values[i+1])
            alignment_part = sma_alignments / (len(sma_values) - 1)

            # Check price position vs SMAs
            above_smas = sum(1 for p in sma_periods if current_price > indicators[f'sma_{p}'])
            position_part = above_smas / len(sma_periods)

            sma_score = (alignment_part + position_part) / 2

            if current_price > indicators['sma_200']:
                signals.append("above_sma_200")
            elif current_price < indicators['sma_200']:
                signals.append("below_sma_200")

        scores.append(sma_score * 0.2)

        # 4. Ichimoku Cloud Analysis (0.25 weight)
        ichimoku_score = 0.0
        if indicators["ichimoku"]:
            ich = indicators["ichimoku"]
            cloud_top = max(ich['senkou_span_a'], ich['senkou_span_b'])
            cloud_bottom = min(ich['senkou_span_a'], ich['senkou_span_b'])

            # Price above cloud
            price_above_cloud = current_price > cloud_top
            price_in_cloud = cloud_bottom <= current_price <= cloud_top
            price_below_cloud = current_price < cloud_bottom

            # TK cross
            tk_bullish = ich['tenkan_sen'] > ich['kijun_sen']

            # Calculate ichimoku score
            if price_above_cloud and tk_bullish and ich['cloud_color'] == "bullish":
                ichimoku_score = 1.0
                signals.append("ichimoku_strong_bullish")
            elif price_above_cloud and tk_bullish:
                ichimoku_score = 0.8
                signals.append("ichimoku_bullish")
            elif price_above_cloud:
                ichimoku_score = 0.6
                signals.append("price_above_cloud")
            elif price_in_cloud:
                ichimoku_score = 0.5
                signals.append("price_in_cloud")
            elif price_below_cloud and not tk_bullish and ich['cloud_color'] == "bearish":
                ichimoku_score = 0.0
                signals.append("ichimoku_strong_bearish")
            elif price_below_cloud:
                ichimoku_score = 0.3
                signals.append("ichimoku_bearish")

        scores.append(ichimoku_score * 0.25)

        # Calculate final trend score
        trend_score = sum(scores)

        # Generate interpretation
        if trend_score >= 0.75:
            interpretation = "Strong uptrend: "
            details = []
            if ema_count >= 3:
                details.append("Short-term EMAs above long-term")
            if price_position_score > 0.8:
                details.append("Price above most EMAs")
            if ichimoku_score >= 0.8:
                details.append("Ichimoku confirms bullish")
            interpretation += ", ".join(details) if details else "Multiple bullish signals"
        elif trend_score >= 0.55:
            interpretation = "Moderate uptrend: Mixed but bullish-leaning signals"
        elif trend_score >= 0.45:
            interpretation = "Neutral trend: Consolidation or range-bound market"
        elif trend_score >= 0.25:
            interpretation = "Moderate downtrend: Mixed but bearish-leaning signals"
        else:
            interpretation = "Strong downtrend: Multiple bearish signals across indicators"

        result = {
            "trend_score": round(trend_score, 2),
            "indicators": indicators,
            "signals": signals,
            "interpretation": interpretation
        }

        # Format text output
        ema_9_str = f"{indicators['ema_9']:.2f}" if indicators['ema_9'] is not None else 'N/A'
        ema_12_str = f"{indicators['ema_12']:.2f}" if indicators['ema_12'] is not None else 'N/A'
        ema_26_str = f"{indicators['ema_26']:.2f}" if indicators['ema_26'] is not None else 'N/A'
        ema_50_str = f"{indicators['ema_50']:.2f}" if indicators['ema_50'] is not None else 'N/A'
        ema_200_str = f"{indicators['ema_200']:.2f}" if indicators['ema_200'] is not None else 'N/A'
        sma_20_str = f"{indicators['sma_20']:.2f}" if indicators['sma_20'] is not None else 'N/A'
        sma_50_str = f"{indicators['sma_50']:.2f}" if indicators['sma_50'] is not None else 'N/A'
        sma_100_str = f"{indicators['sma_100']:.2f}" if indicators['sma_100'] is not None else 'N/A'
        sma_200_str = f"{indicators['sma_200']:.2f}" if indicators['sma_200'] is not None else 'N/A'

        analysis_text = f"""Trend Analysis for {symbol} ({timeframe}):

Trend Score: {trend_score:.2f} / 1.00

EMAs:
  EMA 9: {ema_9_str}
  EMA 12: {ema_12_str}
  EMA 26: {ema_26_str}
  EMA 50: {ema_50_str}
  EMA 200: {ema_200_str}

SMAs:
  SMA 20: {sma_20_str}
  SMA 50: {sma_50_str}
  SMA 100: {sma_100_str}
  SMA 200: {sma_200_str}
"""

        if indicators["ichimoku"]:
            ich = indicators["ichimoku"]
            analysis_text += f"""
Ichimoku Cloud:
  Tenkan-sen (Conversion): {ich['tenkan_sen']:.2f}
  Kijun-sen (Base): {ich['kijun_sen']:.2f}
  Senkou Span A: {ich['senkou_span_a']:.2f}
  Senkou Span B: {ich['senkou_span_b']:.2f}
  Chikou Span: {ich['chikou_span']:.2f}
  Cloud Color: {ich['cloud_color']}
"""

        analysis_text += f"""
Signals: {', '.join(signals) if signals else 'None'}

Interpretation: {interpretation}
"""

        return {
            "content": [{"type": "text", "text": analysis_text}],
            **result
        }

    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Error in trend analysis: {str(e)}"}],
            "is_error": True
        }

@tool(
    name="analyze_momentum",
    description="Analyze momentum using RSI, Stochastic, Elder Force Index and Elder Impulse System",
    input_schema={
        "ohlcv_data": list,
        "symbol": str,
        "timeframe": str
    }
)
async def analyze_momentum(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate momentum indicators: RSI, Stochastic Oscillator, Elder Force Index, Elder Impulse System.
    Returns momentum score (-1.0 to 1.0) based on multiple momentum indicators.
    """
    try:
        ohlcv_data = args.get("ohlcv_data", [])
        symbol = args.get("symbol", "Unknown")
        timeframe = args.get("timeframe", "Unknown")

        if not ohlcv_data:
            return {
                "content": [{"type": "text", "text": "No OHLCV data provided"}],
                "is_error": True
            }

        # Convert to DataFrame
        df = pd.DataFrame(ohlcv_data)

        # Check for sufficient data (need at least 50 periods for all indicators)
        min_required = 50
        if len(df) < min_required:
            return {
                "content": [{"type": "text", "text": f"Insufficient data: need at least {min_required} periods, got {len(df)}"}],
                "is_error": True
            }

        # 1. Calculate RSI (14-period)
        df['rsi'] = ta.rsi(df['close'], length=14)

        # 2. Calculate Stochastic Oscillator (%K=14, %D=3, smooth=3)
        stoch = ta.stoch(df['high'], df['low'], df['close'], k=14, d=3, smooth_k=3)
        if stoch is not None:
            df['stoch_k'] = stoch['STOCHk_14_3_3']
            df['stoch_d'] = stoch['STOCHd_14_3_3']

        # 3. Calculate Elder Force Index
        # Force Index = (Close - Close.shift(1)) * Volume
        # Then apply 13-period EMA smoothing
        df['price_change'] = df['close'] - df['close'].shift(1)
        df['force_raw'] = df['price_change'] * df['volume']
        df['elder_force_index'] = ta.ema(df['force_raw'], length=13)

        # 4. Calculate Elder Impulse System components
        # Need EMA(13) and MACD histogram
        df['ema_13'] = ta.ema(df['close'], length=13)

        # Calculate MACD for histogram
        macd = ta.macd(df['close'], fast=12, slow=26, signal=9)
        if macd is not None:
            df['macd_histogram'] = macd['MACDh_12_26_9']

        # Determine EMA and MACD histogram directions (compare last 2 periods)
        if len(df) >= 2:
            ema_13_current = df['ema_13'].iloc[-1]
            ema_13_prev = df['ema_13'].iloc[-2]
            ema_13_direction = "rising" if ema_13_current > ema_13_prev else "falling"

            macd_hist_current = df['macd_histogram'].iloc[-1]
            macd_hist_prev = df['macd_histogram'].iloc[-2]
            macd_hist_direction = "rising" if macd_hist_current > macd_hist_prev else "falling"

            # Determine Elder Impulse color
            if ema_13_direction == "rising" and macd_hist_direction == "rising":
                elder_impulse = "blue"  # Bullish impulse
            elif ema_13_direction == "falling" and macd_hist_direction == "falling":
                elder_impulse = "red"  # Bearish impulse
            else:
                elder_impulse = "gray"  # Mixed signals
        else:
            ema_13_direction = "unknown"
            macd_hist_direction = "unknown"
            elder_impulse = "gray"

        # Get latest values
        latest = df.iloc[-1]

        # Extract indicator values
        rsi_value = float(latest['rsi']) if pd.notna(latest['rsi']) else None
        stoch_k = float(latest['stoch_k']) if pd.notna(latest['stoch_k']) else None
        stoch_d = float(latest['stoch_d']) if pd.notna(latest['stoch_d']) else None
        elder_force = float(latest['elder_force_index']) if pd.notna(latest['elder_force_index']) else None
        ema_13_value = float(latest['ema_13']) if pd.notna(latest['ema_13']) else None
        macd_hist_value = float(latest['macd_histogram']) if pd.notna(latest['macd_histogram']) else None

        # Check for insufficient calculated data
        if any(val is None for val in [rsi_value, stoch_k, stoch_d, elder_force, ema_13_value, macd_hist_value]):
            return {
                "content": [{"type": "text", "text": "Insufficient data for momentum calculation (NaN values in indicators)"}],
                "is_error": True
            }

        # Build indicators dictionary
        indicators = {
            "rsi": rsi_value,
            "stochastic_k": stoch_k,
            "stochastic_d": stoch_d,
            "elder_force_index": elder_force,
            "elder_impulse": elder_impulse,
            "ema_13": ema_13_value,
            "ema_13_direction": ema_13_direction,
            "macd_histogram": macd_hist_value,
            "macd_histogram_direction": macd_hist_direction
        }

        # Calculate momentum score (-1.0 to 1.0)
        score_components = []
        signals = []

        # 1. RSI contribution (0.3 weight)
        rsi_score = 0.0
        if rsi_value < 30:
            rsi_score = 0.3  # Oversold (bullish)
            signals.append("rsi_oversold")
        elif rsi_value > 70:
            rsi_score = -0.3  # Overbought (bearish)
            signals.append("rsi_overbought")
        else:
            # Scale based on distance from 50
            # RSI 50 = neutral (0.0), RSI 30-50 = slightly bullish, RSI 50-70 = slightly bearish
            normalized = (rsi_value - 50) / 20  # Converts 30-70 range to -1.0 to 1.0
            rsi_score = -normalized * 0.3  # Negative because higher RSI = more bearish in neutral zone
            signals.append("rsi_neutral")

        score_components.append(rsi_score)

        # 2. Stochastic contribution (0.25 weight)
        stoch_score = 0.0
        if stoch_k < 20:
            stoch_score += 0.25  # Oversold
            signals.append("stochastic_oversold")
        elif stoch_k > 80:
            stoch_score -= 0.25  # Overbought
            signals.append("stochastic_overbought")

        # %K vs %D crossover signal (0.15 weight within stochastic)
        if stoch_k > stoch_d:
            stoch_score += 0.15  # Bullish
            signals.append("stochastic_bullish_crossover")
        else:
            stoch_score -= 0.15  # Bearish
            signals.append("stochastic_bearish_crossover")

        score_components.append(stoch_score)

        # 3. Elder Force Index contribution (0.2 weight)
        force_score = 0.0
        if elder_force > 0:
            force_score = 0.2  # Positive force (bullish)
            signals.append("elder_force_positive")
        else:
            force_score = -0.2  # Negative force (bearish)
            signals.append("elder_force_negative")

        score_components.append(force_score)

        # 4. Elder Impulse contribution (0.25 weight)
        impulse_score = 0.0
        if elder_impulse == "blue":
            impulse_score = 0.25  # Bullish impulse
            signals.append("elder_impulse_bullish")
        elif elder_impulse == "red":
            impulse_score = -0.25  # Bearish impulse
            signals.append("elder_impulse_bearish")
        else:
            impulse_score = 0.0  # Neutral/mixed
            signals.append("elder_impulse_neutral")

        score_components.append(impulse_score)

        # Calculate final momentum score
        momentum_score = sum(score_components)

        # Generate interpretation
        if momentum_score >= 0.6:
            interpretation = "Strong bullish momentum: "
            details = []
            if elder_impulse == "blue":
                details.append("Elder Impulse blue")
            if elder_force > 0:
                details.append("positive Force Index")
            if rsi_value < 30:
                details.append("RSI oversold")
            elif 30 <= rsi_value <= 50:
                details.append("RSI healthy bullish range")
            interpretation += ", ".join(details) if details else "Multiple bullish signals"
        elif momentum_score >= 0.2:
            interpretation = "Moderate bullish momentum: Mixed signals with bullish bias"
        elif momentum_score >= -0.2:
            interpretation = "Neutral momentum: Balanced or consolidating"
        elif momentum_score >= -0.6:
            interpretation = "Moderate bearish momentum: Mixed signals with bearish bias"
        else:
            interpretation = "Strong bearish momentum: "
            details = []
            if elder_impulse == "red":
                details.append("Elder Impulse red")
            if elder_force < 0:
                details.append("negative Force Index")
            if rsi_value > 70:
                details.append("RSI overbought")
            interpretation += ", ".join(details) if details else "Multiple bearish signals"

        result = {
            "momentum_score": round(momentum_score, 2),
            "indicators": indicators,
            "signals": signals,
            "interpretation": interpretation
        }

        # Format text output
        analysis_text = f"""Momentum Analysis for {symbol} ({timeframe}):

Momentum Score: {momentum_score:.2f} / 1.00 (bearish to bullish: -1.0 to 1.0)

Indicators:
  RSI (14): {rsi_value:.2f}
  Stochastic %K: {stoch_k:.2f}
  Stochastic %D: {stoch_d:.2f}
  Elder Force Index (13): {elder_force:.2f}

Elder Impulse System:
  Elder Impulse: {elder_impulse.upper()}
  EMA (13): {ema_13_value:.2f} - {ema_13_direction}
  MACD Histogram: {macd_hist_value:.4f} - {macd_hist_direction}

Signals: {', '.join(signals)}

Interpretation: {interpretation}
"""

        return {
            "content": [{"type": "text", "text": analysis_text}],
            **result
        }

    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Error in momentum analysis: {str(e)}"}],
            "is_error": True
        }

@tool(
    name="analyze_volatility",
    description="Analyze volatility using ATR and Bollinger Bands",
    input_schema={
        "ohlcv_data": list,
        "symbol": str,
        "timeframe": str
    }
)
async def analyze_volatility(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate volatility indicators: ATR, ATR%, Bollinger Bands.
    Returns volatility score (0.0-1.0) based on ATR% and BB Width%.
    """
    try:
        ohlcv_data = args.get("ohlcv_data", [])
        symbol = args.get("symbol", "Unknown")
        timeframe = args.get("timeframe", "Unknown")

        if not ohlcv_data:
            return {
                "content": [{"type": "text", "text": "No OHLCV data provided"}],
                "is_error": True
            }

        # Convert to DataFrame
        df = pd.DataFrame(ohlcv_data)

        # Check for sufficient data (need at least 20 periods for Bollinger Bands)
        min_required = 20
        if len(df) < min_required:
            return {
                "content": [{"type": "text", "text": f"Insufficient data: need at least {min_required} periods, got {len(df)}"}],
                "is_error": True
            }

        # Calculate ATR (14-period)
        df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=14)

        # Calculate Bollinger Bands (20-period, 2 std dev)
        bbands = ta.bbands(df['close'], length=20, std=2)
        if bbands is not None:
            # pandas-ta column names may vary by version, try different formats
            try:
                df['bb_upper'] = bbands['BBU_20_2.0_2.0']
                df['bb_middle'] = bbands['BBM_20_2.0_2.0']
                df['bb_lower'] = bbands['BBL_20_2.0_2.0']
            except KeyError:
                df['bb_upper'] = bbands['BBU_20_2.0']
                df['bb_middle'] = bbands['BBM_20_2.0']
                df['bb_lower'] = bbands['BBL_20_2.0']

        # Get latest values
        latest = df.iloc[-1]

        # Extract values and check for NaN
        atr_value = float(latest['atr']) if pd.notna(latest['atr']) else None
        bb_upper = float(latest['bb_upper']) if pd.notna(latest['bb_upper']) else None
        bb_middle = float(latest['bb_middle']) if pd.notna(latest['bb_middle']) else None
        bb_lower = float(latest['bb_lower']) if pd.notna(latest['bb_lower']) else None
        current_price = float(latest['close'])

        # Check for insufficient calculated data
        if any(val is None for val in [atr_value, bb_upper, bb_middle, bb_lower]):
            return {
                "content": [{"type": "text", "text": "Insufficient data for volatility calculation (NaN values in indicators)"}],
                "is_error": True
            }

        # Calculate derived metrics
        atr_percent = (atr_value / current_price) * 100
        bb_width = bb_upper - bb_lower
        bb_width_percent = (bb_width / bb_middle) * 100

        # Calculate volatility score (0.0 to 1.0)

        # 1. ATR% contribution (0.5 weight)
        atr_score = 0.0
        if atr_percent < 0.5:
            atr_score = 0.1  # Very low volatility
        elif atr_percent < 1.0:
            atr_score = 0.3  # Low volatility
        elif atr_percent < 2.0:
            atr_score = 0.5  # Normal volatility
        elif atr_percent < 3.0:
            atr_score = 0.7  # High volatility
        else:
            atr_score = 0.9  # Very high volatility

        # 2. BB Width% contribution (0.5 weight)
        bb_score = 0.0
        if bb_width_percent < 2.0:
            bb_score = 0.2  # Squeeze/low volatility
        elif bb_width_percent < 4.0:
            bb_score = 0.5  # Normal
        else:
            bb_score = 0.8  # Expansion/high volatility

        # Calculate final volatility score
        volatility_score = (atr_score * 0.5) + (bb_score * 0.5)

        # Generate signals
        signals = []

        # Volatility level signal
        if volatility_score >= 0.7:
            signals.append("high_volatility")
        elif volatility_score <= 0.35:
            signals.append("low_volatility")
        else:
            signals.append("normal_volatility")

        # BB squeeze signal
        if bb_width_percent < 2.0:
            signals.append("bb_squeeze")

        # Price position relative to Bollinger Bands
        # Calculate distances from bands as percentage of middle band
        distance_to_upper = ((bb_upper - current_price) / bb_middle) * 100
        distance_to_lower = ((current_price - bb_lower) / bb_middle) * 100

        if distance_to_upper < 1.0:
            signals.append("price_near_bb_upper")
        elif distance_to_lower < 1.0:
            signals.append("price_near_bb_lower")
        else:
            signals.append("price_in_bb_middle")

        # Build indicators dictionary
        indicators = {
            "atr": round(atr_value, 2),
            "atr_percent": round(atr_percent, 2),
            "bb_upper": round(bb_upper, 2),
            "bb_middle": round(bb_middle, 2),
            "bb_lower": round(bb_lower, 2),
            "bb_width": round(bb_width, 2),
            "bb_width_percent": round(bb_width_percent, 2),
            "current_price": round(current_price, 2)
        }

        # Generate interpretation
        volatility_level = "high" if volatility_score >= 0.7 else "low" if volatility_score <= 0.35 else "moderate"

        interpretation_parts = [f"{volatility_level.capitalize()} volatility"]

        if "bb_squeeze" in signals:
            interpretation_parts.append("BB squeeze detected (potential breakout setup)")

        if "price_near_bb_upper" in signals:
            interpretation_parts.append("price near upper Bollinger Band (potential resistance)")
        elif "price_near_bb_lower" in signals:
            interpretation_parts.append("price near lower Bollinger Band (potential support/bounce)")
        else:
            interpretation_parts.append("price in middle of Bollinger Bands")

        interpretation = ", ".join(interpretation_parts)

        result = {
            "volatility_score": round(volatility_score, 2),
            "indicators": indicators,
            "signals": signals,
            "interpretation": interpretation
        }

        # Format text output
        analysis_text = f"""Volatility Analysis for {symbol} ({timeframe}):

Volatility Score: {volatility_score:.2f} / 1.00

ATR Indicators:
  ATR (14): {atr_value:.2f}
  ATR Percentage: {atr_percent:.2f}%

Bollinger Bands:
  Upper Band: {bb_upper:.2f}
  Middle Band: {bb_middle:.2f}
  Lower Band: {bb_lower:.2f}
  BB Width: {bb_width:.2f}
  BB Width %: {bb_width_percent:.2f}%

Current Price: {current_price:.2f}

Signals: {', '.join(signals)}

Interpretation: {interpretation}
"""

        return {
            "content": [{"type": "text", "text": analysis_text}],
            **result
        }

    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Error in volatility analysis: {str(e)}"}],
            "is_error": True
        }

@tool(
    name="analyze_patterns",
    description="Analyze price patterns using Fibonacci retracements and extensions",
    input_schema={
        "ohlcv_data": list,
        "symbol": str,
        "timeframe": str,
        "lookback_periods": int
    }
)
async def analyze_patterns(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate Fibonacci retracement and extension levels based on recent swing high/low.
    Identifies support/resistance levels and generates trading signals.
    """
    try:
        ohlcv_data = args.get("ohlcv_data", [])
        symbol = args.get("symbol", "Unknown")
        timeframe = args.get("timeframe", "Unknown")
        lookback_periods = args.get("lookback_periods", 50)  # Default to 50

        if not ohlcv_data:
            return {
                "content": [{"type": "text", "text": "No OHLCV data provided"}],
                "is_error": True
            }

        # Convert to DataFrame
        df = pd.DataFrame(ohlcv_data)

        # Check for sufficient data
        if len(df) < lookback_periods:
            return {
                "content": [{"type": "text", "text": f"Insufficient data: need at least {lookback_periods} periods, got {len(df)}"}],
                "is_error": True
            }

        # Find swing high and low in last N periods
        swing_high = df['high'].tail(lookback_periods).max()
        swing_low = df['low'].tail(lookback_periods).min()
        swing_range = swing_high - swing_low

        # Check for valid swing range
        if swing_range == 0:
            return {
                "content": [{"type": "text", "text": "Invalid swing range: swing high equals swing low"}],
                "is_error": True
            }

        # Calculate Fibonacci retracement levels
        fib_levels = {
            "0.0": float(swing_low),
            "23.6": float(swing_low + (swing_range * 0.236)),
            "38.2": float(swing_low + (swing_range * 0.382)),
            "50.0": float(swing_low + (swing_range * 0.500)),
            "61.8": float(swing_low + (swing_range * 0.618)),
            "78.6": float(swing_low + (swing_range * 0.786)),
            "100.0": float(swing_high),
            "127.2": float(swing_high + (swing_range * 0.272)),  # Extension
            "161.8": float(swing_high + (swing_range * 0.618))   # Extension
        }

        # Get current price
        current_price = float(df['close'].iloc[-1])

        # Find closest Fibonacci level to current price
        closest_level = min(fib_levels.items(), key=lambda x: abs(x[1] - current_price))
        closest_level_name = closest_level[0]
        closest_level_price = closest_level[1]

        # Calculate distance to closest level
        distance_to_level = abs(current_price - closest_level_price)
        distance_percent = (distance_to_level / current_price) * 100

        # Separate support and resistance levels
        support_levels = [price for level, price in sorted(fib_levels.items(), key=lambda x: float(x[0]))
                         if price < current_price]
        resistance_levels = [price for level, price in sorted(fib_levels.items(), key=lambda x: float(x[0]))
                            if price > current_price]

        # Generate signals
        signals = []

        # Check if near any Fibonacci level (within 1%)
        for level_name, level_price in fib_levels.items():
            if abs(current_price - level_price) / current_price <= 0.01:
                signals.append(f"near_fib_{level_name.replace('.', '')}")
                break

        # Check between which levels price is
        sorted_levels = sorted(fib_levels.items(), key=lambda x: x[1])
        for i in range(len(sorted_levels) - 1):
            lower_level = sorted_levels[i]
            upper_level = sorted_levels[i + 1]
            if lower_level[1] <= current_price <= upper_level[1]:
                lower_name = lower_level[0].replace('.', '')
                upper_name = upper_level[0].replace('.', '')
                signals.append(f"between_{lower_name}_{upper_name}")
                break

        # Determine if bullish or bearish retracement
        distance_from_low = current_price - swing_low
        distance_from_high = swing_high - current_price

        if distance_from_low < distance_from_high:
            signals.append("bullish_retracement")
            retracement_type = "bullish"
        else:
            signals.append("bearish_retracement")
            retracement_type = "bearish"

        # Generate interpretation
        position_desc = f"at {closest_level_name}% retracement" if distance_percent < 1.0 else f"near {closest_level_name}% level"

        if retracement_type == "bullish":
            interpretation = f"Price {position_desc}, potential support zone. "
            if support_levels:
                nearest_support = support_levels[-1]
                interpretation += f"Next support at {nearest_support:.2f}."
        else:
            interpretation = f"Price {position_desc}, potential resistance zone. "
            if resistance_levels:
                nearest_resistance = resistance_levels[0]
                interpretation += f"Next resistance at {nearest_resistance:.2f}."

        # Build result
        result = {
            "fib_levels": fib_levels,
            "current_price": current_price,
            "swing_high": float(swing_high),
            "swing_low": float(swing_low),
            "swing_range": float(swing_range),
            "current_level": closest_level_name,
            "distance_to_level": round(distance_to_level, 2),
            "distance_percent": round(distance_percent, 2),
            "support_levels": support_levels,
            "resistance_levels": resistance_levels,
            "signals": signals,
            "interpretation": interpretation
        }

        # Format text output
        analysis_text = f"""Pattern Analysis for {symbol} ({timeframe}):

Fibonacci Retracement Levels (lookback: {lookback_periods} periods):
  Swing High: {swing_high:.2f}
  Swing Low:  {swing_low:.2f}
  Range:      {swing_range:.2f}

Retracement Levels:
  0.0%   (Swing Low):  {fib_levels['0.0']:.2f}
  23.6%:               {fib_levels['23.6']:.2f}
  38.2%:               {fib_levels['38.2']:.2f}
  50.0%:               {fib_levels['50.0']:.2f}
  61.8%:               {fib_levels['61.8']:.2f}
  78.6%:               {fib_levels['78.6']:.2f}
  100.0% (Swing High): {fib_levels['100.0']:.2f}

Extension Levels:
  127.2%:              {fib_levels['127.2']:.2f}
  161.8%:              {fib_levels['161.8']:.2f}

Current Price: {current_price:.2f}
Closest Level: {closest_level_name}% ({closest_level_price:.2f})
Distance: {distance_to_level:.2f} ({distance_percent:.2f}%)

Support Levels ({len(support_levels)}): {', '.join([f'{s:.2f}' for s in support_levels[-3:]])}
Resistance Levels ({len(resistance_levels)}): {', '.join([f'{r:.2f}' for r in resistance_levels[:3]])}

Signals: {', '.join(signals)}

Interpretation: {interpretation}
"""

        return {
            "content": [{"type": "text", "text": analysis_text}],
            **result
        }

    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Error in pattern analysis: {str(e)}"}],
            "is_error": True
        }

@tool(
    name="multi_timeframe_analysis",
    description="Analyze multiple timeframes simultaneously for comprehensive view",
    input_schema={
        "symbol": str,
        "timeframes": list
    }
)
async def multi_timeframe_analysis(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Coordinate analysis across multiple timeframes.
    This tool orchestrates calls to fetch_market_data and analyze_technicals.
    """
    return {
        "content": [{
            "type": "text",
            "text": "Use fetch_market_data and analyze_technicals for each timeframe: " +
                    ", ".join(args.get("timeframes", []))
        }]
    }
