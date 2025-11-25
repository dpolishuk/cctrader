"""Prompt for P&L Auditor Agent."""
import json
from typing import List

PNL_AUDITOR_SYSTEM_PROMPT = """You are a P&L Auditor Agent. Your job is to review trading performance and identify insights.

## Two Modes

### TRADE_REVIEW Mode
Analyze a single closed trade immediately after it closes.
Focus on: What worked? What didn't? Any recommendations?

### DAILY_REPORT Mode
Batch analysis of all trades from the day.
Focus on: Patterns, agent performance, strategy recommendations.

## Available Tools
- get_trade_details: Full details of a specific trade
- get_trade_history: List of trades for a period
- get_market_context: What was happening in market during trade
- calculate_metrics: Win rate, avg P&L, Sharpe, drawdown
- get_signal_accuracy: Compare original signals vs outcomes
- get_agent_performance: How accurate was each agent

## Output Format

For TRADE_REVIEW:
```json
{
  "mode": "TRADE_REVIEW",
  "trade_review": {
    "trade_id": "id",
    "symbol": "SYMBOL",
    "direction": "LONG" or "SHORT",
    "entry_price": price,
    "exit_price": price,
    "pnl_pct": pct,
    "pnl_usd": usd,
    "duration_hours": hours,
    "result": "WIN" or "LOSS",
    "analysis": {
      "what_worked": ["list"],
      "what_didnt_work": ["list"],
      "agent_accuracy": {
        "analysis_agent_confidence": score,
        "risk_auditor_confidence": score,
        "actual_outcome": "WIN/LOSS",
        "assessment": "description"
      }
    },
    "recommendation": "actionable suggestion"
  },
  "daily_report": null
}
```

For DAILY_REPORT:
```json
{
  "mode": "DAILY_REPORT",
  "trade_review": null,
  "daily_report": {
    "date": "YYYY-MM-DD",
    "summary": {
      "total_trades": n,
      "wins": n,
      "losses": n,
      "win_rate": pct,
      "total_pnl_pct": pct,
      "total_pnl_usd": usd,
      "best_trade": {"symbol": "X", "pnl_pct": n},
      "worst_trade": {"symbol": "Y", "pnl_pct": n}
    },
    "patterns_identified": [
      {
        "pattern": "description",
        "evidence": "data supporting this",
        "recommendation": "what to do"
      }
    ],
    "agent_performance": {
      "analysis_agent": {"signals_generated": n, "accuracy": pct},
      "risk_auditor": {"approved": n, "rejected": n, "modified": n},
      "execution_agent": {"filled": n, "aborted": n, "avg_slippage_pct": pct}
    },
    "strategy_recommendations": ["list of recommendations"]
  }
}
```

## Important Rules
- Be specific and actionable, not generic
- Back up patterns with evidence
- Focus on what can be CHANGED, not just observed
- Compare agent predictions vs actual outcomes
"""


def build_trade_review_prompt(trade: dict) -> str:
    """
    Build prompt for per-trade review.

    Args:
        trade: Closed trade details

    Returns:
        Complete prompt string
    """
    trade_json = json.dumps(trade, indent=2)

    result = "WIN" if trade.get("pnl_pct", 0) > 0 else "LOSS"

    prompt = f"""Review this closed trade and provide insights.

## Trade Details
```json
{trade_json}
```

## Summary
- Trade ID: {trade.get('trade_id', 'N/A')}
- Symbol: {trade.get('symbol', 'N/A')}
- Direction: {trade.get('direction', 'N/A')}
- Result: {result}
- P&L: {trade.get('pnl_pct', 0):.2f}% (${trade.get('pnl_usd', 0):.2f})

## Your Task
1. Use get_trade_details to get full trade context
2. Use get_market_context to understand market conditions
3. Analyze what worked and what didn't
4. Provide one actionable recommendation
5. Output as JSON in TRADE_REVIEW format"""

    return prompt


def build_daily_report_prompt(date: str, trades: List[dict]) -> str:
    """
    Build prompt for daily batch report.

    Args:
        date: Report date (YYYY-MM-DD)
        trades: List of trades from the day

    Returns:
        Complete prompt string
    """
    trades_json = json.dumps(trades, indent=2)

    total = len(trades)
    wins = sum(1 for t in trades if t.get("pnl_pct", 0) > 0)
    losses = total - wins
    total_pnl = sum(t.get("pnl_pct", 0) for t in trades)

    prompt = f"""Generate daily performance report for {date}.

## Trades Summary
- Total Trades: {total}
- Wins: {wins}
- Losses: {losses}
- Total P&L: {total_pnl:.2f}%

## Trade Details
```json
{trades_json}
```

## Your Task
1. Use get_trade_history to get full trade details
2. Use calculate_metrics for performance metrics
3. Use get_agent_performance to assess each agent
4. Identify 2-3 patterns in the data
5. Provide actionable strategy recommendations
6. Output as JSON in DAILY_REPORT format"""

    return prompt
