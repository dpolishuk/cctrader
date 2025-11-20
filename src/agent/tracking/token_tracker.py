"""Core token tracker for Claude Agent SDK."""
import time
import logging
from pathlib import Path
from typing import Any, Dict, Optional, List

from src.agent.tracking.pricing import TokenPricingCalculator
from src.agent.database.token_operations import TokenDatabase
from src.agent.config import config

logger = logging.getLogger(__name__)


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

        # Interval tracking state
        self.interval_start_time: Optional[float] = None
        self.interval_number: int = 0
        self.current_interval: Dict[str, Any] = {
            'tokens_input': 0,
            'tokens_output': 0,
            'cost': 0.0,
            'requests': 0
        }
        self.completed_intervals: List[Dict[str, Any]] = []
        self.INTERVAL_DURATION = config.TOKEN_INTERVAL_MINUTES * 60  # Convert to seconds

    async def start_session(self) -> str:
        """
        Start a new tracking session.

        Returns:
            Session ID
        """
        self.session_id = await self.db.create_session(self.operation_mode)
        self.is_active = True

        # Initialize interval tracking
        self.interval_start_time = time.time()
        self.interval_number = 1
        self.current_interval = {
            'tokens_input': 0,
            'tokens_output': 0,
            'cost': 0.0,
            'requests': 0
        }
        self.completed_intervals = []

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

        # Check if interval should complete BEFORE accumulating new data
        self._check_and_complete_interval()

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

        # Accumulate to current interval
        self.current_interval['tokens_input'] += tokens_input
        self.current_interval['tokens_output'] += tokens_output
        self.current_interval['cost'] += cost_usd
        self.current_interval['requests'] += 1

    def _check_and_complete_interval(self):
        """Check if interval duration elapsed and complete it if so."""
        if not self.interval_start_time:
            return False

        elapsed = time.time() - self.interval_start_time

        if elapsed >= self.INTERVAL_DURATION:
            # Complete current interval
            interval_data = {
                'interval_number': self.interval_number,
                'duration_seconds': elapsed,
                'tokens_input': self.current_interval['tokens_input'],
                'tokens_output': self.current_interval['tokens_output'],
                'tokens_total': self.current_interval['tokens_input'] + self.current_interval['tokens_output'],
                'cost': self.current_interval['cost'],
                'requests': self.current_interval['requests']
            }

            self.completed_intervals.append(interval_data)

            # Log interval summary
            logger.info(
                f"[+{self.interval_number * config.TOKEN_INTERVAL_MINUTES}min] "
                f"Interval {self.interval_number}: "
                f"{interval_data['tokens_total']:,} tokens "
                f"({interval_data['tokens_input']:,} in, {interval_data['tokens_output']:,} out) | "
                f"Cost: ${interval_data['cost']:.4f} | "
                f"{interval_data['requests']} requests"
            )

            # Reset for next interval
            self.interval_number += 1
            self.interval_start_time = time.time()
            self.current_interval = {
                'tokens_input': 0,
                'tokens_output': 0,
                'cost': 0.0,
                'requests': 0
            }

            return True

        return False

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
            # Capture final partial interval if any usage recorded
            if self.current_interval['requests'] > 0:
                elapsed = time.time() - self.interval_start_time if self.interval_start_time else 0
                interval_data = {
                    'interval_number': self.interval_number,
                    'duration_seconds': elapsed,
                    'tokens_input': self.current_interval['tokens_input'],
                    'tokens_output': self.current_interval['tokens_output'],
                    'tokens_total': self.current_interval['tokens_input'] + self.current_interval['tokens_output'],
                    'cost': self.current_interval['cost'],
                    'requests': self.current_interval['requests']
                }
                self.completed_intervals.append(interval_data)

            await self.db.end_session(self.session_id)
            self.is_active = False
