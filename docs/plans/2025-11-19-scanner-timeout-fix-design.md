# Scanner Agent Timeout Fix - Design Document

**Date:** 2025-11-19
**Status:** Approved
**Problem:** Agent analysis timing out after 45 seconds without calling submit_trading_signal()

## Problem Analysis

**Current Bottleneck:**
The agent makes sequential tool calls with significant "thinking time" between each call. Logs show the agent successfully calls WebSearch but then times out at 45 seconds before completing the full workflow and calling `submit_trading_signal()`.

**Root Cause:**
The system prompt encourages sequential processing with phrases like "Think step-by-step" and "Use your tools systematically." While efficiency guidelines exist, they're buried at the bottom and not emphasized enough. The agent spends too much time reasoning between tool calls instead of executing them in parallel.

**Impact:**
- Analysis timeout rate: ~100% (all analyses timing out)
- Wasted API costs: Agent does partial work but produces no actionable signal
- Missed trading opportunities: Movers detected but never analyzed

## Solution Overview

**Strategy:** Restructure the system prompt to make parallel execution the PRIMARY instruction, not a suggestion.

**Key Changes:**
1. **Workflow restructure:** Group analysis into 3 parallel "waves" instead of 5-6 sequential steps
2. **Prominent placement:** Efficiency requirements at the TOP of the prompt, before workflow
3. **Explicit examples:** Show exact tool call patterns in each wave
4. **Urgency framing:** "You have 40 seconds max. Speed is critical."
5. **Optimized timeframes:** Remove 1m and 5m (too granular for 5%+ movers)

**Expected Impact:**
- Current: ~8-10 tool calls spread across 45+ seconds with reasoning between each
- Target: 7 tool calls in 3 parallel waves within 25-30 seconds
- Speedup: ~40-50% reduction in total time
- Success rate: 0% → 100% (agent completes and submits signal)

## New Prompt Structure

**File:** `/home/deepol/work/cctrader/agent/main.py` (lines 306-338)

**New System Prompt:**

```python
system_prompt="""SPEED REQUIREMENTS (CRITICAL - READ FIRST):
- You have 40 seconds maximum to complete analysis
- Call tools in PARALLEL whenever possible
- Submit your signal immediately after analysis - do NOT add extra reasoning

PARALLEL EXECUTION PATTERN:
Wave 1 (immediate): fetch_market_data(15m), fetch_market_data(1h), fetch_market_data(4h), get_current_price
Wave 2 (after Wave 1): analyze_market_sentiment, mcp__web-search__search
Wave 3 (final): submit_trading_signal()

DO NOT call tools one at a time. DO NOT add lengthy reasoning between waves.

Your mission: Analyze market movers (5%+ moves) to identify high-probability trades.

Analysis workflow:
1. PARALLEL WAVE 1: Gather ALL technical data in one message
   - Call fetch_market_data for timeframes: 15m, 1h, 4h in SINGLE message
   - Include get_current_price in SAME message
   - 4 tool calls total, all parallel

2. PARALLEL WAVE 2: Get sentiment in one message
   - Call analyze_market_sentiment to get query
   - Call mcp__web-search__search with that query
   - Both in SINGLE message

3. Calculate 4-component confidence score (0-100):
   - Technical alignment: 0-40 points (15m/1h/4h alignment?)
   - Sentiment: 0-30 points (catalysts from web search? REQUIRED)
   - Liquidity: 0-20 points (volume quality?)
   - Correlation: 0-10 points (BTC relationship?)

4. IMMEDIATE FINAL STEP: Call submit_trading_signal() with all 10 parameters
   - Submit immediately after calculating confidence
   - Do NOT add extra reasoning
   - Include: confidence, entry_price, stop_loss, tp1, technical_score, sentiment_score,
     liquidity_score, correlation_score, symbol, analysis

Scoring guidelines:
- Only recommend trades with confidence ≥ 60
- Be conservative - require alignment across ALL factors
- Technical: Aligned trend across 15m/1h/4h timeframes
- Sentiment: Clear catalysts from web search (MUST search)
- Liquidity: Sufficient volume, no manipulation signs
- Correlation: BTC relationship supports trade direction

CRITICAL REQUIREMENTS:
1. You MUST call mcp__web-search__search for sentiment scoring (0-30 pts)
2. You MUST call submit_trading_signal() as your FINAL step
3. If a tool fails, continue with available data - do NOT retry
4. If web search returns minimal results, score sentiment as neutral (15/30) and continue

Your analysis is NOT complete until you call submit_trading_signal().""",
```

