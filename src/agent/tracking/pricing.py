"""Token pricing calculator for Claude API usage."""
from typing import Dict, Any


class TokenPricingCalculator:
    """Calculate costs based on token usage."""

    def __init__(
        self,
        cost_per_1m_input: float = 3.0,
        cost_per_1m_output: float = 15.0,
        model: str = "claude-sonnet-4-5"
    ):
        """
        Initialize pricing calculator.

        Args:
            cost_per_1m_input: Cost per 1M input tokens (default: Sonnet 4.5)
            cost_per_1m_output: Cost per 1M output tokens (default: Sonnet 4.5)
            model: Model name for reference
        """
        self.cost_per_1m_input = cost_per_1m_input
        self.cost_per_1m_output = cost_per_1m_output
        self.model = model

    def calculate_cost(
        self,
        tokens_input: int,
        tokens_output: int
    ) -> float:
        """
        Calculate total cost for token usage.

        Args:
            tokens_input: Number of input tokens
            tokens_output: Number of output tokens

        Returns:
            Total cost in USD
        """
        input_cost = (tokens_input / 1_000_000) * self.cost_per_1m_input
        output_cost = (tokens_output / 1_000_000) * self.cost_per_1m_output

        return input_cost + output_cost

    def get_pricing_info(self) -> Dict[str, Any]:
        """
        Get pricing configuration.

        Returns:
            Dictionary with pricing information
        """
        return {
            'model': self.model,
            'cost_per_1m_input': self.cost_per_1m_input,
            'cost_per_1m_output': self.cost_per_1m_output
        }
