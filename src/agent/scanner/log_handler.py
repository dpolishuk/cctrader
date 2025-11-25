# src/agent/scanner/log_handler.py
"""Log handler for split-screen dashboard display."""
import logging
from collections import deque
from datetime import datetime
from typing import List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.text import Text


class LogBuffer:
    """Thread-safe circular buffer for log lines."""

    def __init__(self, max_lines: int = 500):
        """
        Initialize log buffer.

        Args:
            max_lines: Maximum number of lines to keep.
        """
        self.max_lines = max_lines
        self._lines: deque = deque(maxlen=max_lines)

    def add(self, line: str) -> None:
        """Add a line to the buffer."""
        self._lines.append(line)

    def get_lines(self) -> List[str]:
        """Get all lines in the buffer."""
        return list(self._lines)

    def get_recent(self, n: int) -> List[str]:
        """Get the most recent n lines."""
        lines = list(self._lines)
        return lines[-n:] if n < len(lines) else lines

    def clear(self) -> None:
        """Clear all lines from the buffer."""
        self._lines.clear()

    def __len__(self) -> int:
        return len(self._lines)


class DashboardLogHandler(logging.Handler):
    """Custom logging handler that writes to a LogBuffer."""

    def __init__(self, buffer: LogBuffer, level: int = logging.NOTSET):
        """
        Initialize the dashboard log handler.

        Args:
            buffer: LogBuffer to write to.
            level: Logging level.
        """
        super().__init__(level)
        self.buffer = buffer

    def emit(self, record: logging.LogRecord) -> None:
        """
        Emit a log record to the buffer.

        Args:
            record: Log record to emit.
        """
        try:
            msg = self.format(record)
            self.buffer.add(msg)
        except Exception:
            self.handleError(record)


class SplitScreenManager:
    """Manager for split-screen dashboard with scrolling logs."""

    # Log level colors
    LEVEL_STYLES = {
        "DEBUG": "dim",
        "INFO": "white",
        "WARNING": "yellow",
        "ERROR": "red",
        "CRITICAL": "bold red",
    }

    def __init__(
        self,
        max_log_lines: int = 500,
        log_display_lines: int = 10,
    ):
        """
        Initialize split screen manager.

        Args:
            max_log_lines: Maximum lines to buffer.
            log_display_lines: Lines to show in display.
        """
        self.log_buffer = LogBuffer(max_lines=max_log_lines)
        self.log_display_lines = log_display_lines
        self._handler: Optional[DashboardLogHandler] = None
        self.console = Console()

    def get_log_handler(self) -> DashboardLogHandler:
        """
        Get or create the log handler.

        Returns:
            DashboardLogHandler instance.
        """
        if self._handler is None:
            self._handler = DashboardLogHandler(self.log_buffer)
            self._handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s %(levelname)s %(message)s",
                    datefmt="%H:%M:%S",
                )
            )
        return self._handler

    def get_recent_logs(self, n: Optional[int] = None) -> List[str]:
        """
        Get recent log lines.

        Args:
            n: Number of lines (defaults to log_display_lines).

        Returns:
            List of log line strings.
        """
        n = n or self.log_display_lines
        return self.log_buffer.get_recent(n)

    def _colorize_log_line(self, line: str) -> Text:
        """
        Apply color to a log line based on level.

        Args:
            line: Log line string.

        Returns:
            Rich Text object with styling.
        """
        text = Text()

        # Try to detect level from line
        for level, style in self.LEVEL_STYLES.items():
            if f" {level} " in line:
                text.append(line, style=style)
                return text

        # Default styling
        text.append(line, style="dim white")
        return text

    def render_log_panel(self, height: int = 10) -> Panel:
        """
        Render the log display panel.

        Args:
            height: Number of lines to show.

        Returns:
            Rich Panel with log output.
        """
        lines = self.get_recent_logs(height)

        content = Text()
        for i, line in enumerate(lines):
            content.append_text(self._colorize_log_line(line))
            if i < len(lines) - 1:
                content.append("\n")

        # Add padding if not enough lines
        if len(lines) < height:
            for _ in range(height - len(lines)):
                content.append("\n")

        return Panel(
            content,
            title="[bold dim]LOG OUTPUT[/bold dim]",
            border_style="dim blue",
            height=height + 2,  # Account for border
        )

    def install_handler(self, logger_name: Optional[str] = None) -> None:
        """
        Install the log handler on a logger.

        Args:
            logger_name: Logger name (None for root logger).
        """
        handler = self.get_log_handler()
        logger = logging.getLogger(logger_name)
        logger.addHandler(handler)

    def remove_handler(self, logger_name: Optional[str] = None) -> None:
        """
        Remove the log handler from a logger.

        Args:
            logger_name: Logger name (None for root logger).
        """
        if self._handler:
            logger = logging.getLogger(logger_name)
            logger.removeHandler(self._handler)
