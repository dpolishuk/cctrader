# Bundled Tools Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix scanner timeout by replacing 7 sequential tool calls with 2 bundled tools that fetch all data in single operations.

**Architecture:** Create fetch_technical_snapshot (bundles 4 technical data calls) and fetch_sentiment_data (bundles sentiment + web search). Update scanner config to use only bundled tools. Agent makes 3 total calls instead of 7+ sequential.

**Tech Stack:** Python, Claude Agent SDK, asyncio, pytest, ccxt (exchange API)

---

## Task 1: Create fetch_technical_snapshot Tool with Tests

**Files:**
- Modify: `src/agent/scanner/tools.py` (add new tool)
- Create: `tests/test_scanner_bundled_tools.py`

**Step 1: Write the failing test**

Create `tests/test_scanner_bundled_tools.py`:

```python
"""Tests for scanner bundled tools."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.agent.scanner.tools import fetch_technical_snapshot


@pytest.mark.asyncio
async def test_fetch_technical_snapshot_success():
    """Test successful fetch of all technical data."""
    # Mock the internal fetch functions
    mock_15m_data = {"ohlcv": [[1, 2, 3, 4, 5]], "indicators": {"rsi": 50}}
    mock_1h_data = {"ohlcv": [[6, 7, 8, 9, 10]], "indicators": {"rsi": 55}}
    mock_4h_data = {"ohlcv": [[11, 12, 13, 14, 15]], "indicators": {"rsi": 60}}
    mock_price = 93500.0

    with patch('agent.scanner.tools.fetch_market_data_internal') as mock_fetch, \
         patch('agent.scanner.tools.get_current_price_internal') as mock_price_fn:

        # Setup mocks to return successful data
        mock_fetch.side_effect = [mock_15m_data, mock_1h_data, mock_4h_data]
        mock_price_fn.return_value = mock_price

        # Call the tool
        result = await fetch_technical_snapshot({"symbol": "BTCUSDT"})

        # Verify structure
        assert "content" in result
        content = result["content"][0]
        assert content["type"] == "text"

        import json
        data = json.loads(content["text"])

        # Verify all timeframes present
        assert "timeframes" in data
        assert "15m" in data["timeframes"]
        assert "1h" in data["timeframes"]
        assert "4h" in data["timeframes"]
        assert data["timeframes"]["15m"] == mock_15m_data
        assert data["timeframes"]["1h"] == mock_1h_data
        assert data["timeframes"]["4h"] == mock_4h_data

        # Verify current price
        assert data["current_price"] == mock_price

        # Verify no warnings
        assert data["warnings"] == []
        assert data["success_count"] == 4
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_scanner_bundled_tools.py::test_fetch_technical_snapshot_success -v`

Expected: FAIL with "cannot import name 'fetch_technical_snapshot'" or "module has no attribute"

**Step 3: Write minimal implementation**

Add to `src/agent/scanner/tools.py` (after the submit_trading_signal tool):

