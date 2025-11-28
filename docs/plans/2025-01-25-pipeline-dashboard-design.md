# Multi-Agent Pipeline Dashboard Design

## Overview

A real-time CLI dashboard for monitoring the 4-agent trading pipeline, built with Rich library.

## Design Decisions

| Question | Choice |
|----------|--------|
| Display Type | Real-time CLI Dashboard |
| Visual Layout | Vertical stacked panels |
| Detail Level | Detailed with scores, reasoning, metrics |
| Dashboard Layout | Full: header + pipeline + sidebar + history |
| Update Behavior | Hybrid: live progress + redraw on completion |
| Color Scheme | Trading Pro (red/green, bold contrast) |
| Data Flow Viz | Connector arrows + delta highlighting |

## Visual Layout

```
╔══════════════════════════════════════════════════════════════════════════════╗
║  CCTRADER PIPELINE  │ BTCUSDT │ 14:35:22 │ Session: scanner-2025-01-25      ║
╠═══════════════════════════════════════════════════════════╦══════════════════╣
║ ┏━ Stage 1: Analysis Agent ━━━━━━━━━━━━━━ ✓ COMPLETE ━━━┓ ║ PORTFOLIO        ║
║ ┃ ▲ LONG @ $67,500 │ SL: $64,125 │ TP: $72,900         ┃ ║ Equity: $10,450  ║
║ ┃ Tech:35/40 │ Sent:22/30 │ Liq:15/20 │ Conf: 72       ┃ ║ Positions: 3     ║
║ ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛ ║ Exposure: 12%    ║
║                          │                                ║ Daily: +1.2%     ║
║                          ▼ proposed_signal                ║ Weekly: +3.8%    ║
║                          │                                ╠══════════════════╣
║ ┏━ Stage 2: Risk Auditor ━━━━━━━━━━━━━━━ MODIFY ━━━━━━━┓ ║ AGENT STATS      ║
║ ┃ CHANGES: conf 72→68, size 3%→2.5%                    ┃ ║ Analyzed: 12     ║
║ ┃ ⚠ WARNING: High BTC correlation                      ┃ ║ Approved: 8      ║
║ ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛ ║ Executed: 6      ║
║                          │                                ║ Win Rate: 67%    ║
║                          ▼ audited_signal (modified)      ║                  ║
║                          │                                ║                  ║
║ ┏━ Stage 3: Execution Agent ━━━━━━━━━━━━ ⏳ RUNNING ━━━┓ ║                  ║
║ ┃ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ 1.2s                 ┃ ║                  ║
║ ┃ Checking spread and orderbook depth...               ┃ ║                  ║
║ ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛ ║                  ║
╠═══════════════════════════════════════════════════════════╩══════════════════╣
║ HISTORY: ETHUSDT→NO_TRADE │ SOLUSDT→REJECTED │ AVAXUSDT→EXECUTED (+0.8%)     ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

## File Structure

```
src/agent/pipeline/
├── __init__.py              # Existing
├── orchestrator.py          # Existing
├── dashboard/
│   ├── __init__.py
│   ├── pipeline_dashboard.py    # Main dashboard controller
│   ├── stage_panels.py          # Individual stage panel renderers
│   ├── sidebar.py               # Portfolio & stats sidebar
│   ├── history_feed.py          # Recent results feed
│   ├── styles.py                # Color scheme & styling constants
│   └── events.py                # Event types for stage updates
```

## Components

### 1. PipelineDashboard (Main Controller)
- Creates Rich Layout with regions
- Manages Live display context
- Receives events from orchestrator
- Coordinates panel updates

### 2. StagePanel (Per-Agent Renderer)
- Renders detailed panel for each agent
- States: PENDING, RUNNING, COMPLETE, SKIPPED
- Shows progress bar when running
- Shows full content when complete
- Handles delta highlighting for changes

### 3. Sidebar
- Portfolio snapshot (equity, positions, exposure, P&L)
- Agent stats (analyzed, approved, executed, win rate)
- Updates after each pipeline completion

### 4. HistoryFeed
- Rolling list of recent pipeline results
- Shows: symbol, outcome, key detail
- Max 5-10 entries visible

### 5. Styles
- Trading Pro color constants
- Border styles for different states
- Status indicators and icons

## Color Scheme (Trading Pro)

```python
COLORS = {
    # Status
    "success": "bold bright_green",
    "error": "bold red",
    "warning": "bold yellow",
    "running": "bold cyan",
    "pending": "dim white",

    # Trading
    "long": "bold bright_green",
    "short": "bold red",
    "bullish": "green",
    "bearish": "red",

    # Data
    "price": "white",
    "change_up": "green",
    "change_down": "red",
    "unchanged": "dim white",

    # Borders
    "border_running": "cyan",
    "border_complete": "green",
    "border_rejected": "yellow",
    "border_error": "red",
    "border_pending": "dim white",
}

ICONS = {
    "long": "▲",
    "short": "▼",
    "complete": "✓",
    "running": "⏳",
    "pending": "○",
    "warning": "⚠",
    "error": "✗",
    "arrow_down": "▼",
}
```

## Event System

```python
@dataclass
class StageEvent:
    """Event emitted by orchestrator for dashboard updates."""
    stage: str  # "analysis", "risk_auditor", "execution", "pnl_auditor"
    status: str  # "started", "running", "complete", "error"
    symbol: str
    elapsed_ms: int
    output: Optional[Dict[str, Any]] = None
    message: Optional[str] = None  # For running status updates
