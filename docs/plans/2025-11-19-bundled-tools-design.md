# Scanner Timeout Fix - Bundled Tools Approach

**Date:** 2025-11-19
**Status:** Approved
**Problem:** Agent analysis timing out after 45 seconds without calling submit_trading_signal()
**Previous Attempt:** Prompt optimization (failed - agent ignored parallel execution instructions)

## Problem Analysis

**Root Cause Discovery:**
Through SDK research and testing, we discovered that Claude decides parallel vs sequential tool execution based on **dependency analysis**, not prompt instructions. Even explicit prompts stating "call these 4 tools in parallel" were completely ignored.

**Why Prompt Engineering Failed:**
- Claude analyzes tool dependencies at the model level
- If tools appear independent but sequentially ordered in the prompt, Claude may still call them sequentially
- No SDK configuration exists to override this behavior (`disable_parallel_tool_use` exists but does the opposite)
- Prompt engineering cannot force parallel execution

**SDK Documentation Key Finding:**
> "Claude can execute multiple tools simultaneously within a single response when operations are independent. However, Claude decides whether to use parallel or sequential execution based on whether the tools depend on each other's outputs."

**Current Bottleneck:**
Agent makes 7+ sequential tool calls:
1. fetch_market_data(15m) - ~5s
2. fetch_market_data(1h) - ~5s
3. fetch_market_data(4h) - ~5s
4. get_current_price() - ~3s
5. analyze_market_sentiment() - ~5s
6. mcp__web-search__search() - ~8s
7. More analysis/thinking - ~10s+

Total: 45+ seconds → timeout before submit_trading_signal()

## Solution Overview

**Strategy:** Replace multiple small tools with 2 bundled tools that eliminate perceived dependencies by fetching all required data in single calls.

**New Tool Architecture:**

1. **`fetch_technical_snapshot(symbol: str)`**
   - Bundles: 15m/1h/4h timeframe data + current price
   - Returns: All technical data in one response
   - Internal implementation: Uses asyncio.gather() for true parallelism
   - Replaces: 4 sequential calls → 1 bundled call (~5-8 seconds)

2. **`fetch_sentiment_data(symbol: str, context: str)`**
   - Bundles: Sentiment query generation + web search execution
   - Returns: Sentiment summary + web results combined
   - Replaces: 2-3 sequential calls → 1 bundled call (~5-8 seconds)

**Expected Impact:**
- Tool calls: 7 sequential → **3 total** (2 bundled + 1 submit)
- Execution time: 45s+ (timeout) → **15-20 seconds** (success)
- Success rate: 0% → ~100%

## Architecture

### Tool 1: fetch_technical_snapshot

**Purpose:** Gather all technical analysis data in one call

**Function Signature:**
```python
@tool(
    name="fetch_technical_snapshot",
    description="""
    Fetch complete technical analysis data in one call.

    Returns ALL timeframe data (15m, 1h, 4h) plus current price.
    This is the PRIMARY tool for gathering technical data - more efficient than individual fetches.

    Returns data even if some timeframes fail (graceful degradation).
    """
)
async def fetch_technical_snapshot(symbol: str) -> Dict[str, Any]:
    """Fetch all technical data in one bundled call."""
```

**Internal Implementation:**

1. **Parallel fetching** using `asyncio.gather()`:
   ```python
   results = await asyncio.gather(
       fetch_market_data_internal(symbol, "15m", limit=50),
       fetch_market_data_internal(symbol, "1h", limit=50),
       fetch_market_data_internal(symbol, "4h", limit=50),
       get_current_price_internal(symbol),
       return_exceptions=True  # Don't fail entire call on one error
   )
   ```

2. **Graceful error handling:**
   - If a timeframe fetch fails: Set value to `None`, add warning
   - If current price fails: Return 0 or last known price, add warning
   - Never raise exceptions - always return partial data

3. **Response format:**
   ```python
   {
       "timeframes": {
           "15m": {"ohlcv": [...], "indicators": {...}},  # or None if failed
           "1h": {"ohlcv": [...], "indicators": {...}},
           "4h": {"ohlcv": [...], "indicators": {...}}
       },
       "current_price": 93500.0,  # or 0 if failed
       "warnings": ["4h data unavailable"],  # empty if all succeeded
       "success_count": 4  # how many operations succeeded (0-4)
   }
   ```

**Error Handling:**
- Use `return_exceptions=True` in asyncio.gather
- Check each result: if isinstance(result, Exception), set to None
- Build warnings list for failed operations
- Always return a valid dict (never raise)