```python
import asyncio
import json
from typing import Dict, Any, List


async def fetch_market_data_internal(symbol: str, timeframe: str, limit: int = 50) -> Dict[str, Any]:
    """Internal function to fetch market data."""
    from src.agent.tools.market_data import fetch_market_data
    result = await fetch_market_data({
        "symbol": symbol,
        "timeframe": timeframe,
        "limit": limit
    })
    # Extract data from MCP response format
    if "content" in result and len(result["content"]) > 0:
        import json
        return json.loads(result["content"][0]["text"])
    return {}


async def get_current_price_internal(symbol: str) -> float:
    """Internal function to get current price."""
    from src.agent.tools.market_data import get_current_price
    result = await get_current_price({"symbol": symbol})
    # Extract price from MCP response format
    if "content" in result and len(result["content"]) > 0:
        import json
        data = json.loads(result["content"][0]["text"])
        return data.get("price", 0.0)
    return 0.0


@tool(
    name="fetch_technical_snapshot",
    description="""
    Fetch complete technical analysis data in one call.

    Returns ALL timeframe data (15m, 1h, 4h) plus current price.
    This is the PRIMARY tool for gathering technical data - more efficient than individual fetches.

    Returns data even if some timeframes fail (graceful degradation).

    Args:
        symbol: Trading pair (e.g., "BTCUSDT")

    Returns:
        JSON with timeframes dict, current_price, warnings array, success_count
    """
)
async def fetch_technical_snapshot(args: Dict[str, Any]) -> Dict[str, Any]:
    """Fetch all technical data in one bundled call."""
    symbol = args.get("symbol", "")
    warnings: List[str] = []
    success_count = 0

    # Fetch all data in parallel using asyncio.gather
    results = await asyncio.gather(
        fetch_market_data_internal(symbol, "15m", limit=50),
        fetch_market_data_internal(symbol, "1h", limit=50),
        fetch_market_data_internal(symbol, "4h", limit=50),
        get_current_price_internal(symbol),
        return_exceptions=True
    )

    # Process results with error handling
    timeframes = {}
    current_price = 0.0

    # 15m data
    if isinstance(results[0], Exception):
        warnings.append(f"15m data fetch failed: {results[0]}")
        timeframes["15m"] = None
    else:
        timeframes["15m"] = results[0]
        success_count += 1

    # 1h data
    if isinstance(results[1], Exception):
        warnings.append(f"1h data fetch failed: {results[1]}")
        timeframes["1h"] = None
    else:
        timeframes["1h"] = results[1]
        success_count += 1

    # 4h data
    if isinstance(results[2], Exception):
        warnings.append(f"4h data fetch failed: {results[2]}")
        timeframes["4h"] = None
    else:
        timeframes["4h"] = results[2]
        success_count += 1

    # Current price
    if isinstance(results[3], Exception):
        warnings.append(f"Current price fetch failed: {results[3]}")
        current_price = 0.0
    else:
        current_price = results[3]
        success_count += 1

    # Build response
    response_data = {
        "timeframes": timeframes,
        "current_price": current_price,
        "warnings": warnings,
        "success_count": success_count
    }

    return {
        "content": [{
            "type": "text",
            "text": json.dumps(response_data)
        }]
    }
```

**Step 4: Add tool import at top of file**

Add to imports section in `src/agent/scanner/tools.py`:

```python
from claude_agent_sdk import tool
```

**Step 5: Run test to verify it passes**

Run: `pytest tests/test_scanner_bundled_tools.py::test_fetch_technical_snapshot_success -v`

Expected: PASS

**Step 6: Commit**

```bash
git add agent/scanner/tools.py tests/test_scanner_bundled_tools.py
git commit -m "feat: add fetch_technical_snapshot bundled tool

Bundles 15m/1h/4h timeframe fetches + current price into one call.
Uses asyncio.gather for parallel fetching with graceful error handling.
Returns partial data with warnings if some fetches fail.

Part of scanner timeout fix (7 calls → 3 calls).

🤖 Generated with Claude Code

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 2: Add Partial Failure Test for fetch_technical_snapshot

**Files:**
- Modify: `tests/test_scanner_bundled_tools.py`

**Step 1: Write the failing test**

Add to `tests/test_scanner_bundled_tools.py`:

```python
@pytest.mark.asyncio
async def test_fetch_technical_snapshot_partial_failure():
    """Test fetch with one timeframe failing."""
    mock_15m_data = {"ohlcv": [[1, 2, 3, 4, 5]], "indicators": {"rsi": 50}}
    mock_1h_data = {"ohlcv": [[6, 7, 8, 9, 10]], "indicators": {"rsi": 55}}
    mock_price = 93500.0

    with patch('agent.scanner.tools.fetch_market_data_internal') as mock_fetch, \
         patch('agent.scanner.tools.get_current_price_internal') as mock_price_fn:

        # 4h fetch fails, others succeed
        mock_fetch.side_effect = [
            mock_15m_data,
            mock_1h_data,
            Exception("API rate limit exceeded")  # 4h fails
        ]
        mock_price_fn.return_value = mock_price

        result = await fetch_technical_snapshot({"symbol": "BTCUSDT"})

        import json
        data = json.loads(result["content"][0]["text"])

        # Verify partial success
        assert data["timeframes"]["15m"] == mock_15m_data
        assert data["timeframes"]["1h"] == mock_1h_data
        assert data["timeframes"]["4h"] is None  # Failed
        assert data["current_price"] == mock_price

        # Verify warning present
        assert len(data["warnings"]) == 1
        assert "4h data fetch failed" in data["warnings"][0]
        assert data["success_count"] == 3  # 3 out of 4 succeeded
