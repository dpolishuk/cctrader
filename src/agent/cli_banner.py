"""CLI banner for displaying session information.

This module provides a Rich-formatted banner that displays session information
at the start of each command, including model name, API endpoint, token tracking
status, and session information.
"""
import logging
from typing import Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .config import config
from .session_manager import SessionManager

logger = logging.getLogger(__name__)


class SessionBanner:
    """Creates and displays formatted session information banners."""

    @staticmethod
    def display(
        model: str,
        api_endpoint: str,
        token_tracking_enabled: bool,
        session_id: Optional[str],
        operation_type: str,
        session_status: str  # "resumed" or "new"
    ):
        """
        Display session information banner.

        Args:
            model: Model name (e.g., "claude-sonnet-4-5")
            api_endpoint: Anthropic API endpoint URL
            token_tracking_enabled: Whether token tracking is enabled
            session_id: Session ID if available (will be truncated for display)
            operation_type: Type of operation (scanner, analysis, monitor, paper_trading)
            session_status: "resumed" or "new"
        """
        console = Console()

        # Create table for banner content
        table = Table.grid(padding=(0, 2))
        table.add_column(style="dim", justify="left")
        table.add_column(style="white", justify="left")

        # Add rows
        table.add_row("Model:", model)
        table.add_row("API Endpoint:", api_endpoint)

        # Token tracking status with indicator
        if token_tracking_enabled:
            if session_id:
                # Truncate session ID to 8 chars + "..."
                truncated_id = session_id[:8] + "..." if len(session_id) > 8 else session_id
                token_status = f"[green]✓[/green] Enabled (Session: {truncated_id})"
            else:
                token_status = "[green]✓[/green] Enabled (Session: N/A)"
        else:
            token_status = "[yellow]⚠[/yellow] Disabled"

        table.add_row("Token Tracking:", token_status)
        table.add_row("Operation:", operation_type)

        # Session status
        if session_status == "resumed" and session_id:
            truncated_id = session_id[:8] + "..." if len(session_id) > 8 else session_id
            status_text = f"Resuming {truncated_id}"
        elif session_status == "new":
            status_text = "New session created"
        else:
            status_text = "Session tracking: Not available"

        table.add_row("Session Status:", status_text)

        # Create panel with table
        panel = Panel(
            table,
            title="Session Information",
            border_style="cyan",
            padding=(1, 2)
        )

        console.print()
        console.print(panel)
        console.print()


async def show_session_banner(
    operation_type: str,
    model: str = "claude-sonnet-4-5",
    session_manager: Optional[SessionManager] = None
):
    """
    Gather session information and display banner.

    This helper function collects all necessary information from various sources
    and displays the session banner. It handles errors gracefully to ensure
    command execution continues even if banner display fails.

    Args:
        operation_type: Type of operation (scanner, analysis, monitor, paper_trading)
        model: Model name to display (default: "claude-sonnet-4-5")
        session_manager: Optional SessionManager instance for session info

    Raises:
        Does not raise exceptions - logs warnings on failure
    """
    try:
        # Get API endpoint from config (with fallback)
        import os
        api_endpoint = os.getenv("ANTHROPIC_API_URL", "https://api.anthropic.com")

        # Get token tracking status
        token_tracking_enabled = config.TOKEN_TRACKING_ENABLED

        # Get session information
        session_id = None
        session_status = "new"

        if session_manager:
            try:
                # Check if session exists for this operation
                session_id = await session_manager.get_session_id(operation_type)
                if session_id:
                    session_status = "resumed"
            except Exception as e:
                logger.warning(f"Failed to retrieve session info: {e}")
                session_id = None

        # Display banner
        SessionBanner.display(
            model=model,
            api_endpoint=api_endpoint,
            token_tracking_enabled=token_tracking_enabled,
            session_id=session_id,
            operation_type=operation_type,
            session_status=session_status
        )

    except Exception as e:
        # Log warning but don't crash the command
        logger.warning(f"Failed to display session banner: {e}")
