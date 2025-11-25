"""Pydantic schemas for agent communication."""
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field, field_validator


# === Analysis Agent Schemas ===

class AnalysisReport(BaseModel):
    """Raw analysis data from Analysis Agent."""
    symbol: str
    timestamp: str
    technical: Dict[str, Any]
    sentiment: Dict[str, Any]
    liquidity: Dict[str, Any]
    btc_correlation: float


class ProposedSignal(BaseModel):
    """Proposed trading signal from Analysis Agent."""
    direction: Literal["LONG", "SHORT"]
    confidence: int = Field(ge=0, le=100)
    entry_price: float = Field(gt=0)
    stop_loss: float = Field(gt=0)
    take_profit: float = Field(gt=0)
    position_size_pct: float = Field(gt=0, le=100)
    reasoning: str


class AnalysisAgentOutput(BaseModel):
    """Complete output from Analysis Agent."""
    analysis_report: AnalysisReport
    proposed_signal: Optional[ProposedSignal] = None


# === Risk Auditor Schemas ===

class RiskDecision(BaseModel):
    """Risk decision from Risk Auditor Agent."""
    action: Literal["APPROVE", "REJECT", "MODIFY"]
    original_confidence: int = Field(ge=0, le=100)
    audited_confidence: Optional[int] = Field(default=None, ge=0, le=100)
    modifications: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    risk_score: int = Field(ge=0, le=100)
    reason: Optional[str] = None  # For rejections


class AuditedSignal(BaseModel):
    """Signal after risk audit modifications."""
    direction: Literal["LONG", "SHORT"]
    confidence: int = Field(ge=0, le=100)
    entry_price: float = Field(gt=0)
    stop_loss: float = Field(gt=0)
    take_profit: float = Field(gt=0)
    position_size_pct: float = Field(gt=0, le=100)
    reasoning: str


class PortfolioSnapshot(BaseModel):
    """Portfolio state at time of risk decision."""
    equity: float
    open_positions: int
    current_exposure_pct: float
    daily_pnl_pct: float
    weekly_pnl_pct: float


class RiskAuditorOutput(BaseModel):
    """Complete output from Risk Auditor Agent."""
    risk_decision: RiskDecision
    audited_signal: Optional[AuditedSignal] = None
    portfolio_snapshot: PortfolioSnapshot


# === Execution Agent Schemas ===

class ExecutionReport(BaseModel):
    """Execution report from Execution Agent."""
    status: Literal["FILLED", "PARTIAL", "ABORTED"]
    order_type: Optional[Literal["MARKET", "LIMIT"]] = None
    requested_entry: float
    actual_entry: Optional[float] = None
    slippage_pct: Optional[float] = None
    position_size: Optional[float] = None
    position_value_usd: Optional[float] = None
    execution_time_ms: Optional[int] = None
    order_id: Optional[str] = None
    notes: Optional[str] = None
    # For aborted orders
    reason: Optional[str] = None
    current_price: Optional[float] = None
    price_deviation_pct: Optional[float] = None


class PositionOpened(BaseModel):
    """Position details when trade is executed."""
    symbol: str
    direction: Literal["LONG", "SHORT"]
    entry_price: float
    stop_loss: float
    take_profit: float
    size: float
    opened_at: str


class ExecutionAgentOutput(BaseModel):
    """Complete output from Execution Agent."""
    execution_report: ExecutionReport
    position_opened: Optional[PositionOpened] = None


# === P&L Auditor Schemas ===

class TradeReviewAnalysis(BaseModel):
    """Analysis section of trade review."""
    what_worked: List[str]
    what_didnt_work: List[str]
    agent_accuracy: Dict[str, Any]


class TradeReview(BaseModel):
    """Per-trade review from P&L Auditor."""
    trade_id: str
    symbol: str
    direction: Literal["LONG", "SHORT"]
    entry_price: float
    exit_price: float
    pnl_pct: float
    pnl_usd: float
    duration_hours: float
    result: Literal["WIN", "LOSS"]
    analysis: TradeReviewAnalysis
    recommendation: str


class DailyReportSummary(BaseModel):
    """Summary section of daily report."""
    total_trades: int
    wins: int
    losses: int
    win_rate: float
    total_pnl_pct: float
    total_pnl_usd: float
    best_trade: Optional[Dict[str, Any]] = None
    worst_trade: Optional[Dict[str, Any]] = None


class PatternIdentified(BaseModel):
    """Pattern identified in daily analysis."""
    pattern: str
    evidence: str
    recommendation: str


class AgentPerformance(BaseModel):
    """Performance metrics for each agent."""
    analysis_agent: Dict[str, Any]
    risk_auditor: Dict[str, Any]
    execution_agent: Dict[str, Any]


class DailyReport(BaseModel):
    """Daily batch report from P&L Auditor."""
    date: str
    summary: DailyReportSummary
    patterns_identified: List[PatternIdentified]
    agent_performance: AgentPerformance
    strategy_recommendations: List[str]


class PnlAuditorOutput(BaseModel):
    """Output from P&L Auditor (either trade review or daily report)."""
    mode: Literal["TRADE_REVIEW", "DAILY_REPORT"]
    trade_review: Optional[TradeReview] = None
    daily_report: Optional[DailyReport] = None