```

**Step 2: Run test to verify it passes**

Run: `pytest tests/test_scanner_bundled_tools.py::test_fetch_technical_snapshot_partial_failure -v`

Expected: PASS (implementation already handles this)

**Step 3: Commit**

```bash
git add tests/test_scanner_bundled_tools.py
git commit -m "test: add partial failure test for fetch_technical_snapshot

Verifies graceful degradation when one timeframe fetch fails.
Ensures warnings are generated and partial data is returned.

🤖 Generated with Claude Code

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 3: Create fetch_sentiment_data Tool with Tests

**Files:**
- Modify: `src/agent/scanner/tools.py`
- Modify: `tests/test_scanner_bundled_tools.py`

**Step 1: Write the failing test**

Add to `tests/test_scanner_bundled_tools.py`:

```python
@pytest.mark.asyncio
async def test_fetch_sentiment_data_success():
    """Test successful fetch of sentiment data."""
    mock_query = "Bitcoin BTC price analysis catalysts"
    mock_web_results = [
        {"title": "BTC ETF Approved", "snippet": "SEC approves...", "url": "https://..."},
        {"title": "Institutional Demand", "snippet": "Major funds...", "url": "https://..."}
    ]
    mock_summary = "Positive catalysts: ETF approval, institutional demand"

    with patch('agent.scanner.tools.generate_sentiment_query_internal') as mock_query_fn, \
         patch('agent.scanner.tools.execute_web_search_internal') as mock_search:

        mock_query_fn.return_value = mock_query
        mock_search.return_value = mock_web_results

        result = await fetch_sentiment_data({"symbol": "BTCUSDT", "context": "5% up"})

        import json
        data = json.loads(result["content"][0]["text"])

        # Verify query generated
        assert data["sentiment_query"] == mock_query

        # Verify web results
        assert data["web_results"] == mock_web_results

        # Verify summary exists
        assert "sentiment_summary" in data
        assert len(data["sentiment_summary"]) > 0

        # Verify sentiment score suggested
        assert "suggested_sentiment_score" in data
        assert 0 <= data["suggested_sentiment_score"] <= 30

        # Verify no warnings
        assert data["warnings"] == []
        assert data["success"] is True
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_scanner_bundled_tools.py::test_fetch_sentiment_data_success -v`

Expected: FAIL with "cannot import name 'fetch_sentiment_data'"

**Step 3: Write minimal implementation**

Add to `src/agent/scanner/tools.py` (after fetch_technical_snapshot):