**Location:** `src/agent/scanner/tools.py` (alongside submit_trading_signal)

### Tool 2: fetch_sentiment_data

**Purpose:** Gather sentiment analysis and web search results in one call

**Function Signature:**
```python
@tool(
    name="fetch_sentiment_data",
    description="""
    Fetch complete sentiment analysis data in one call.

    Automatically generates a sentiment query and executes web search.
    Returns sentiment summary and web search results combined.

    This tool handles the entire sentiment gathering workflow in one operation.
    """
)
async def fetch_sentiment_data(symbol: str, context: str = "") -> Dict[str, Any]:
    """Fetch sentiment query + web results in one bundled call."""
```

**Internal Implementation:**

1. **Step 1: Generate sentiment query**
   ```python
   try:
       sentiment_result = await analyze_market_sentiment_internal(symbol, context)
       query = sentiment_result.get("query", f"{symbol} cryptocurrency news")
   except Exception as e:
       query = f"{symbol} cryptocurrency news"  # Fallback
       warnings.append(f"Sentiment query generation failed: {e}")
   ```

2. **Step 2: Execute web search**
   ```python
   try:
       # Call MCP web-search tool internally
       web_results = await execute_web_search(query)
   except Exception as e:
       web_results = []
       warnings.append(f"Web search failed: {e}")
   ```

3. **Step 3: Generate sentiment summary**
   - Analyze web results for catalysts, sentiment, key themes
   - Suggest sentiment score (agent can override)
   - If no results: Return neutral sentiment

4. **Response format:**
   ```python
   {
       "sentiment_query": "Bitcoin BTC price analysis catalysts",
       "web_results": [
           {"title": "...", "snippet": "...", "url": "..."},
           # ... more results
       ],
       "sentiment_summary": "Positive catalysts: ETF approval, institutional demand...",
       "suggested_sentiment_score": 25,  # out of 30 (agent can override)
       "warnings": [],  # empty if all succeeded
       "success": true
   }
   ```

**Error Handling:**
- If sentiment query generation fails: Use fallback query
- If web search fails: Return empty results with warning
- If both fail: Return minimal data with neutral sentiment score
- Never raise exceptions

**Location:** `src/agent/scanner/tools.py`

## System Prompt Updates

**Location:** `src/agent/main.py` lines 307-338 (system_prompt in ClaudeAgentOptions)

**New Prompt:**

```python
system_prompt="""You are an expert cryptocurrency trading analysis agent for market movers scanning.

Your mission: Analyze high-momentum market movers (5%+ moves) to identify high-probability trading opportunities.

Analysis workflow:
1. Gather ALL data first:
   - fetch_technical_snapshot: Returns 15m/1h/4h data + current price in ONE call
   - fetch_sentiment_data: Returns sentiment query + web search results in ONE call

2. Calculate 4-component confidence score (0-100):
   - Technical alignment: 0-40 points (15m/1h/4h alignment?)
   - Sentiment: 0-30 points (catalysts from web results?)
   - Liquidity: 0-20 points (volume quality from technical data?)
   - Correlation: 0-10 points (BTC relationship?)

3. IMMEDIATELY call submit_trading_signal() with all 10 parameters
   - Include: confidence, entry_price, stop_loss, tp1, technical_score,
     sentiment_score, liquidity_score, correlation_score, symbol, analysis
   - Do NOT add extra reasoning after calculating confidence

Scoring guidelines:
- Only recommend trades with confidence ≥ 60
- Be conservative - require alignment across ALL factors
- Technical: Aligned trend across 15m/1h/4h timeframes
- Sentiment: Clear catalysts from web results
- Liquidity: Sufficient volume, no manipulation signs
- Correlation: BTC relationship supports trade direction

CRITICAL REQUIREMENTS:
1. Each data tool should only be called ONCE
2. If a tool returns warnings, use available data - do NOT retry
3. You MUST call submit_trading_signal() as your FINAL step
4. Your analysis is NOT complete until you call submit_trading_signal()

Speed target: Complete analysis in under 30 seconds.
"""
```

**Key Changes from Old Prompt:**
- Removed references to individual `fetch_market_data` calls
- Emphasizes "ONE call" for each data gathering step
- Added "do NOT retry" to prevent repeated calls on warnings
- Simplified workflow to 3 clear steps (was 5 sequential steps)
- Removed verbose explanations (shorter = faster processing)
- Added explicit "30 seconds" speed target
- Removed "Think step-by-step" phrases

