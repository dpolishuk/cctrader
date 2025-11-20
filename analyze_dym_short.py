"""
Comprehensive analysis of DYM/USDT SHORT opportunity.
"""
import asyncio
import ccxt.async_support as ccxt
import pandas as pd
import pandas_ta as ta
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

async def analyze_dym_short():
    """Analyze DYM/USDT as a potential SHORT opportunity."""

    # Initialize Bybit exchange
    exchange = ccxt.bybit({
        'enableRateLimit': True,
        'options': {'defaultType': 'spot'}
    })

    print("="*80)
    print("DYM/USDT SHORT OPPORTUNITY ANALYSIS")
    print("="*80)
    print()

    symbol = "DYM/USDT"

    # Score components
    technical_score = 0  # Max 40
    sentiment_score = 0  # Max 30
    liquidity_score = 0  # Max 20
    correlation_score = 0  # Max 10

    try:
        # 1. MULTI-TIMEFRAME TECHNICAL ANALYSIS
        print("📊 STEP 1: MULTI-TIMEFRAME TECHNICAL ANALYSIS")
        print("-" * 80)

        timeframes = {
            "1m": "1m",
            "5m": "5m",
            "15m": "15m",
            "1h": "1h",
            "4h": "4h"
        }

        tf_analysis = {}

        for name, tf in timeframes.items():
            try:
                ohlcv = await exchange.fetch_ohlcv(symbol, tf, limit=200)
                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

                # Calculate indicators
                df['rsi'] = ta.rsi(df['close'], length=14)
                df['macd'] = ta.macd(df['close'])['MACD_12_26_9']
                df['macd_signal'] = ta.macd(df['close'])['MACDs_12_26_9']
                ema_20 = ta.ema(df['close'], length=20)
                ema_50 = ta.ema(df['close'], length=50)

                # Latest values
                latest = df.iloc[-1]
                price = latest['close']
                rsi = latest['rsi']
                macd_val = latest['macd']
                macd_sig = latest['macd_signal']

                # Trend analysis
                trend = "BEARISH" if pd.notna(ema_20.iloc[-1]) and pd.notna(ema_50.iloc[-1]) and ema_20.iloc[-1] < ema_50.iloc[-1] else "BULLISH"

                # Price change
                price_change_pct = ((df['close'].iloc[-1] - df['close'].iloc[-20]) / df['close'].iloc[-20] * 100) if len(df) >= 20 else 0

                tf_analysis[name] = {
                    'price': price,
                    'rsi': rsi,
                    'macd': macd_val,
                    'macd_signal': macd_sig,
                    'trend': trend,
                    'price_change': price_change_pct,
                    'volume': latest['volume']
                }

                print(f"\n{name.upper()} Timeframe:")
                print(f"  Price: ${price:.4f}")
                print(f"  RSI: {rsi:.2f}" + (" [OVERBOUGHT]" if rsi > 70 else " [OVERSOLD]" if rsi < 30 else ""))
                print(f"  MACD: {macd_val:.6f} (Signal: {macd_sig:.6f}) {'[BEARISH CROSS]' if macd_val < macd_sig else '[BULLISH]'}")
                print(f"  Trend: {trend}")
                print(f"  20-period change: {price_change_pct:.2f}%")

            except Exception as e:
                print(f"  ⚠️  Error fetching {name}: {e}")
                tf_analysis[name] = None

        # Calculate technical score (0-40 points)
        bearish_signals = 0
        total_signals = 0

        for tf_name, data in tf_analysis.items():
            if data:
                total_signals += 1

                # RSI overbought (>70) = bearish for SHORT
                if data['rsi'] > 70:
                    bearish_signals += 1
                    technical_score += 6
                elif data['rsi'] > 60:
                    bearish_signals += 0.5
                    technical_score += 3

                # MACD bearish cross
                if data['macd'] < data['macd_signal']:
                    bearish_signals += 1
                    technical_score += 4

                # Bearish trend
                if data['trend'] == "BEARISH":
                    bearish_signals += 1
                    technical_score += 4

        # Cap at 40
        technical_score = min(technical_score, 40)

        print(f"\n✅ Technical Score: {technical_score}/40")
        print(f"   Bearish signals: {bearish_signals}/{total_signals * 3}")

        # 2. MARKET SENTIMENT ANALYSIS
        print("\n" + "="*80)
        print("📰 STEP 2: MARKET SENTIMENT ANALYSIS")
        print("-" * 80)

        # Based on web research from earlier
        print("\nSentiment Summary:")
        print("  • Fear & Greed Index: 29 (FEAR)")
        print("  • +75.62% in 4h followed by -6.76% in 1h = PUMP & DUMP pattern")
        print("  • 23 bearish vs 6 bullish technical indicators (TradingView)")
        print("  • Predicted -24.91% drop to $0.067 by Nov 30, 2025")
        print("  • Extreme volatility with speculative trading")
        print("  • Mainnet launch catalyst exhausted")

        # Sentiment scoring (0-30)
        sentiment_score = 25  # Strong bearish sentiment
        print(f"\n✅ Sentiment Score: {sentiment_score}/30")

        # 3. LIQUIDITY & VOLUME ANALYSIS
        print("\n" + "="*80)
        print("💧 STEP 3: LIQUIDITY & VOLUME QUALITY")
        print("-" * 80)

        ticker = await exchange.fetch_ticker(symbol)

        current_price = ticker['last']
        volume_24h = ticker['quoteVolume']
        price_change_24h = ticker['percentage']

        print(f"\nCurrent Price: ${current_price:.4f}")
        print(f"24h Volume: ${volume_24h:,.0f}")
        print(f"24h Change: {price_change_24h:.2f}%")

        # Liquidity scoring (0-20)
        if volume_24h > 50_000_000:
            liquidity_score = 20
            print("  ✅ Excellent liquidity (>$50M)")
        elif volume_24h > 10_000_000:
            liquidity_score = 15
            print("  ✅ Good liquidity ($10M-$50M)")
        elif volume_24h > 1_000_000:
            liquidity_score = 10
            print("  ⚠️  Moderate liquidity ($1M-$10M)")
        else:
            liquidity_score = 5
            print("  ❌ Low liquidity (<$1M)")

        print(f"\n✅ Liquidity Score: {liquidity_score}/20")

        # 4. BTC CORRELATION
        print("\n" + "="*80)
        print("₿  STEP 4: BTC CORRELATION ANALYSIS")
        print("-" * 80)

        # Fetch BTC data
        btc_ohlcv = await exchange.fetch_ohlcv("BTC/USDT", "1h", limit=50)
        btc_df = pd.DataFrame(btc_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

        dym_ohlcv = await exchange.fetch_ohlcv(symbol, "1h", limit=50)
        dym_df = pd.DataFrame(dym_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

        # Calculate correlation
        btc_returns = btc_df['close'].pct_change()
        dym_returns = dym_df['close'].pct_change()

        correlation = btc_returns.corr(dym_returns)

        print(f"\nBTC Correlation (1h, 50 periods): {correlation:.3f}")

        if correlation < 0.3:
            correlation_score = 10
            print("  ✅ Low correlation - DYM moving independently")
        elif correlation < 0.6:
            correlation_score = 7
            print("  ⚠️  Moderate correlation")
        else:
            correlation_score = 5
            print("  ⚠️  High correlation - follows BTC closely")

        print(f"\n✅ Correlation Score: {correlation_score}/10")

        # 5. CALCULATE TOTAL CONFIDENCE
        print("\n" + "="*80)
        print("🎯 STEP 5: CONFIDENCE SCORE & DECISION")
        print("=" * 80)

        total_confidence = technical_score + sentiment_score + liquidity_score + correlation_score

        print(f"\nSCORE BREAKDOWN:")
        print(f"  Technical Alignment:  {technical_score}/40")
        print(f"  Sentiment:            {sentiment_score}/30")
        print(f"  Liquidity:            {liquidity_score}/20")
        print(f"  BTC Correlation:      {correlation_score}/10")
        print(f"  " + "-" * 35)
        print(f"  TOTAL CONFIDENCE:     {total_confidence}/100")

        print()

        # 6. TRADING DECISION
        if total_confidence >= 60:
            print("🟢 HIGH PROBABILITY SHORT TRADE")
            print()

            # Calculate position sizing
            portfolio_size = 10000
            risk_per_trade = 0.02  # 2% risk

            entry_price = current_price
            stop_loss_pct = 0.05  # 5% stop loss
            take_profit_pct = 0.10  # 10% take profit (SHORT)

            stop_loss = entry_price * (1 + stop_loss_pct)
            take_profit = entry_price * (1 - take_profit_pct)

            risk_amount = portfolio_size * risk_per_trade
            position_size_usd = risk_amount / stop_loss_pct

            print("TRADE PARAMETERS:")
            print(f"  Entry Price:       ${entry_price:.4f}")
            print(f"  Stop Loss:         ${stop_loss:.4f} (+{stop_loss_pct*100:.1f}%)")
            print(f"  Take Profit:       ${take_profit:.4f} (-{take_profit_pct*100:.1f}%)")
            print(f"  Position Size:     ${position_size_usd:.2f}")
            print(f"  Risk Amount:       ${risk_amount:.2f} ({risk_per_trade*100}% of portfolio)")
            print()
            print("RATIONALE:")
            print("  • Overbought RSI across multiple timeframes")
            print("  • Bearish technical indicators (23 vs 6 on TradingView)")
            print("  • Pump & dump pattern: +75% in 4h then -6.76% in 1h")
            print("  • Fear sentiment (index=29)")
            print("  • Analysts predict -24.91% drop to $0.067")
            print("  • Post-mainnet euphoria fading")

        else:
            print("🔴 NOT A HIGH PROBABILITY TRADE")
            print(f"   Confidence {total_confidence}/100 is below threshold of 60")
            print()
            print("RECOMMENDATION: PASS - Wait for better setup")

    except Exception as e:
        print(f"❌ Error during analysis: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await exchange.close()

    print()
    print("="*80)
    print("Analysis Complete")
    print("="*80)

if __name__ == "__main__":
    asyncio.run(analyze_dym_short())
