"""Core token tracker for Claude Agent SDK."""
import time
from pathlib import Path
from typing import Any, Dict, Optional

from src.agent.tracking.pricing import TokenPricingCalculator
from src.agent.database.token_operations import TokenDatabase
from src.agent.config import config


class TokenTracker:
    """Tracks token usage for Claude Agent SDK calls."""

    def __init__(
        self,
        db_path: Path,
        operation_mode: str,
        pricing_calculator: Optional[TokenPricingCalculator] = None
    ):
        """
        Initialize token tracker.

        Args:
            db_path: Path to tracking database
            operation_mode: Type of operation (monitor, analyze, scan)
            pricing_calculator: Optional custom pricing calculator
        """
        self.db = TokenDatabase(db_path)
        self.operation_mode = operation_mode
        self.pricing = pricing_calculator or TokenPricingCalculator(
            cost_per_1m_input=config.CLAUDE_COST_PER_1M_INPUT,
            cost_per_1m_output=config.CLAUDE_COST_PER_1M_OUTPUT
        )

        self.session_id: Optional[str] = None
        self.is_active = False

    async def start_session(self) -> str:
        """
        Start a new tracking session.

        Returns:
            Session ID
        """
        self.session_id = await self.db.create_session(self.operation_mode)
        self.is_active = True
        return self.session_id

    async def record_usage(
        self,
        result: Any,
        operation_type: str,
        duration_seconds: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Record token usage from agent result.

        Args:
            result: Agent result with usage attribute
            operation_type: Type of operation
            duration_seconds: Request duration
            metadata: Additional context
        """
        if not self.is_active or not self.session_id:
            raise RuntimeError("Session not started")

        # Extract token counts from result
        # ResultMessage has usage dict with input_tokens and output_tokens
        usage = getattr(result, 'usage', {})
        tokens_input = usage.get('input_tokens', 0)
        tokens_output = usage.get('output_tokens', 0)

        # Get model name - may be in result or metadata
        model = getattr(result, 'model', metadata.get('model', 'unknown')) if metadata else getattr(result, 'model', 'unknown')

        # Calculate cost
        cost_usd = self.pricing.calculate_cost(tokens_input, tokens_output)

        # Record in database
        await self.db.record_token_usage(
            session_id=self.session_id,
            operation_type=operation_type,
            model=model,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            cost_usd=cost_usd,
            duration_seconds=duration_seconds,
            metadata=metadata
        )

    async def get_session_stats(self) -> Dict[str, Any]:
        """
        Get current session statistics.

        Returns:
            Session data
        """
        if not self.session_id:
            raise RuntimeError("Session not started")

        return await self.db.get_session(self.session_id)

    async def get_rate_limit_status(self) -> Dict[str, Any]:
        """
        Get rate limit status.

        Returns:
            Dictionary with hourly and daily usage vs limits
        """
        hourly_usage = await self.db.get_hourly_usage()
        daily_usage = await self.db.get_daily_usage()

        return {
            'hourly': {
                'request_count': hourly_usage['request_count'],
                'limit': config.CLAUDE_HOURLY_LIMIT,
                'percentage': (hourly_usage['request_count'] / config.CLAUDE_HOURLY_LIMIT) * 100
            },
            'daily': {
                'request_count': daily_usage['request_count'],
                'limit': config.CLAUDE_DAILY_LIMIT,
                'percentage': (daily_usage['request_count'] / config.CLAUDE_DAILY_LIMIT) * 100
            }
        }

    async def end_session(self):
        """End the current tracking session."""
        if self.session_id:
            await self.db.end_session(self.session_id)
            self.is_active = False