## Key Changes from Current Prompt

**Removed:**
- "Think step-by-step. Show reasoning." (encourages slowness)
- 1m and 5m timeframes (too granular, waste resources)
- Verbose workflow explanations
- Efficiency guidelines at bottom (moved to top)

**Added:**
- "SPEED REQUIREMENTS" section at top (critical visibility)
- "PARALLEL EXECUTION PATTERN" with explicit waves
- "DO NOT call tools one at a time" (repeated emphasis)
- "40 seconds maximum" (urgency)
- "Do NOT add extra reasoning" (multiple reminders)
- Error handling: "If tool fails, continue" (prevent debugging loops)

**Timeframe Optimization:**
- **15m:** Entry timing for momentum trades
- **1h:** Trend confirmation
- **4h:** Broader trend context
- **Removed 1m, 5m:** Too noisy for 5%+ movers, wastes API calls

## Tool Call Pattern

**Wave 1: Technical Data (4 parallel calls)**
```python
# Single message with 4 tools:
fetch_market_data(symbol="BTCUSDT", timeframe="15m", limit=50)
fetch_market_data(symbol="BTCUSDT", timeframe="1h", limit=50)
fetch_market_data(symbol="BTCUSDT", timeframe="4h", limit=50)
get_current_price(symbol="BTCUSDT")
```

**Wave 2: Sentiment Data (2 parallel calls)**
```python
# Single message with 2 tools:
analyze_market_sentiment(symbol="BTCUSDT", context="...")
mcp__web-search__search(query="Bitcoin BTC price analysis catalysts")
```

**Wave 3: Submit Signal (1 call)**
```python
# Immediately after calculating confidence:
submit_trading_signal(
    confidence=75,
    entry_price=93500,
    stop_loss=92000,
    tp1=95000,
    technical_score=35,
    sentiment_score=25,
    liquidity_score=18,
    correlation_score=7,
    symbol="BTCUSDT",
    analysis="Strong uptrend across 15m/1h/4h..."
)
```

**Total: 7 tool calls in 3 waves** (down from 8-10 sequential)

## Edge Cases & Error Handling

### Edge Case 1: Agent Still Times Out
- **Detection:** Timeout warning in logs after prompt change
- **Diagnosis:** Check if agent is still making sequential calls (one tool per message in logs)
- **Fix:** Add even more explicit instruction in prompt:
  - "EXAMPLE: In your next message, call these 4 tools: fetch_market_data(15m), fetch_market_data(1h), fetch_market_data(4h), get_current_price"

### Edge Case 2: Agent Skips Required Tools
- **Detection:** Signal submitted with 0 sentiment score or missing technical data
- **Safeguard:** Keep "MUST call" statements, add "Wave 2 is REQUIRED - cannot skip"
- **Validation:** Check submit_trading_signal logs for complete parameter set

### Edge Case 3: Parallel Calls Fail/Error
- **Scenario:** One tool in Wave 1 fails, agent stops entire analysis
- **Mitigation:** Prompt includes "If a tool fails, continue with available data. Do NOT retry failed calls."
- **Behavior:** Agent should score with available data, note limitation in analysis field