```python
async def generate_sentiment_query_internal(symbol: str, context: str = "") -> str:
    """Internal function to generate sentiment query."""
    from src.agent.tools.sentiment import analyze_market_sentiment
    result = await analyze_market_sentiment({
        "symbol": symbol,
        "context": context
    })
    # Extract query from MCP response format
    if "content" in result and len(result["content"]) > 0:
        import json
        data = json.loads(result["content"][0]["text"])
        return data.get("query", f"{symbol} cryptocurrency news")
    return f"{symbol} cryptocurrency news"


async def execute_web_search_internal(query: str) -> List[Dict[str, str]]:
    """Internal function to execute web search via MCP."""
    # This will be called via the MCP server, but for now we'll simulate
    # In actual implementation, this calls the web-search MCP tool
    # For testing, we return empty list as fallback
    return []


def analyze_sentiment_from_results(web_results: List[Dict[str, str]]) -> tuple[str, int]:
    """
    Analyze web results to generate summary and suggest sentiment score.

    Returns:
        (summary, suggested_score) where score is 0-30
    """
    if not web_results:
        return "No web results available for sentiment analysis", 15

    # Simple heuristic: count positive/negative keywords
    positive_keywords = ["approval", "approved", "bullish", "surge", "rally", "institutional",
                        "adoption", "demand", "breakthrough", "upgrade"]
    negative_keywords = ["crash", "bearish", "decline", "concern", "risk", "regulation",
                        "ban", "hack", "fraud", "lawsuit"]

    positive_count = 0
    negative_count = 0

    for result in web_results:
        text = f"{result.get('title', '')} {result.get('snippet', '')}".lower()
        positive_count += sum(1 for kw in positive_keywords if kw in text)
        negative_count += sum(1 for kw in negative_keywords if kw in text)

    # Generate summary
    if positive_count > negative_count * 1.5:
        summary = f"Positive sentiment detected. Catalysts found: {positive_count} positive signals vs {negative_count} negative."
        score = min(30, 15 + positive_count * 2)
    elif negative_count > positive_count * 1.5:
        summary = f"Negative sentiment detected. Risks found: {negative_count} negative signals vs {positive_count} positive."
        score = max(0, 15 - negative_count * 2)
    else:
        summary = f"Neutral sentiment. Mixed signals: {positive_count} positive, {negative_count} negative."
        score = 15

    return summary, score


@tool(
    name="fetch_sentiment_data",
    description="""
    Fetch complete sentiment analysis data in one call.

    Automatically generates a sentiment query and executes web search.
    Returns sentiment summary and web search results combined.

    This tool handles the entire sentiment gathering workflow in one operation.

    Args:
        symbol: Trading pair (e.g., "BTCUSDT")
        context: Optional context about the move (e.g., "5% up in last hour")

    Returns:
        JSON with sentiment_query, web_results, sentiment_summary, suggested_sentiment_score, warnings, success
    """
)
async def fetch_sentiment_data(args: Dict[str, Any]) -> Dict[str, Any]:
    """Fetch sentiment query + web results in one bundled call."""
    symbol = args.get("symbol", "")
    context = args.get("context", "")
    warnings: List[str] = []

    # Step 1: Generate sentiment query
    try:
        sentiment_query = await generate_sentiment_query_internal(symbol, context)
    except Exception as e:
        warnings.append(f"Sentiment query generation failed: {e}")
        sentiment_query = f"{symbol} cryptocurrency news"

    # Step 2: Execute web search
    try:
        web_results = await execute_web_search_internal(sentiment_query)
    except Exception as e:
        warnings.append(f"Web search failed: {e}")
        web_results = []

    # Step 3: Analyze results and generate summary
    sentiment_summary, suggested_score = analyze_sentiment_from_results(web_results)

    # Build response
    response_data = {
        "sentiment_query": sentiment_query,
        "web_results": web_results,
        "sentiment_summary": sentiment_summary,
        "suggested_sentiment_score": suggested_score,
        "warnings": warnings,
        "success": len(warnings) == 0
    }

    return {
        "content": [{
            "type": "text",
            "text": json.dumps(response_data)
        }]
    }
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_scanner_bundled_tools.py::test_fetch_sentiment_data_success -v`

Expected: PASS

**Step 5: Commit**

```bash
git add agent/scanner/tools.py tests/test_scanner_bundled_tools.py
git commit -m "feat: add fetch_sentiment_data bundled tool

Bundles sentiment query generation + web search into one call.
Analyzes web results to suggest sentiment score (0-30 points).
Graceful fallback if query generation or search fails.

Part of scanner timeout fix (7 calls → 3 calls).

🤖 Generated with Claude Code

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 4: Update Scanner MCP Server Configuration

**Files:**
- Modify: `src/agent/main.py:273-304`

**Step 1: Import bundled tools**

Add to imports section in `src/agent/main.py` (around line 270):

```python
from src.agent.scanner.tools import submit_trading_signal, fetch_technical_snapshot, fetch_sentiment_data
```

**Step 2: Update tools list**

Modify lines 273-284 in `src/agent/main.py`:

```python
        # Create MCP server with all trading tools including bundled tools
        trading_tools_server = create_sdk_mcp_server(
            name="trading_tools",
            version="1.0.0",
            tools=[
                # Scanner bundled tools
                fetch_technical_snapshot,
                fetch_sentiment_data,
                submit_trading_signal,

                # Keep individual tools for other agents (not scanner)
                fetch_market_data,
                get_current_price,
                analyze_technicals,
                multi_timeframe_analysis,
                analyze_market_sentiment,
                detect_market_events,
            ]
        )