## MCP Server and Tools Configuration

**Location:** `src/agent/main.py` lines 273-304

**Changes to tools list:**

```python
# Create MCP server with bundled tools
trading_tools_server = create_sdk_mcp_server(
    name="trading_tools",
    version="1.0.0",
    tools=[
        # NEW: Bundled tools for scanner
        fetch_technical_snapshot,
        fetch_sentiment_data,

        # Keep for other agents, but scanner won't use:
        fetch_market_data,
        get_current_price,
        analyze_technicals,
        analyze_market_sentiment,
        detect_market_events,

        # Scanner output tool
        submit_trading_signal,
    ]
)
```

**Changes to allowed_tools:**

```python
allowed_tools=[
    # Scanner uses bundled tools only
    "mcp__trading__fetch_technical_snapshot",
    "mcp__trading__fetch_sentiment_data",
    "mcp__trading__submit_trading_signal",

    # External tools
    "mcp__web-search__search",  # Used internally by fetch_sentiment_data
]
```

**Removed from scanner:**
- `mcp__trading__fetch_market_data` (bundled into fetch_technical_snapshot)
- `mcp__trading__get_current_price` (bundled into fetch_technical_snapshot)
- `mcp__trading__analyze_technicals` (not needed for scanner)
- `mcp__trading__multi_timeframe_analysis` (replaced by bundled tools)
- `mcp__trading__analyze_market_sentiment` (bundled into fetch_sentiment_data)
- `mcp__trading__detect_market_events` (not needed for scanner)

## Error Handling Strategy

### Tool-Level Resilience

1. **Both bundled tools return partial data on failure:**
   - Never raise exceptions to the agent
   - Use `return_exceptions=True` in asyncio.gather
   - Check each result for Exception type
   - Build warnings array for failed operations

2. **Response structure guarantees:**
   - Always return a valid dict
   - Always include `warnings` array (empty if all succeeded)
   - Always include `success_count` or `success` boolean
   - Null/0 values for failed individual operations

### Agent-Level Handling

1. **Prompt instructs graceful degradation:**
   - "If a tool returns warnings, use available data - do NOT retry"
   - Agent can calculate confidence with partial data
   - Lower confidence is natural outcome of missing data

2. **Example scenarios:**
   - 4h timeframe fails → Calculate with 15m/1h only (technical_score reduced)
   - Web search fails → Use neutral sentiment (sentiment_score = 15/30)
   - Current price fails → Use last known price from timeframe data

### Timeout Safeguards

1. **Internal operation timeouts:**
   - Each fetch operation: 10-second timeout
   - Web search: 15-second timeout
   - Total bundled tool time: ~8-12 seconds max

2. **Agent wrapper timeout:**
   - Keep at 45 seconds (unchanged)
   - Now has comfortable margin: 15-20s actual vs 45s limit
   - Previous: 45s+ actual vs 45s limit (always timeout)

## Testing Strategy

### Unit Tests for Bundled Tools

**Test file:** `tests/test_scanner_bundled_tools.py`

**Test cases:**

1. **test_fetch_technical_snapshot_success:**
   - Mock all timeframe fetches to succeed
   - Verify all 4 data points returned
   - Verify warnings array is empty
   - Verify success_count = 4

2. **test_fetch_technical_snapshot_partial_failure:**
   - Mock 4h fetch to fail, others succeed
   - Verify 15m/1h data present, 4h is None
   - Verify warning about 4h failure
   - Verify success_count = 3

3. **test_fetch_technical_snapshot_complete_failure:**
   - Mock all fetches to fail
   - Verify minimal data structure returned
   - Verify all warnings present
   - Verify success_count = 0

4. **test_fetch_sentiment_data_success:**
   - Mock sentiment query and web search to succeed
   - Verify query, results, summary present
   - Verify suggested_sentiment_score calculated
   - Verify warnings array empty

5. **test_fetch_sentiment_data_web_search_failure:**
   - Mock web search to fail
   - Verify fallback to empty results
   - Verify neutral sentiment suggested
   - Verify warning present

### Integration Test with Scanner

**Test procedure:**

1. Run scanner for 2-3 cycles:
   ```bash
   cd /home/deepol/work/cctrader/.worktrees/scanner-timeout
   python -m src.agent.main scan-movers --interval 60 2>&1 | tee /tmp/bundled_test.log
   ```