### Edge Case 4: Web Search Returns No Results
- **Current:** Agent may spend time trying different queries
- **Fix:** "If web search returns minimal results, score sentiment as neutral (15/30) and continue. Do NOT retry search."
- **Reasoning:** Neutral sentiment (15/30) still allows high confidence if other factors align (40+20+10 = 70 possible)

## Testing Strategy

### Quick Validation
Run scanner for 1-2 cycles and check logs for:

1. **Tool call grouping:**
   - ✅ Wave 1: 4 tools in single message
   - ✅ Wave 2: 2 tools in single message
   - ✅ Wave 3: 1 tool (submit)
   - ❌ One tool per message (indicates sequential execution)

2. **Timing:**
   - Measure from "Starting agent analysis" to "Agent analysis complete" in logs
   - ✅ Target: < 35 seconds (safety margin)
   - ❌ > 40 seconds (approaching timeout)

3. **Success rate:**
   - ✅ Agent calls submit_trading_signal() for every analysis
   - ❌ Timeout warnings appear

### Success Criteria
- Agent completes analysis in < 35 seconds (safety margin from 45s timeout)
- All 4 scoring components still calculated (technical, sentiment, liquidity, correlation)
- Confidence scores remain reasonable (distribution similar to baseline)
- submit_trading_signal() called 100% of the time (no timeouts)

### Failure Indicators
- Still timing out after 45s
- Agent skips web search or technical analysis
- Confidence always 0 or unreasonably low
- Error logs show tool call failures

### Monitoring Metrics (Post-Deployment)
- **Analysis time per mover:** Should drop from 45s+ to 25-35s
- **Submit call rate:** Should go from 0% (timeout) to 100% (success)
- **Confidence distribution:** Should remain similar to current baseline
- **Tool call count:** Should be exactly 7 calls per analysis

## Rollback Plan

**Before Implementation:**
- Commit current working state
- Keep old prompt in comment block above new one for reference

**If New Prompt Fails:**
- Failure threshold: 3+ consecutive analyses timeout or produce bad signals
- Rollback action: `git revert <commit-sha>` to restore old prompt
- Debug: Check logs for actual tool call pattern vs expected pattern

## Implementation Steps

1. **Backup current prompt:**
   - Add comment block with old prompt above new one
   - Commit: "backup: preserve original scanner prompt before optimization"

2. **Apply new prompt:**
   - Replace lines 306-338 in `/home/deepol/work/cctrader/agent/main.py`
   - Commit: "feat(scanner): optimize agent prompt for parallel execution"

3. **Test with scanner:**
   - Run: `python -m agent.main scan-movers --interval 60`
   - Monitor logs for 2-3 scan cycles
   - Verify tool call pattern and timing

4. **Validate or rollback:**
   - If success criteria met: Keep change, monitor production
   - If failure indicators: Revert commit, analyze logs, iterate design

## Expected Outcomes

**Before Fix:**
- Analysis time: 45+ seconds (timeout)
- Success rate: 0%
- Tool pattern: Sequential (one per message)
- Result: No signals generated

**After Fix:**
- Analysis time: 25-35 seconds
- Success rate: 100%
- Tool pattern: 3 waves (4+2+1 parallel calls)
- Result: Signals generated with full 4-component scoring

**Quality Preservation:**
- All 4 scoring components maintained (technical, sentiment, liquidity, correlation)
- Confidence threshold unchanged (≥60 required)
- Scoring guidelines unchanged
- Only change: Speed optimization via parallel execution

## Future Enhancements

**If further optimization needed:**
1. Consider bundled tool: `quick_technical_snapshot(symbol)` returning all timeframes in one call
2. Reduce 4h timeframe to daily for even faster analysis
3. Add timeout warning at 30s mark to prompt agent urgency
4. Implement adaptive timeout based on market volatility

**Monitoring improvements:**
- Log actual vs expected tool call pattern
- Track analysis time distribution (histogram)
- Alert if timeout rate > 5%
