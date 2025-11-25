"""Pipeline orchestrator for multi-agent trading system."""
import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any

from src.agent.agents.base_agent import BaseAgent
from src.agent.database.agent_operations import AgentOperations

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """Result of pipeline execution."""
    status: str  # NO_TRADE, REJECTED, ABORTED, EXECUTED
    stage: str  # Which stage produced this result
    analysis_output: Optional[Dict[str, Any]] = None
    risk_output: Optional[Dict[str, Any]] = None
    execution_output: Optional[Dict[str, Any]] = None
    position: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class PipelineOrchestrator:
    """Orchestrates the 4-agent trading pipeline."""

    def __init__(
        self,
        analysis_agent: BaseAgent,
        risk_auditor: BaseAgent,
        execution_agent: BaseAgent,
        pnl_auditor: BaseAgent,
        db_ops: AgentOperations
    ):
        """
        Initialize pipeline orchestrator.

        Args:
            analysis_agent: Analysis Agent instance
            risk_auditor: Risk Auditor Agent instance
            execution_agent: Execution Agent instance
            pnl_auditor: P&L Auditor Agent instance
            db_ops: Database operations for audit trail
        """
        self.analysis_agent = analysis_agent
        self.risk_auditor = risk_auditor
        self.execution_agent = execution_agent
        self.pnl_auditor = pnl_auditor
        self.db_ops = db_ops

    async def run_pipeline(
        self,
        session_id: str,
        symbol: str,
        momentum_data: Dict[str, float],
        current_price: Optional[float] = None,
        volume_24h: Optional[float] = None,
        portfolio_state: Optional[Dict[str, Any]] = None
    ) -> PipelineResult:
        """
        Run the complete 4-agent pipeline.

        Args:
            session_id: Unique session identifier
            symbol: Trading symbol (e.g., "BTCUSDT")
            momentum_data: Dict with "1h" and "4h" momentum percentages
            current_price: Optional current price
            volume_24h: Optional 24h volume
            portfolio_state: Optional current portfolio state

        Returns:
            PipelineResult with status and outputs
        """
        logger.info(f"Starting pipeline for {symbol} (session: {session_id})")

        # Stage 1: Analysis
        logger.info("Stage 1: Running Analysis Agent")
        try:
            analysis_output = await self.analysis_agent.run_with_tracking(
                session_id=session_id,
                symbol=symbol,
                input_data={
                    "symbol": symbol,
                    "momentum_1h": momentum_data.get("1h", 0),
                    "momentum_4h": momentum_data.get("4h", 0),
                    "current_price": current_price,
                    "volume_24h": volume_24h
                }
            )
        except Exception as e:
            logger.error(f"Analysis Agent failed: {e}")
            return PipelineResult(
                status="ERROR",
                stage="analysis",
                error=str(e)
            )

        # Check if analysis produced a signal
        proposed_signal = analysis_output.get("proposed_signal")
        if proposed_signal is None:
            logger.info(f"Analysis Agent returned NO_TRADE for {symbol}")
            return PipelineResult(
                status="NO_TRADE",
                stage="analysis",
                analysis_output=analysis_output
            )

        # Stage 2: Risk Audit
        logger.info("Stage 2: Running Risk Auditor Agent")
        try:
            risk_output = await self.risk_auditor.run_with_tracking(
                session_id=session_id,
                symbol=symbol,
                input_data={
                    "analysis_output": analysis_output,
                    "portfolio_state": portfolio_state or {}
                }
            )
        except Exception as e:
            logger.error(f"Risk Auditor failed: {e}")
            return PipelineResult(
                status="ERROR",
                stage="risk_auditor",
                analysis_output=analysis_output,
                error=str(e)
            )

        # Check risk decision
        risk_decision = risk_output.get("risk_decision", {})
        action = risk_decision.get("action", "REJECT")

        if action == "REJECT":
            reason = risk_decision.get("reason", "Unknown")
            logger.info(f"Risk Auditor REJECTED signal for {symbol}: {reason}")
            return PipelineResult(
                status="REJECTED",
                stage="risk_auditor",
                analysis_output=analysis_output,
                risk_output=risk_output
            )

        # Stage 3: Execution
        audited_signal = risk_output.get("audited_signal")
        if audited_signal is None:
            logger.error("Risk Auditor approved but no audited_signal provided")
            return PipelineResult(
                status="ERROR",
                stage="risk_auditor",
                analysis_output=analysis_output,
                risk_output=risk_output,
                error="Missing audited_signal"
            )

        logger.info("Stage 3: Running Execution Agent")
        try:
            execution_output = await self.execution_agent.run_with_tracking(
                session_id=session_id,
                symbol=symbol,
                input_data={
                    "symbol": symbol,
                    "audited_signal": audited_signal,
                    "portfolio_equity": portfolio_state.get("equity", 10000) if portfolio_state else 10000
                }
            )
        except Exception as e:
            logger.error(f"Execution Agent failed: {e}")
            return PipelineResult(
                status="ERROR",
                stage="execution",
                analysis_output=analysis_output,
                risk_output=risk_output,
                error=str(e)
            )

        # Check execution result
        exec_report = execution_output.get("execution_report", {})
        exec_status = exec_report.get("status", "ABORTED")

        if exec_status == "ABORTED":
            reason = exec_report.get("reason", "Unknown")
            logger.info(f"Execution Agent ABORTED for {symbol}: {reason}")
            return PipelineResult(
                status="ABORTED",
                stage="execution",
                analysis_output=analysis_output,
                risk_output=risk_output,
                execution_output=execution_output
            )

        # Success!
        position = execution_output.get("position_opened")
        logger.info(f"Pipeline EXECUTED successfully for {symbol}")

        return PipelineResult(
            status="EXECUTED",
            stage="execution",
            analysis_output=analysis_output,
            risk_output=risk_output,
            execution_output=execution_output,
            position=position
        )

    async def run_trade_review(
        self,
        session_id: str,
        trade: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Run P&L Auditor for a closed trade.

        Args:
            session_id: Session identifier
            trade: Closed trade details

        Returns:
            Trade review output
        """
        return await self.pnl_auditor.run_with_tracking(
            session_id=session_id,
            symbol=trade.get("symbol", "UNKNOWN"),
            input_data={
                "mode": "TRADE_REVIEW",
                "trade": trade
            }
        )

    async def run_daily_report(
        self,
        session_id: str,
        date: str,
        trades: list
    ) -> Dict[str, Any]:
        """
        Run P&L Auditor for daily batch report.

        Args:
            session_id: Session identifier
            date: Report date (YYYY-MM-DD)
            trades: List of trades from the day

        Returns:
            Daily report output
        """
        return await self.pnl_auditor.run_with_tracking(
            session_id=session_id,
            symbol="PORTFOLIO",
            input_data={
                "mode": "DAILY_REPORT",
                "date": date,
                "trades": trades
            }
        )
