# src/agent/pipeline/dashboard/events.py
"""Event types for pipeline dashboard updates."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any
from datetime import datetime


class StageStatus(Enum):
    """Status of a pipeline stage."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass
class StageEvent:
    """Event emitted by orchestrator for dashboard updates."""
    stage: str  # "analysis", "risk_auditor", "execution", "pnl_auditor"
    status: StageStatus
    symbol: str
    elapsed_ms: int
    output: Optional[Dict[str, Any]] = None
    message: Optional[str] = None
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class PipelineState:
    """Current state of the entire pipeline."""
    symbol: str
    session_id: str
    started_at: datetime = field(default_factory=datetime.now)
    stages: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    final_outcome: Optional[str] = None

    def __post_init__(self):
        """Initialize stage tracking."""
        if not self.stages:
            self.stages = {
                "analysis": {"status": StageStatus.PENDING, "elapsed_ms": 0, "output": None},
                "risk_auditor": {"status": StageStatus.PENDING, "elapsed_ms": 0, "output": None},
                "execution": {"status": StageStatus.PENDING, "elapsed_ms": 0, "output": None},
                "pnl_auditor": {"status": StageStatus.PENDING, "elapsed_ms": 0, "output": None},
            }

    def update(self, event: StageEvent) -> None:
        """Update state from event."""
        if event.stage in self.stages:
            self.stages[event.stage]["status"] = event.status
            self.stages[event.stage]["elapsed_ms"] = event.elapsed_ms
            if event.output:
                self.stages[event.stage]["output"] = event.output
            if event.message:
                self.stages[event.stage]["message"] = event.message
            if event.error:
                self.stages[event.stage]["error"] = event.error

    def get_current_stage(self) -> Optional[str]:
        """Get the currently running stage."""
        for stage_name, stage_data in self.stages.items():
            if stage_data["status"] == StageStatus.RUNNING:
                return stage_name
        return None
