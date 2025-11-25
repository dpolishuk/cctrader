# Multi-Agent Trading Pipeline Design

**Date:** 2025-01-25
**Status:** Approved

## Overview

Redesign the CCTrader system from a single-agent architecture to a sequential multi-agent pipeline with four specialized Claude agents:

1. **Analysis Agent** - Market analysis and signal generation
2. **Risk Auditor Agent** - Independent risk review with full authority
3. **Execution Agent** - Smart conditional order execution
4. **P&L Auditor Agent** - Trade review and performance insights

## Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                        MARKET MOVERS SCANNER (Python)                        │
│                    Detects momentum > threshold, triggers pipeline           │
└──────────────────────────────────────────────┬───────────────────────────────┘
                                               │ Symbol + Momentum Data
                                               ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                         ANALYSIS AGENT (Claude API #1)                       │
│  Tools: fetch_market_data, technical_analysis, sentiment_search              │
│  Output: AnalysisReport + ProposedSignal (JSON)                              │
└──────────────────────────────────────────────┬───────────────────────────────┘
                                               │ AnalysisReport + ProposedSignal
                                               ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                        RISK AUDITOR AGENT (Claude API #2)                    │
│  Tools: get_portfolio_state, get_open_positions, check_correlation           │
│  Output: RiskDecision (APPROVE/REJECT/MODIFY) + AuditedSignal (JSON)         │
└──────────────────────────────────────────────┬───────────────────────────────┘
                                               │ AuditedSignal (if approved)
                                               ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                        EXECUTION AGENT (Claude API #3)                       │
│  Tools: get_orderbook, place_limit_order, place_market_order, cancel_order   │
│  Output: ExecutionReport (filled/partial/aborted) (JSON)                     │
└──────────────────────────────────────────────┬───────────────────────────────┘
                                               │ ExecutionReport
                                               ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                        P&L AUDITOR AGENT (Claude API #4)                     │
│  Tools: get_trade_history, get_market_context, calculate_metrics             │
│  Output: TradeReview (per-trade) or DailyReport (batch)                      │
└──────────────────────────────────────────────────────────────────────────────┘
                                               │
                                               ▼
                                      ┌─────────────────┐
                                      │    DATABASE     │
                                      │  (Audit Trail)  │
                                      └─────────────────┘
```

**Key design decisions:**
- Each agent is a separate Claude API call with dedicated prompt and tools
- Agents pass structured JSON to next stage
- Every agent output is persisted to database for audit trail
- Pipeline can short-circuit (Risk Auditor rejects → skip Execution)
- Data flow: JSON for real-time, database for persistence

---

## Agent 1: Analysis Agent

**Purpose:** Gather market data, perform technical and sentiment analysis, produce a proposed trading signal.

**Prompt Strategy:**
```
You are a Market Analysis Agent. Your job is to analyze {symbol} and determine
if there's a trading opportunity.

You have access to tools for:
- Multi-timeframe technical analysis (1m, 5m, 15m, 1h, 4h)
- Sentiment analysis via web search
- Current price and volume data

Your output must be structured JSON with two parts:
1. AnalysisReport - raw scores and findings
2. ProposedSignal - your trade recommendation (or "NO_TRADE")
```

**Tools:**
| Tool | Purpose |
|------|---------|
| `fetch_technical_snapshot` | Multi-timeframe TA (trend, momentum, volatility, patterns) |
| `fetch_sentiment_data` | Web search for news/catalysts |
| `get_current_price` | Real-time price and volume |
| `get_btc_correlation` | Correlation with BTC movement |

**Output Schema:**
```json
{
  "analysis_report": {
    "symbol": "MONUSDT",
    "timestamp": "2025-01-25T10:30:00Z",
    "technical": {
      "trend_score": 0.85,
      "momentum_score": 0.42,
      "volatility": "high",
      "key_levels": { "support": 0.038, "resistance": 0.045 }
    },
    "sentiment": {
      "score": 0.65,
      "catalysts": ["Project launch announcement"],
      "news_summary": "..."
    },
    "liquidity": { "volume_24h": 87000000, "spread_pct": 0.12 },
    "btc_correlation": 0.72
  },
  "proposed_signal": {
    "direction": "LONG",
    "confidence": 72,
    "entry_price": 0.0407,
    "stop_loss": 0.0366,
    "take_profit": 0.0472,
    "position_size_pct": 4.0,
    "reasoning": "Strong uptrend across timeframes, bullish momentum..."
  }
}
```

**NO_TRADE conditions:**
- Confidence below 50
- Conflicting timeframe signals
- No clear catalyst or technical setup

---

## Agent 2: Risk Auditor Agent

**Purpose:** Independent risk assessment with full authority to approve, reject, or modify signals.

**Prompt Strategy:**
```
You are a Risk Auditor Agent. Your job is to protect the portfolio from excessive risk.

You receive:
- Analysis report and proposed signal from Analysis Agent
- Current portfolio state (positions, exposure, P&L)

You have FULL AUTHORITY to:
- APPROVE: Signal passes all risk checks
- REJECT: Signal violates risk limits or is too risky
- MODIFY: Adjust position size, stop-loss, or take-profit

Be conservative. When in doubt, reject or reduce size.
```

**Tools:**
| Tool | Purpose |
|------|---------|
| `get_portfolio_state` | Current equity, exposure %, daily/weekly P&L |
| `get_open_positions` | List of current positions with unrealized P&L |
| `check_correlation_group` | How many positions in same correlation group |
| `get_risk_config` | Current risk limits (max exposure, max positions, etc.) |
| `calculate_position_risk` | Compute risk metrics for proposed trade |

**Risk Checks:**
1. Confidence threshold - Reject if below 60
2. Position limit - Reject if already at max positions
3. Exposure limit - Modify size if would exceed max exposure
4. Daily loss limit - Reject all trades if daily loss exceeded
5. Weekly loss limit - Reject all trades if weekly loss exceeded
6. Correlation limit - Reject if too many positions in same group
7. Risk/reward ratio - Modify if R:R below 1.5
8. Stop-loss validity - Reject if stop-loss too tight or too wide

**Output Schema (Approved/Modified):**
```json
{
  "risk_decision": {
    "action": "MODIFY",
    "original_confidence": 72,
    "audited_confidence": 68,
    "modifications": [
      "Reduced position size from 4% to 2.5% due to existing exposure",
      "Tightened stop-loss from 0.0366 to 0.0375 for better R:R"
    ],
    "warnings": [
      "Portfolio has 3 altcoin positions - consider diversification"
    ],
    "risk_score": 35
  },
  "audited_signal": {
    "direction": "LONG",
    "confidence": 68,
    "entry_price": 0.0407,
    "stop_loss": 0.0375,
    "take_profit": 0.0472,
    "position_size_pct": 2.5,
    "reasoning": "Approved with modifications..."
  },
  "portfolio_snapshot": {
    "equity": 10000,
    "open_positions": 3,
    "current_exposure_pct": 15.0,
    "daily_pnl_pct": -1.2,
    "weekly_pnl_pct": 3.5
  }
}
```

**Output Schema (Rejected):**
```json
{
  "risk_decision": {
    "action": "REJECT",
    "reason": "Daily loss limit of -5% reached. No new trades allowed today.",
    "risk_score": 90
  },
  "audited_signal": null,
  "portfolio_snapshot": { ... }
}
```

---

## Agent 3: Execution Agent

**Purpose:** Smart conditional order execution with ability to use limit orders, wait for better prices, or abort.

**Prompt Strategy:**
```
You are an Execution Agent. Your job is to execute the audited signal optimally.

You receive:
- Audited signal from Risk Auditor (already risk-approved)
- Current market conditions

You can:
- Execute immediately with market order
- Place limit order and wait for fill
- Split into multiple smaller orders
- ABORT if market has moved significantly against the entry

Your goal: Best execution price while ensuring the trade gets filled.
```

**Tools:**
| Tool | Purpose |
|------|---------|
| `get_current_price` | Real-time bid/ask/last price |
| `get_orderbook_depth` | Order book snapshot (bids/asks) |
| `place_market_order` | Execute at market price |
| `place_limit_order` | Place limit order at specified price |
| `check_order_status` | Check if limit order filled |
| `cancel_order` | Cancel unfilled limit order |
| `get_spread_info` | Current spread and slippage estimate |

**Execution Logic:**
1. Check current price vs entry - If price moved >1% against, consider abort
2. Assess spread - If spread >0.5%, use limit order
3. Check order book depth - If thin liquidity, split order
4. Execute - Market or limit based on conditions
5. Monitor - For limit orders, wait up to N seconds then decide

**Abort Conditions:**
- Price moved >2% away from intended entry
- Spread exceeds 1%
- Order book too thin (would cause >1% slippage)
- Limit order not filled within timeout

**Output Schema (Success):**
```json
{
  "execution_report": {
    "status": "FILLED",
    "order_type": "LIMIT",
    "requested_entry": 0.0407,
    "actual_entry": 0.0405,
    "slippage_pct": -0.49,
    "position_size": 250.0,
    "position_value_usd": 101.25,
    "execution_time_ms": 1250,
    "order_id": "ORD-12345",
    "notes": "Limit order filled at better price than requested"
  },
  "position_opened": {
    "symbol": "MONUSDT",
    "direction": "LONG",
    "entry_price": 0.0405,
    "stop_loss": 0.0375,
    "take_profit": 0.0472,
    "size": 250.0,
    "opened_at": "2025-01-25T10:31:15Z"
  }
}
```

**Output Schema (Aborted):**
```json
{
  "execution_report": {
    "status": "ABORTED",
    "reason": "Price moved 2.3% above entry.",
    "requested_entry": 0.0407,
    "current_price": 0.0416,
    "price_deviation_pct": 2.3
  },
  "position_opened": null
}
```

---

## Agent 4: P&L Auditor Agent

**Purpose:** Review trade performance and identify patterns. Runs per-trade (quick) and daily (batch).

**Prompt Strategy:**
```
You are a P&L Auditor Agent. Your job is to review trading performance and
identify what's working and what's not.

Two modes:
1. TRADE_REVIEW: Analyze a single closed trade immediately after it closes
2. DAILY_REPORT: Batch analysis of all trades from the day

Provide actionable insights, not just statistics.
```

**Tools:**
| Tool | Purpose |
|------|---------|
| `get_trade_details` | Full details of a specific trade |
| `get_trade_history` | List of trades for a period |
| `get_market_context` | What was happening in market during trade |
| `calculate_metrics` | Win rate, avg P&L, Sharpe, drawdown, etc. |
| `get_signal_accuracy` | Compare original signals vs outcomes |
| `get_agent_performance` | How accurate was each agent's assessment |

**Per-Trade Review Output:**
```json
{
  "trade_review": {
    "trade_id": "TRD-789",
    "symbol": "MONUSDT",
    "direction": "LONG",
    "entry_price": 0.0405,
    "exit_price": 0.0468,
    "pnl_pct": 15.56,
    "pnl_usd": 15.75,
    "duration_hours": 4.2,
    "result": "WIN"
  },
  "analysis": {
    "what_worked": [
      "Technical analysis correctly identified strong uptrend",
      "Entry timing was good - filled near local low"
    ],
    "what_didnt_work": [
      "Take-profit was conservative - left money on table"
    ],
    "agent_accuracy": {
      "analysis_agent_confidence": 72,
      "risk_auditor_confidence": 68,
      "actual_outcome": "WIN",
      "assessment": "Both agents correctly identified opportunity"
    }
  },
  "recommendation": "Consider using trailing stop for strong momentum trades"
}
```

**Daily Report Output:**
```json
{
  "daily_report": {
    "date": "2025-01-25",
    "summary": {
      "total_trades": 8,
      "wins": 5,
      "losses": 3,
      "win_rate": 62.5,
      "total_pnl_pct": 4.2,
      "total_pnl_usd": 420.0,
      "best_trade": { "symbol": "MONUSDT", "pnl_pct": 15.56 },
      "worst_trade": { "symbol": "TNSR", "pnl_pct": -8.2 }
    },
    "patterns_identified": [
      {
        "pattern": "High sentiment score trades outperforming",
        "evidence": "Trades with sentiment >20 had 80% win rate vs 40% for <20",
        "recommendation": "Weight sentiment score higher in confidence calculation"
      }
    ],
    "agent_performance": {
      "analysis_agent": { "signals_generated": 12, "accuracy": 58.3 },
      "risk_auditor": { "approved": 8, "rejected": 3, "modified": 1 },
      "execution_agent": { "filled": 8, "aborted": 0, "avg_slippage_pct": -0.12 }
    }
  },
  "strategy_recommendations": [
    "Risk Auditor rejections are adding value - 67% accurate",
    "Execution Agent achieving negative slippage - limit orders working"
  ]
}
```

---

## Database Schema

```sql
-- Agent outputs for audit trail
CREATE TABLE agent_outputs (
    id INTEGER PRIMARY KEY,
    session_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    agent_type TEXT NOT NULL,  -- 'analysis', 'risk_auditor', 'execution', 'pnl_auditor'
    input_json TEXT,
    output_json TEXT,
    tokens_used INTEGER,
    duration_ms INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Risk decisions
CREATE TABLE risk_decisions (
    id INTEGER PRIMARY KEY,
    session_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    action TEXT NOT NULL,      -- 'APPROVE', 'REJECT', 'MODIFY'
    original_confidence INTEGER,
    audited_confidence INTEGER,
    modifications TEXT,
    warnings TEXT,
    risk_score INTEGER,
    portfolio_snapshot TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Execution reports
CREATE TABLE execution_reports (
    id INTEGER PRIMARY KEY,
    session_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    status TEXT NOT NULL,      -- 'FILLED', 'PARTIAL', 'ABORTED'
    order_type TEXT,
    requested_entry REAL,
    actual_entry REAL,
    slippage_pct REAL,
    position_size REAL,
    execution_time_ms INTEGER,
    abort_reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Trade reviews
CREATE TABLE trade_reviews (
    id INTEGER PRIMARY KEY,
    trade_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    pnl_pct REAL,
    pnl_usd REAL,
    result TEXT,
    what_worked TEXT,
    what_didnt_work TEXT,
    recommendation TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Daily reports
CREATE TABLE daily_reports (
    id INTEGER PRIMARY KEY,
    report_date DATE NOT NULL UNIQUE,
    total_trades INTEGER,
    wins INTEGER,
    losses INTEGER,
    win_rate REAL,
    total_pnl_pct REAL,
    total_pnl_usd REAL,
    patterns_json TEXT,
    recommendations_json TEXT,
    agent_performance_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## File Structure

```
src/agent/
├── main.py                      # Add new CLI commands
├── config.py                    # Add agent-specific config
│
├── agents/                      # NEW: Agent definitions
│   ├── __init__.py
│   ├── base_agent.py            # Base class for all agents
│   ├── analysis_agent.py
│   ├── risk_auditor_agent.py
│   ├── execution_agent.py
│   └── pnl_auditor_agent.py
│
├── agents/prompts/              # NEW: Agent prompts
│   ├── analysis_prompt.py
│   ├── risk_auditor_prompt.py
│   ├── execution_prompt.py
│   └── pnl_auditor_prompt.py
│
├── agents/tools/                # NEW: Agent-specific tools
│   ├── analysis_tools.py
│   ├── risk_tools.py
│   ├── execution_tools.py
│   └── pnl_tools.py
│
├── agents/schemas.py            # NEW: Pydantic models for JSON schemas
│
├── pipeline/                    # NEW: Pipeline orchestration
│   ├── __init__.py
│   ├── orchestrator.py
│   └── pipeline_config.py
│
├── scanner/
│   └── main_loop.py             # MODIFY: Call pipeline instead of single agent
│
├── database/
│   ├── agent_schema.py          # NEW
│   └── agent_operations.py      # NEW
│
└── tools/                       # EXISTING: Shared tools (keep as-is)
```

---

## Cost & Performance

**Token usage per symbol:**
| Agent | Tokens | Cost @ Sonnet |
|-------|--------|---------------|
| Analysis Agent | ~4,000 | ~$0.012 |
| Risk Auditor | ~2,000 | ~$0.006 |
| Execution Agent | ~1,500 | ~$0.005 |
| P&L Auditor (per-trade) | ~1,500 | ~$0.005 |
| **Total** | **~9,000** | **~$0.028** |

**Comparison:** Current system ~$0.015/trade, new system ~$0.028/trade (~2x cost)

**Latency:** ~25-55 seconds per pipeline run (vs ~15-30 seconds currently)

**Optimizations:**
- Early exit if Analysis Agent outputs NO_TRADE
- Consider Haiku for Risk Auditor (simpler task)
- Skip per-trade P&L review, only daily batch
- Cache portfolio state

---

## Implementation Order

1. Database schema (agent_schema.py, agent_operations.py)
2. Base agent class and schemas
3. Analysis Agent (refactor from current)
4. Risk Auditor Agent
5. Pipeline orchestrator
6. Execution Agent
7. P&L Auditor Agent
8. Integration with main_loop.py
9. CLI commands for reports
