# tests/test_dashboard_log_handler.py
"""Tests for dashboard log handler."""
import pytest
import logging
from io import StringIO
from unittest.mock import MagicMock, patch

from src.agent.scanner.log_handler import (
    DashboardLogHandler,
    LogBuffer,
    SplitScreenManager,
)


class TestLogBuffer:
    """Tests for LogBuffer class."""

    def test_create_buffer(self):
        """Test creating a log buffer."""
        buffer = LogBuffer(max_lines=100)
        assert buffer.max_lines == 100
        assert len(buffer) == 0

    def test_add_line(self):
        """Test adding lines to buffer."""
        buffer = LogBuffer(max_lines=10)
        buffer.add("Line 1")
        buffer.add("Line 2")
        assert len(buffer) == 2
        assert buffer.get_lines() == ["Line 1", "Line 2"]

    def test_max_lines_limit(self):
        """Test that buffer respects max_lines."""
        buffer = LogBuffer(max_lines=3)
        for i in range(5):
            buffer.add(f"Line {i}")
        assert len(buffer) == 3
        assert buffer.get_lines() == ["Line 2", "Line 3", "Line 4"]

    def test_get_recent_lines(self):
        """Test getting recent lines."""
        buffer = LogBuffer(max_lines=10)
        for i in range(5):
            buffer.add(f"Line {i}")
        recent = buffer.get_recent(3)
        assert recent == ["Line 2", "Line 3", "Line 4"]

    def test_clear_buffer(self):
        """Test clearing the buffer."""
        buffer = LogBuffer()
        buffer.add("Line 1")
        buffer.add("Line 2")
        buffer.clear()
        assert len(buffer) == 0


class TestDashboardLogHandler:
    """Tests for DashboardLogHandler class."""

    def test_create_handler(self):
        """Test creating a log handler."""
        buffer = LogBuffer()
        handler = DashboardLogHandler(buffer)
        assert handler.buffer is buffer

    def test_handler_captures_logs(self):
        """Test that handler captures log messages."""
        buffer = LogBuffer()
        handler = DashboardLogHandler(buffer)
        handler.setLevel(logging.INFO)

        logger = logging.getLogger("test_handler")
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        logger.info("Test message")

        assert len(buffer) == 1
        assert "Test message" in buffer.get_lines()[0]

        # Clean up
        logger.removeHandler(handler)

    def test_handler_formats_logs(self):
        """Test that handler formats log messages."""
        buffer = LogBuffer()
        handler = DashboardLogHandler(buffer)
        handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))

        logger = logging.getLogger("test_format")
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        logger.warning("Warning message")

        assert "WARNING: Warning message" in buffer.get_lines()[0]

        # Clean up
        logger.removeHandler(handler)

    def test_handler_respects_level(self):
        """Test that handler respects log level."""
        buffer = LogBuffer()
        handler = DashboardLogHandler(buffer)
        handler.setLevel(logging.WARNING)

        logger = logging.getLogger("test_level")
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        logger.info("Info message")  # Should not be captured
        logger.warning("Warning message")  # Should be captured

        assert len(buffer) == 1
        assert "Warning message" in buffer.get_lines()[0]

        # Clean up
        logger.removeHandler(handler)


class TestSplitScreenManager:
    """Tests for SplitScreenManager class."""

    def test_create_manager(self):
        """Test creating a split screen manager."""
        manager = SplitScreenManager()
        assert manager is not None
        assert manager.log_buffer is not None

    def test_get_log_handler(self):
        """Test getting the log handler."""
        manager = SplitScreenManager()
        handler = manager.get_log_handler()
        assert isinstance(handler, DashboardLogHandler)

    def test_get_recent_logs(self):
        """Test getting recent logs."""
        manager = SplitScreenManager()
        manager.log_buffer.add("Log 1")
        manager.log_buffer.add("Log 2")

        recent = manager.get_recent_logs(10)
        assert len(recent) == 2

    def test_render_log_panel(self):
        """Test rendering log panel."""
        manager = SplitScreenManager()
        manager.log_buffer.add("Test log entry")

        panel = manager.render_log_panel(height=5)
        assert panel is not None