2. Check logs for expected pattern:
   ```
   ✅ Message #1: 1 tool(s) - fetch_technical_snapshot
   ✅ Message #2: 1 tool(s) - fetch_sentiment_data
   ✅ Message #3: 1 tool(s) - submit_trading_signal
   ```

3. Verify timing:
   - Analysis start to completion: < 25 seconds
   - No timeout warnings
   - submit_trading_signal called 100% of the time

4. Check signal quality:
   - Confidence scores reasonable (similar distribution to baseline)
   - All 4 scoring components calculated
   - No regression in analysis quality

## Success Criteria

**Primary Metrics:**

1. **Analysis time:** < 30 seconds (was 45s+ timeout)
   - Target: 15-20 seconds average
   - Maximum: 25 seconds

2. **Success rate:** 100% (was 0%)
   - Agent calls submit_trading_signal every time
   - No timeout warnings in logs

3. **Tool call pattern:** 3 messages (was 7+ sequential)
   - Message #1: fetch_technical_snapshot
   - Message #2: fetch_sentiment_data
   - Message #3: submit_trading_signal

**Secondary Metrics:**

1. **Signal quality:** No regression
   - Confidence distribution similar to baseline
   - All 4 components calculated (technical, sentiment, liquidity, correlation)
   - Entry/stop/target prices reasonable

2. **Error resilience:** Handles partial failures
   - Can complete with 2/3 timeframes
   - Can complete with failed web search (neutral sentiment)
   - Warnings logged but doesn't crash

**Failure Indicators:**

- Analysis still times out after 45 seconds
- Agent calls bundled tools multiple times (retries)
- Agent calls web-search directly (bypassing fetch_sentiment_data)
- Confidence always 0 or unreasonably low
- submit_trading_signal not called

## Rollback Plan

**If bundled tools approach fails:**

1. **Immediate rollback:**
   ```bash
   git revert <bundled-tools-commit-sha>
   ```

2. **Partial rollback option:**
   - Keep bundled tools in codebase but remove from scanner's allowed_tools
   - Restore old tools to allowed_tools list
   - Restore old system prompt

3. **Investigation steps:**
   - Check bundled tool internal errors (asyncio.gather failures?)
   - Verify web-search MCP integration works
   - Test if agent still tries to call removed tools (error logs)
   - Review if agent ignores bundled tools in favor of non-existent ones

**Backup files:**
- Design doc: `docs/plans/2025-11-19-bundled-tools-design.md`
- Old tools still exist in `src/agent/tools/` for other agents
- Git history preserves all previous working states

## Implementation Steps

1. **Create bundled tools:**
   - Add `fetch_technical_snapshot` to `src/agent/scanner/tools.py`
   - Add `fetch_sentiment_data` to `src/agent/scanner/tools.py`
   - Import necessary functions from `src/agent/tools/market_data.py`

2. **Update scanner configuration:**
   - Modify `src/agent/main.py` lines 273-284 (tools list)
   - Modify `src/agent/main.py` lines 295-304 (allowed_tools)
   - Modify `src/agent/main.py` lines 307-338 (system_prompt)

3. **Write unit tests:**
   - Create `tests/test_scanner_bundled_tools.py`
   - Add test cases for success and failure scenarios

4. **Test with scanner:**
   - Run for 2-3 cycles
   - Analyze logs for tool call pattern
   - Verify timing and success rate

5. **Validate or rollback:**
   - If success criteria met: Merge to main
   - If failure indicators: Rollback and investigate

## Expected Outcomes

**Before Fix:**
- Analysis time: 45+ seconds (timeout)
- Success rate: 0%
- Tool pattern: 7+ sequential calls
- Result: No signals generated

**After Fix:**
- Analysis time: 15-20 seconds
- Success rate: ~100%
- Tool pattern: 3 calls (2 bundled + 1 submit)
- Result: Signals generated with full 4-component scoring

**Quality Preservation:**
- All 4 scoring components maintained
- Confidence threshold unchanged (≥60 required)
- Scoring guidelines unchanged
- Only change: Speed optimization via tool bundling

## Future Enhancements

**If further optimization needed:**

1. **Pre-fetch current price:** Cache current price before agent call starts
2. **Combine both bundled tools:** Single `fetch_all_analysis_data` tool
3. **Streaming results:** Return data as it arrives (reduce perceived latency)
4. **Caching:** Cache recent technical data (avoid re-fetching same timeframe)

**Monitoring improvements:**

- Log actual vs expected tool call pattern
- Track analysis time distribution (histogram)
- Alert if timeout rate > 5%
- Track partial failure rate (warnings present)