```

## Integration with Orchestrator

The orchestrator will emit events via callback:

```python
class PipelineOrchestrator:
    def __init__(self, ..., event_callback: Optional[Callable] = None):
        self.event_callback = event_callback

    async def run_pipeline(self, ...):
        # Before each stage
        self._emit_event(StageEvent(stage="analysis", status="started", ...))

        # During long operations (optional)
        self._emit_event(StageEvent(stage="analysis", status="running", message="Fetching sentiment..."))

        # After completion
        self._emit_event(StageEvent(stage="analysis", status="complete", output=analysis_output))
```

## Panel Content Details

### Analysis Agent Panel (Complete)
```
┏━ Stage 1: Analysis Agent ━━━━━━━━━━━━━━━━━ ✓ COMPLETE (2.3s) ━━━┓
┃ PROPOSED SIGNAL                                                  ┃
┃   ▲ LONG BTCUSDT @ $67,500.00                                   ┃
┃   Stop Loss: $64,125.00 (-5.0%)  Take Profit: $72,900.00 (+8.0%)┃
┃   Position Size: 3.0% of portfolio                               ┃
┃                                                                  ┃
┃ SCORING                                                          ┃
┃   Technical:  ████████░░ 35/40   Sentiment: ██████░░░░ 22/30    ┃
┃   Liquidity:  ███████░░░ 15/20   Correlation: ████████░░ 0/10   ┃
┃   Total Confidence: 72/100                                       ┃
┃                                                                  ┃
┃ REASONING                                                        ┃
┃   Strong uptrend on 4h with momentum confirmation. RSI not       ┃
┃   overbought. Volume increasing on breakout.                     ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
```

### Risk Auditor Panel (with Delta)
```
┏━ Stage 2: Risk Auditor ━━━━━━━━━━━━━━━━━━━ MODIFY (1.8s) ━━━━━━━┓
┃ DECISION: MODIFY                                                 ┃
┃                                                                  ┃
┃ CHANGES FROM ANALYSIS                                            ┃
┃   Confidence:    72 → 68 (-4)                                    ┃
┃   Position Size: 3.0% → 2.5% (-0.5%)                            ┃
┃   Stop Loss:     $64,125 → $64,125 (unchanged)                  ┃
┃                                                                  ┃
┃ WARNINGS                                                         ┃
┃   ⚠ High correlation with existing BTC position                 ┃
┃   ⚠ Approaching daily exposure limit (12% → 14.5%)              ┃
┃                                                                  ┃
┃ RISK SCORE: 35/100 (acceptable)                                  ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
```

### Execution Agent Panel (Complete)
```
┏━ Stage 3: Execution Agent ━━━━━━━━━━━━━━━━ ✓ FILLED (0.9s) ━━━━━┓
┃ ORDER EXECUTED                                                   ┃
┃   Type: LIMIT                                                    ┃
┃   Requested: $67,500.00    Filled: $67,489.50                   ┃
┃   Slippage: -0.016% (better than expected)                      ┃
┃                                                                  ┃
┃ POSITION OPENED                                                  ┃
┃   Size: 0.0037 BTC ($249.91)                                    ┃
┃   Entry: $67,489.50                                              ┃
┃   Stop Loss: $64,125.00    Take Profit: $72,900.00              ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
```

### Running State Panel
```
┏━ Stage 3: Execution Agent ━━━━━━━━━━━━━━━━ ⏳ RUNNING ━━━━━━━━━━┓
┃                                                                  ┃
┃   ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  1.2s elapsed    ┃
┃                                                                  ┃
┃   Checking orderbook depth and spread...                         ┃
┃                                                                  ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
```

## Usage Example

```python
from src.agent.pipeline.dashboard import PipelineDashboard
from src.agent.pipeline.orchestrator import PipelineOrchestrator

# Create dashboard
dashboard = PipelineDashboard()

# Create orchestrator with dashboard callback
orchestrator = PipelineOrchestrator(
    analysis_agent=analysis,
    risk_auditor=risk,
    execution_agent=execution,
    pnl_auditor=pnl,
    db_ops=db_ops,
    event_callback=dashboard.handle_event
)

# Run with live display
async with dashboard.live_display():
    result = await orchestrator.run_pipeline(
        session_id="scanner-2025-01-25",
        symbol="BTCUSDT",
        momentum_data={"1h": 5.0, "4h": 10.0},
        portfolio_state=portfolio_state
    )
```

## Implementation Tasks

1. **Task 10: Dashboard Styles & Events** - Create styles.py and events.py
2. **Task 11: Stage Panel Renderer** - Create stage_panels.py with all panel types
3. **Task 12: Sidebar Components** - Create sidebar.py for portfolio/stats
4. **Task 13: History Feed** - Create history_feed.py for recent results
5. **Task 14: Main Dashboard** - Create pipeline_dashboard.py controller
6. **Task 15: Orchestrator Integration** - Add event callbacks to orchestrator
7. **Task 16: CLI Integration** - Add dashboard option to scan-movers command
