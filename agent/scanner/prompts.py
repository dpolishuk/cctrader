"""Prompt templates for Claude Agent analysis."""
from typing import Dict, Any

class PromptBuilder:
    """Builds prompts for agent analysis tasks."""

    def build_analysis_prompt(
        self,
        mover_context: Dict[str, Any],
        portfolio_context: Dict[str, Any]
    ) -> str:
        """
        Build prompt for analyzing a market mover.

        Args:
            mover_context: Mover details (symbol, direction, changes, price)
            portfolio_context: Portfolio state (value, positions, exposure)

        Returns:
            Formatted prompt string
        """
        symbol = mover_context['symbol']
        direction = mover_context['direction']
        change_1h = mover_context['change_1h']
        change_4h = mover_context['change_4h']
        current_price = mover_context['current_price']
        volume_24h = mover_context.get('volume_24h', 0)

        portfolio_value = portfolio_context['total_value']
        open_positions = portfolio_context['open_positions']
        exposure_pct = portfolio_context['exposure_pct']

        prompt = f"""Analyze {symbol} as a potential {direction} opportunity.

Context:
- Current momentum: {change_1h:+.2f}% in 1h, {change_4h:+.2f}% in 4h
- Current price: ${current_price:,.2f}
- 24h volume: ${volume_24h:,.0f}
- Paper portfolio: ${portfolio_value:,.0f}
- Open positions: {open_positions}/5
- Current exposure: {exposure_pct:.1f}%

Your task:
1. Gather multi-timeframe technical analysis (1m, 5m, 15m, 1h, 4h)
2. Analyze market sentiment and detect catalysts using Perplexity
3. Check liquidity and volume quality
4. Assess correlation with BTC
5. Calculate confidence score (0-100):
   - Technical alignment: 0-40 points
   - Sentiment: 0-30 points
   - Liquidity: 0-20 points
   - Correlation: 0-10 points
6. Determine if HIGH PROBABILITY trade (confidence ≥ 60)
7. If yes, specify entry, stop-loss, take-profit, position size

Use your tools systematically. Think step-by-step. Show reasoning.

EFFICIENCY GUIDELINES:
- Call tools in PARALLEL when possible (multiple independent fetch_market_data calls in one message)
- DO NOT call the same tool multiple times with identical parameters
- Use multi_timeframe_analysis when available instead of individual fetches
- Verify symbol format once (e.g., try "XANUSDT" not "XAN") before making multiple calls

IMPORTANT: Only recommend trades with confidence ≥ 60. Be conservative.

FINAL STEP: Call submit_trading_signal() with your complete analysis.
This is REQUIRED - include all 10 parameters (confidence, prices, scores, symbol, analysis).
"""
        return prompt

    def build_reanalysis_prompt(self, position: Dict[str, Any]) -> str:
        """
        Build prompt for re-analyzing an open position.

        Args:
            position: Position details

        Returns:
            Formatted prompt string
        """
        symbol = position['symbol']
        direction = position['direction']
        entry_price = position['entry_price']
        current_price = position['current_price']
        pnl_pct = position['pnl_pct']
        original_confidence = position['original_confidence']
        duration = position['duration_minutes']

        prompt = f"""Re-analyze open position for {symbol} {direction}.

Position details:
- Entry: ${entry_price:,.2f} @ {duration} minutes ago
- Current price: ${current_price:,.2f}
- P&L: {pnl_pct:+.2f}%
- Original confidence: {original_confidence}
- Time in position: {duration} minutes

Check:
1. Has market sentiment changed? (query Perplexity)
2. Are technicals still aligned?
3. Any new events or catalysts?
4. Is momentum weakening?

Calculate updated confidence score. If <40, recommend early exit.
"""
        return prompt
