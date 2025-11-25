# Scanner Dashboard Integration Design

## Overview

Integrate the pipeline dashboard visualization into the `scan-movers` command via a `--dashboard` flag.

## Design Decisions

| Question | Choice |
|----------|--------|
| Activation | `--dashboard` flag (hybrid mode) |
| Visual Style | Full 4-panel dashboard mapped from single agent |
| Phase Mapping | Tool calls → dashboard stages |
| Queue Display | Cycle summary view (all movers with status) |
| Layout | Classic (pipeline left, sidebar right, history bottom) |
| Log Handling | Split screen - dashboard top, scrolling logs bottom |

## Layout Design

```
╔══════════════════════════════════════════════════════════════════════════════╗
║  MARKET MOVERS SCANNER  │ Cycle #5 │ 14:35:22 │ Session: scanner-2025-01-25  ║
╠═══════════════════════════════════════════════════════════╦══════════════════╣
║                                                           ║ PORTFOLIO        ║
║  CYCLE PROGRESS [██████░░░░] 3/5                         ║ $10,450 (+1.2%)  ║
║                                                           ║ 3 positions      ║
║  ▲ BTCUSDT  +7.2%  ✓ NO_TRADE    (45 conf)              ║ 12% exposure     ║
║  ▲ ETHUSDT  +5.8%  ✓ EXECUTED    @ $3,450               ╠══════════════════╣
║  ▼ SOLUSDT  -6.1%  ⏳ Analysis    [████░░░░] sentiment   ║ CYCLE STATS      ║
║  ▲ AVAXUSDT +5.2%  ○ Pending                             ║ Signals: 2       ║
║  ▼ LINKUSDT -5.5%  ○ Pending                             ║ Executed: 1      ║
║                                                           ║ Rejected: 0      ║
╠═══════════════════════════════════════════════════════════╩══════════════════╣
║ HISTORY: Cycle#4: 2 exec │ Cycle#3: 0 movers │ Today: 67% win (4/6)         ║
╚══════════════════════════════════════════════════════════════════════════════╝
─── LOG OUTPUT ────────────────────────────────────────────────────────────────
14:35:22 INFO 🔍 SCAN CYCLE #5 - Analyzing 5 movers
14:35:23 INFO BTCUSDT: Technical score 28/40, weak setup
```

## Phase Mapping

| Agent Tool/Action | Dashboard Stage | Status |
|-------------------|-----------------|--------|
| `fetch_technical_snapshot` | Analysis | ⏳ Running (technical) |
| `fetch_sentiment_data` | Analysis | ⏳ Running (sentiment) |
| `submit_trading_signal` | Analysis | ✓ Complete |
| `risk_validator.validate` | Risk Auditor | ⏳/✓ |
| `portfolio.execute` | Execution | ⏳/✓ |

## Implementation Tasks

### Task 1: Scanner Dashboard Component
Create `src/agent/scanner/dashboard.py` with:
- `ScannerDashboard` class extending/using pipeline dashboard components
- `MoverStatus` dataclass for tracking each mover
- `CycleState` dataclass for cycle-level tracking
- Methods for updating mover progress

### Task 2: Mover Row Renderer
Create `src/agent/pipeline/dashboard/mover_row.py` with:
- Compact row renderer for movers list
- Status icons and progress indicators
- Color coding for gainers/losers

### Task 3: Scanner Event Hooks
Modify `src/agent/scanner/main_loop.py` to:
- Add event callback support
- Emit events at key phases (analysis start, sentiment, signal, risk, execution)
- Pass dashboard callback through scanner

### Task 4: CLI Integration
Modify `src/agent/main.py` to:
- Add `--dashboard` flag to `scan-movers` command
- Create dashboard instance when flag enabled
- Wire up event callbacks
- Handle split-screen layout with Rich

### Task 5: Log Handler for Split Screen
Create custom log handler that:
- Captures log output
- Displays in scrolling region below dashboard
- Maintains dashboard above fold

## File Structure

```
src/agent/
├── scanner/
│   ├── main_loop.py      # Modified - add event hooks
│   └── dashboard.py      # NEW - scanner-specific dashboard
├── pipeline/
│   └── dashboard/
│       ├── mover_row.py  # NEW - mover row renderer
│       └── ...           # Existing components
└── main.py               # Modified - add --dashboard flag
```

## Component Details

### MoverStatus Dataclass
```python
@dataclass
class MoverStatus:
    symbol: str
    change_pct: float  # +7.2 or -6.1
    direction: str     # "gainer" or "loser"
    status: str        # "pending", "analyzing", "complete"
    stage: str         # "analysis", "risk", "execution"
    stage_detail: str  # "technical", "sentiment", etc.
    result: Optional[str]  # "NO_TRADE", "EXECUTED", "REJECTED"
    confidence: Optional[int]
    entry_price: Optional[float]
```

### CycleState Dataclass
```python
@dataclass
class CycleState:
    cycle_number: int
    started_at: datetime
    movers: List[MoverStatus]
    signals_generated: int
    trades_executed: int
    trades_rejected: int
```

### Event Types
```python
class ScannerEvent:
    CYCLE_START = "cycle_start"
    MOVER_START = "mover_start"
    ANALYSIS_PHASE = "analysis_phase"  # technical, sentiment
    SIGNAL_GENERATED = "signal_generated"
    RISK_CHECK = "risk_check"
    EXECUTION = "execution"
    MOVER_COMPLETE = "mover_complete"
    CYCLE_COMPLETE = "cycle_complete"
```
