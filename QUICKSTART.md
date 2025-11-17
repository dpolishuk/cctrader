# Quick Start Guide

## Installation

### 1. Automated Installation (Recommended)

```bash
cd /home/deepol/work/cctrader
./install.sh
```

### 2. Manual Installation

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Setup environment
cp .env.example .env
```

## Configuration

Edit `.env` file and add your API keys:

```env
ANTHROPIC_API_KEY=sk-ant-...
BYBIT_API_KEY=your_bybit_key
BYBIT_API_SECRET=your_bybit_secret
BYBIT_TESTNET=false
```

### Getting API Keys

1. **Anthropic API Key**: https://console.anthropic.com/settings/keys
2. **Bybit API**: https://www.bybit.com/app/user/api-management
   - Create a new API key
   - Permissions: Read-only for market data (no trading permissions needed)

## Usage

### Activate Virtual Environment

Always activate before running:
```bash
source venv/bin/activate
```

### Run Single Analysis

```bash
python -m agent.main analyze --symbol BTC/USDT
```

### Start Continuous Monitoring

```bash
python -m agent.main monitor --symbol BTC/USDT --interval 300
```

This will:
- Fetch market data every 5 minutes (300 seconds)
- Perform technical analysis on multiple timeframes
- Query Perplexity for market sentiment
- Generate trading signals
- Save everything to SQLite database

### View Trading Signals

```bash
python -m agent.main signals --symbol BTC/USDT --limit 20
```

### Check Portfolio Status

```bash
python -m agent.main status --symbol BTC/USDT
```

## CLI Commands

```bash
# Help
python -m agent.main --help
python -m agent.main analyze --help

# Different symbols
python -m agent.main analyze --symbol ETH/USDT
python -m agent.main monitor --symbol SOL/USDT --interval 600

# Custom analysis query
python -m agent.main analyze --symbol BTC/USDT "What are the key support and resistance levels?"
```

## What the Agent Does

1. **Fetches Market Data** from Bybit (OHLCV candlesticks)
2. **Calculates Technical Indicators**:
   - RSI (14-period)
   - MACD (12, 26, 9)
   - Bollinger Bands (20, 2)
   - Volume analysis
3. **Analyzes Sentiment** using Perplexity:
   - Recent news events
   - Market sentiment (bullish/bearish/neutral)
   - Regulatory developments
4. **Generates Trading Signals**:
   - Combines technical + sentiment analysis
   - BUY / SELL / HOLD recommendations
   - Confidence scores
5. **Stores Historical Data** in SQLite for analysis

## Database Location

Default: `./trading_data.db`

Contains tables:
- `signals` - Trading signals history
- `technical_analysis` - TA indicators by timeframe
- `sentiment_analysis` - Market sentiment data
- `portfolio_state` - Position tracking

## Troubleshooting

### Import Errors

Make sure virtual environment is activated:
```bash
source venv/bin/activate
```

### API Key Errors

Check `.env` file has correct keys:
```bash
cat .env
```

### CCXT Connection Issues

Try with testnet first:
```env
BYBIT_TESTNET=true
```

### Missing Dependencies

Reinstall:
```bash
pip install -r requirements.txt
```

## Next Steps

1. Run your first analysis
2. Monitor for a few cycles
3. Review signals in database
4. Customize system prompt in `agent/trading_agent.py`
5. Add more timeframes or indicators
6. Integrate with your trading strategy

## Safety Notes

- This agent analyzes markets but does NOT execute trades automatically
- All Bybit API calls are read-only (market data)
- No trading permissions required on Bybit API
- You control all trading decisions

Enjoy your AI-powered trading analysis! 🚀