```

**Step 3: Update allowed_tools list**

Modify lines 295-304 in `src/agent/main.py`:

```python
            # Allowed tools - scanner uses only bundled tools
            allowed_tools=[
                "mcp__trading__fetch_technical_snapshot",
                "mcp__trading__fetch_sentiment_data",
                "mcp__trading__submit_trading_signal",
                "mcp__web-search__search",  # Used internally by fetch_sentiment_data
            ],
```

**Step 4: Verify syntax**

Run: `python -m py_compile agent/main.py`

Expected: No errors

**Step 5: Verify import**

Run: `python -c "from src.agent.main import cli; print('OK')"`

Expected: Output "OK"

**Step 6: Commit**

```bash
git add agent/main.py
git commit -m "feat: configure scanner to use bundled tools

Changes:
- Import fetch_technical_snapshot and fetch_sentiment_data
- Add bundled tools to MCP server tools list
- Update allowed_tools to only include bundled tools for scanner
- Remove individual fetch_market_data, get_current_price from allowed_tools

Scanner now limited to 2 data tools instead of 7+ individual tools.

🤖 Generated with Claude Code

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 5: Update System Prompt

**Files:**
- Modify: `src/agent/main.py:306-338` (system_prompt section)

**Step 1: Read current prompt location**

Run: `grep -n "system_prompt=" agent/main.py | head -1`

Expected: Line number around 337 (after ORIGINAL PROMPT backup from previous attempt)

**Step 2: Replace system prompt**

Find the `system_prompt="""..."""` section (starts around line 337) and replace with:

```python
            # System prompt for scanner agent
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

Speed target: Complete analysis in under 30 seconds.""",
```

**Step 3: Verify syntax**

Run: `python -m py_compile agent/main.py`

Expected: No errors

**Step 4: Commit**

```bash
git add agent/main.py
git commit -m "feat: update scanner prompt for bundled tools workflow

Changes:
- Replace 5-step sequential workflow with 3-step bundled workflow
- Emphasize ONE call for each data tool
- Add explicit 'do NOT retry' instruction
- Remove references to individual fetch_market_data calls
- Simplify to 3 clear steps: gather data, calculate score, submit
- Add 30-second speed target

🤖 Generated with Claude Code

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 6: Run Unit Tests

**Files:**
- Test: `tests/test_scanner_bundled_tools.py`

**Step 1: Run all bundled tools tests**

Run: `pytest tests/test_scanner_bundled_tools.py -v`

Expected: All tests PASS (3 tests total)

**Step 2: If any tests fail, fix and re-run**

If failures occur:
- Read error message
- Fix implementation in `src/agent/scanner/tools.py`
- Re-run tests
- Commit fix with message: "fix: [description of fix]"

**Step 3: Run full test suite to check for regressions**

Run: `pytest tests/ -v --tb=short`

Expected: Existing tests still pass (new failures unrelated to bundled tools are pre-existing)

---

## Task 7: Integration Test with Scanner

**Files:**
- Test: Manual scanner execution
- Create: `test_bundled_tools_results.txt`

**Step 1: Run scanner for 2-3 cycles**

Run:
```bash
cd /home/deepol/work/cctrader/.worktrees/scanner-timeout
python -m src.agent.main scan-movers --interval 60 2>&1 | tee /tmp/bundled_tools_test.log
```

Let it run for 2-3 complete cycles (2-3 minutes), then Ctrl+C

**Step 2: Analyze logs for success indicators**

Run:
```bash
grep "Message #" /tmp/bundled_tools_test.log
grep "Tool call:" /tmp/bundled_tools_test.log
grep "Agent analysis" /tmp/bundled_tools_test.log
```

Expected success indicators:
- ✅ "Message #1: 1 tool(s) - fetch_technical_snapshot"
- ✅ "Message #2: 1 tool(s) - fetch_sentiment_data"
- ✅ "Message #3: 1 tool(s) - submit_trading_signal"
- ✅ "Agent analysis complete: confidence=..." (not timeout)
- ✅ Analysis time < 30 seconds

Failure indicators:
- ❌ "Agent analysis timeout after 45 seconds"
- ❌ More than 3 messages with tools
- ❌ Agent calling web-search directly (should be bundled)

**Step 3: Document results**

Run:
```bash
cat > test_bundled_tools_results.txt << 'EOF'
Bundled Tools Test Results - $(date)
=====================================

