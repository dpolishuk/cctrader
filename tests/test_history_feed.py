"""Tests for history feed component."""
import pytest
from datetime import datetime
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from src.agent.pipeline.dashboard.history_feed import (
    HistoryFeed,
    PipelineHistoryEntry,
    render_history_feed
)


@pytest.fixture
def feed():
    """Create history feed instance."""
    return HistoryFeed(max_entries=5)


@pytest.fixture
def sample_entries():
    """Sample history entries."""
    return [
        PipelineHistoryEntry(
            symbol="BTCUSDT",
            outcome="EXECUTED",
            timestamp=datetime(2025, 1, 25, 14, 35, 22),
            detail="+0.8%"
        ),
        PipelineHistoryEntry(
            symbol="ETHUSDT",
            outcome="NO_TRADE",
            timestamp=datetime(2025, 1, 25, 14, 32, 10),
            detail="low confidence"
        ),
        PipelineHistoryEntry(
            symbol="SOLUSDT",
            outcome="REJECTED",
            timestamp=datetime(2025, 1, 25, 14, 28, 45),
            detail="daily loss limit"
        ),
        PipelineHistoryEntry(
            symbol="AVAXUSDT",
            outcome="ABORTED",
            timestamp=datetime(2025, 1, 25, 14, 15, 30),
            detail="price moved 3%"
        ),
    ]


def test_history_entry_creation():
    """Test creating a history entry."""
    entry = PipelineHistoryEntry(
        symbol="BTCUSDT",
        outcome="EXECUTED",
        timestamp=datetime.now(),
        detail="+1.5%"
    )
    assert entry.symbol == "BTCUSDT"
    assert entry.outcome == "EXECUTED"
    assert entry.detail == "+1.5%"


def test_history_feed_add_entry(feed):
    """Test adding entries to feed."""
    entry = PipelineHistoryEntry(
        symbol="BTCUSDT",
        outcome="EXECUTED",
        timestamp=datetime.now()
    )
    feed.add(entry)
    assert len(feed.entries) == 1
    assert feed.entries[0].symbol == "BTCUSDT"


def test_history_feed_max_entries(feed):
    """Test feed respects max_entries limit."""
    for i in range(10):
        feed.add(PipelineHistoryEntry(
            symbol=f"SYM{i}",
            outcome="NO_TRADE",
            timestamp=datetime.now()
        ))
    assert len(feed.entries) == 5  # max_entries
    assert feed.entries[0].symbol == "SYM9"  # Most recent first


def test_history_feed_render_empty(feed):
    """Test rendering empty feed."""
    panel = feed.render()
    assert isinstance(panel, Panel)


def test_history_feed_render_with_entries(feed, sample_entries):
    """Test rendering feed with entries."""
    # Add in reverse order so most recent (BTCUSDT) ends up at position 0
    for entry in reversed(sample_entries):
        feed.add(entry)

    panel = feed.render()
    assert isinstance(panel, Panel)

    console = Console(force_terminal=True, width=100)
    with console.capture() as capture:
        console.print(panel)
    output = capture.get()

    assert "BTCUSDT" in output
    assert "EXECUTED" in output or "+" in output


def test_history_feed_render_inline(feed, sample_entries):
    """Test rendering inline history (single line)."""
    # Add in reverse order so most recent (BTCUSDT) ends up at position 0
    for entry in reversed(sample_entries):
        feed.add(entry)

    text = feed.render_inline(max_items=3)
    assert isinstance(text, Text)

    rendered = str(text)
    assert "BTCUSDT" in rendered


def test_outcome_styling():
    """Test different outcomes get different styling."""
    feed = HistoryFeed()

    outcomes = ["EXECUTED", "NO_TRADE", "REJECTED", "ABORTED", "ERROR"]
    for outcome in outcomes:
        feed.add(PipelineHistoryEntry(
            symbol="TEST",
            outcome=outcome,
            timestamp=datetime.now()
        ))

    # Should render without error
    panel = feed.render()
    assert isinstance(panel, Panel)


def test_standalone_render_function(sample_entries):
    """Test standalone render function."""
    panel = render_history_feed(sample_entries)
    assert isinstance(panel, Panel)
