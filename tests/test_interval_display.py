"""Tests for interval display utilities."""
import pytest
from io import StringIO
from rich.console import Console
from src.agent.tracking.interval_display import display_interval_summary, _format_duration


def test_format_duration():
    """Test duration formatting."""
    assert _format_duration(0) == "0:00"
    assert _format_duration(59) == "0:59"
    assert _format_duration(60) == "1:00"
    assert _format_duration(125) == "2:05"
    assert _format_duration(3661) == "61:01"


def test_display_interval_summary_with_completed():
    """Test displaying completed intervals."""
    intervals = [
        {
            'interval_number': 1,
            'duration_seconds': 300,
            'tokens_input': 890,
            'tokens_output': 344,
            'tokens_total': 1234,
            'cost': 0.012,
            'requests': 3
        },
        {
            'interval_number': 2,
            'duration_seconds': 300,
            'tokens_input': 1502,
            'tokens_output': 654,
            'tokens_total': 2156,
            'cost': 0.021,
            'requests': 5
        }
    ]

    # Should not raise exception
    display_interval_summary(intervals)


def test_display_interval_summary_empty():
    """Test displaying with no intervals."""
    # Should not raise exception or display anything
    display_interval_summary([])