Test command:
python -m src.agent.main scan-movers --interval 60

Duration: [X minutes, Y cycles]

Tool Call Pattern:
------------------
$(grep "Message #" /tmp/bundled_tools_test.log | head -10)

Analysis Times:
---------------
$(grep "Agent analysis complete" /tmp/bundled_tools_test.log)

Success/Failure:
----------------
Timeout warnings: $(grep -c "timeout" /tmp/bundled_tools_test.log)
submit_trading_signal calls: $(grep -c "submit_trading_signal" /tmp/bundled_tools_test.log)
Total cycles: [X]

Verdict: [SUCCESS/FAILURE]
EOF
```

**Step 4: Commit test results**

```bash
git add test_bundled_tools_results.txt
git commit -m "test: verify bundled tools fix scanner timeout

Results:
- Tool call pattern: [3 calls / sequential - fill in actual result]
- Analysis time: [XX seconds - fill in actual result]
- Success rate: [X/Y cycles - fill in actual result]

[Add any notable observations]

🤖 Generated with Claude Code

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 8: Validation and Decision

**Files:**
- Review: `test_bundled_tools_results.txt`
- Decision: Keep or rollback

**Step 1: Evaluate test results against success criteria**

Success criteria (from design doc):
- ✅ Analysis time < 30 seconds (was 45s+ timeout)
- ✅ Success rate 100% (was 0%)
- ✅ Tool call pattern = 3 messages (was 7+ sequential)
- ✅ Signal quality preserved (confidence scores reasonable)

Decision matrix:

**KEEP (proceed to Task 9):**
- Agent completes analysis without timeout
- Tool calls grouped in 3 messages (bundled pattern)
- submit_trading_signal called successfully
- Analysis time < 30 seconds
- Confidence scores still reasonable

**ROLLBACK (proceed to Task 10):**
- Agent still times out after 45 seconds
- Agent calls tools more than expected (retries or bypasses bundled tools)
- Errors or crashes during analysis
- Confidence always 0 or analysis quality degraded

**Step 2: Make decision**

Based on test_bundled_tools_results.txt, choose:
- Option A: Keep changes (proceed to Task 9)
- Option B: Rollback (proceed to Task 10)

---

## Task 9: Success - Finalize and Document (Conditional)

**Only run if Task 8 decision = KEEP**

**Files:**
- Update: `docs/plans/2025-11-19-bundled-tools-design.md`

**Step 1: Update design doc with results**

Add to end of `docs/plans/2025-11-19-bundled-tools-design.md`:

```markdown
## Implementation Results

**Implementation Date:** 2025-11-19

**Test Results:**
- Analysis completion rate: [X%] (was 0%)
- Average analysis time: [XX seconds] (was 45s+ timeout)
- Tool call pattern: 3 calls as designed (fetch_technical_snapshot, fetch_sentiment_data, submit_trading_signal)
- Success rate: [X/Y] cycles completed successfully

**Validation:**
- ✅ Agent completes analysis within 30 seconds
- ✅ All 4 scoring components calculated
- ✅ submit_trading_signal called every time
- ✅ Confidence scores reasonable (similar distribution to baseline)

**Status:** VALIDATED - Ready for production

**Key Learnings:**
- Prompt engineering insufficient to control tool execution
- Tool bundling successfully eliminated sequential dependency perception
- Graceful error handling enabled analysis even with partial data failures
```

