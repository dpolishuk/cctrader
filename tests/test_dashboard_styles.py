"""Tests for dashboard styles."""
import pytest

from src.agent.pipeline.dashboard.styles import (
    COLORS,
    ICONS,
    BORDERS,
    get_status_style,
    get_direction_icon,
    get_border_style
)


def test_colors_defined():
    """Test that all required colors are defined."""
    required = ["success", "error", "warning", "running", "pending",
                "long", "short", "price", "change_up", "change_down"]
    for color in required:
        assert color in COLORS, f"Missing color: {color}"


def test_icons_defined():
    """Test that all required icons are defined."""
    required = ["long", "short", "complete", "running", "pending",
                "warning", "error", "arrow_down"]
    for icon in required:
        assert icon in ICONS, f"Missing icon: {icon}"


def test_borders_defined():
    """Test that all required border styles are defined."""
    required = ["running", "complete", "rejected", "aborted", "error", "pending"]
    for border in required:
        assert border in BORDERS, f"Missing border: {border}"


def test_get_status_style():
    """Test status style lookup."""
    assert "green" in get_status_style("complete").lower() or "green" in get_status_style("complete")
    assert "red" in get_status_style("error").lower() or "red" in get_status_style("error")
    assert get_status_style("unknown") is not None  # Should have default


def test_get_direction_icon():
    """Test direction icon lookup."""
    assert get_direction_icon("LONG") == ICONS["long"]
    assert get_direction_icon("SHORT") == ICONS["short"]
    assert get_direction_icon("UNKNOWN") is not None  # Should have default


def test_get_border_style():
    """Test border style lookup."""
    assert get_border_style("EXECUTED") == BORDERS["complete"]
    assert get_border_style("REJECTED") == BORDERS["rejected"]
    assert get_border_style("ABORTED") == BORDERS["aborted"]
    assert get_border_style("RUNNING") == BORDERS["running"]
