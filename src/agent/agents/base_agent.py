"""Base class for all pipeline agents."""
import json
import time
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

from src.agent.database.agent_operations import AgentOperations

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Base class for all pipeline agents."""

    agent_type: str = None  # Must be overridden by subclass

    def __init__(self, db_ops: AgentOperations):
        """
        Initialize base agent.

        Args:
            db_ops: Database operations instance for saving outputs
        """
        if self.agent_type is None:
            raise NotImplementedError("Subclass must define agent_type")

        self.db_ops = db_ops

    @abstractmethod
    async def run(self, input_data: dict) -> dict:
        """
        Execute agent logic. Must be implemented by subclass.

        Args:
            input_data: Input data for the agent

        Returns:
            Agent output as dictionary
        """
        pass

    async def run_with_tracking(
        self,
        session_id: str,
        symbol: str,
        input_data: dict
    ) -> dict:
        """
        Run agent with automatic output tracking.

        Args:
            session_id: Unique session identifier
            symbol: Trading symbol being analyzed
            input_data: Input data for the agent

        Returns:
            Agent output as dictionary
        """
        start_time = time.time()
        tokens_used = 0  # Will be populated by Claude client

        try:
            output_data = await self.run(input_data)

            duration_ms = int((time.time() - start_time) * 1000)

            # Save output to database
            await self._save_output(
                session_id=session_id,
                symbol=symbol,
                input_data=input_data,
                output_data=output_data,
                tokens_used=tokens_used,
                duration_ms=duration_ms
            )

            return output_data

        except Exception as e:
            logger.error(f"{self.agent_type} failed: {e}", exc_info=True)
            raise

    async def _save_output(
        self,
        session_id: str,
        symbol: str,
        input_data: dict,
        output_data: dict,
        tokens_used: int,
        duration_ms: int
    ) -> None:
        """
        Save agent output to database for audit trail.

        Args:
            session_id: Unique session identifier
            symbol: Trading symbol
            input_data: Input that was provided to agent
            output_data: Output produced by agent
            tokens_used: Number of tokens consumed
            duration_ms: Execution duration in milliseconds
        """
        await self.db_ops.save_agent_output(
            session_id=session_id,
            symbol=symbol,
            agent_type=self.agent_type,
            input_json=json.dumps(input_data),
            output_json=json.dumps(output_data),
            tokens_used=tokens_used,
            duration_ms=duration_ms
        )

        logger.info(
            f"Saved {self.agent_type} output for {symbol} "
            f"(session: {session_id}, duration: {duration_ms}ms)"
        )