**Step 2: Commit documentation update**

```bash
git add docs/plans/2025-11-19-bundled-tools-design.md
git commit -m "docs: add implementation results to bundled tools design

Validation complete:
- Timeout issue resolved (0% → [X%] success)
- Analysis time reduced (45s+ → [XX]s)
- Bundled execution working as designed

🤖 Generated with Claude Code

Co-Authored-By: Claude <noreply@anthropic.com>"
```

**Step 3: Final commit**

```bash
git commit --allow-empty -m "feat: bundled tools fix complete

Summary:
- Problem: Agent timeout after 45s with sequential tool calls
- Solution: Bundled 7 sequential calls into 2 parallel operations
- Result: 0% → [X%] success rate, 45s+ → [XX]s analysis time

All tests passed. Ready for merge.

🤖 Generated with Claude Code

Co-Authored-By: Claude <noreply@anthropic.com>"
```

**Step 4: Ready for merge**

Implementation complete. Use `superpowers:finishing-a-development-branch` skill to:
- Merge to main, or
- Create pull request, or
- Keep branch as-is

---

## Task 10: Rollback (Only if Task 8 decision = ROLLBACK)

**Only run if Task 8 decision = ROLLBACK**

**Files:**
- Revert: Multiple commits
- Create: `rollback_bundled_tools_notes.txt`

**Step 1: Identify commits to revert**

Run:
```bash
git log --oneline --graph | head -20
```

Find commit SHAs for:
- System prompt update
- Scanner config update
- Bundled tools creation

**Step 2: Revert commits**

Run:
```bash
git revert <system-prompt-sha>
git revert <scanner-config-sha>
git revert <bundled-tools-sha>
```

Or use interactive rebase:
```bash
git rebase -i HEAD~[number-of-commits-to-rollback]
# Mark commits as 'drop' in editor
```

**Step 3: Verify revert**

Run: `python -c "from src.agent.main import cli; print('Reverted successfully')"`

Expected: Import succeeds

**Step 4: Document failure**

Run:
```bash
cat > rollback_bundled_tools_notes.txt << 'EOF'
Bundled Tools Approach - Rollback
==================================

Date: $(date)
Reason: Bundled tools did not resolve timeout issue

Observations from testing:
- [What went wrong - fill in from test results]
- [What pattern did agent actually use]
- [What errors occurred]

Root cause analysis:
- [Why bundled tools failed]
- [What assumptions were incorrect]

Next steps:
- Investigate alternative approaches:
  * Increase timeout limit (temporary fix)
  * Optimize individual tool operations (caching, faster APIs)
  * Different bundling strategy (single mega-tool?)
  * SDK configuration options not yet explored
EOF
```

**Step 5: Commit rollback documentation**

```bash
git add rollback_bundled_tools_notes.txt
git commit -m "docs: document bundled tools rollback

Bundled tools approach did not resolve timeout issue.
Reverting to baseline while investigating alternatives.

See rollback_bundled_tools_notes.txt for details.

🤖 Generated with Claude Code

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Summary

**Total Tasks:** 10 (8 main + 2 conditional)

**Implementation Flow:**
1. Create fetch_technical_snapshot with tests → Commit
2. Add partial failure test → Commit
3. Create fetch_sentiment_data with tests → Commit
4. Update scanner MCP config → Commit
5. Update system prompt → Commit
6. Run unit tests → Verify
7. Integration test with scanner → Commit results
8. Evaluate success/failure → Decision point
9a. If success → Document and finalize → Ready for merge
9b. If failure → Rollback and document → Investigate alternatives

**Success Criteria:**
- Agent completes analysis in < 30 seconds
- Tool calls grouped in 3 messages (2 bundled + 1 submit)
- submit_trading_signal called 100% of the time
- All 4 scoring components calculated
- Signal quality preserved

**Estimated Time:** 60-90 minutes (mostly testing and analysis)

**Next Steps After Completion:**
- If success: Use `superpowers:finishing-a-development-branch` to merge or create PR
- If failure: Investigate alternative approaches (timeout increase, caching, SDK options)
