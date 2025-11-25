# src/agent/pipeline/dashboard/styles.py
"""Dashboard styling constants and helpers."""
from typing import Dict

# Trading Pro Color Scheme
COLORS: Dict[str, str] = {
    # Status colors
    "success": "bold bright_green",
    "error": "bold red",
    "warning": "bold yellow",
    "running": "bold cyan",
    "pending": "dim white",

    # Trading colors
    "long": "bold bright_green",
    "short": "bold red",
    "bullish": "green",
    "bearish": "red",

    # Data colors
    "price": "white",
    "change_up": "green",
    "change_down": "red",
    "unchanged": "dim white",

    # UI colors
    "header": "bold cyan",
    "label": "dim cyan",
    "value": "white",
    "muted": "dim white",
}

# Icons
ICONS: Dict[str, str] = {
    "long": "▲",
    "short": "▼",
    "complete": "✓",
    "running": "⏳",
    "pending": "○",
    "warning": "⚠",
    "error": "✗",
    "arrow_down": "▼",
    "arrow_right": "→",
    "bullet": "•",
}

# Border styles for different states
BORDERS: Dict[str, str] = {
    "running": "cyan",
    "complete": "green",
    "rejected": "yellow",
    "aborted": "yellow",
    "error": "red",
    "pending": "dim white",
    "no_trade": "dim white",
}

# Status to style mapping
STATUS_STYLES: Dict[str, str] = {
    "complete": COLORS["success"],
    "running": COLORS["running"],
    "pending": COLORS["pending"],
    "error": COLORS["error"],
    "skipped": COLORS["muted"],
}

# Pipeline outcome to border mapping
OUTCOME_BORDERS: Dict[str, str] = {
    "EXECUTED": "complete",
    "REJECTED": "rejected",
    "ABORTED": "aborted",
    "NO_TRADE": "no_trade",
    "ERROR": "error",
    "RUNNING": "running",
}


def get_status_style(status: str) -> str:
    """Get Rich style string for a status."""
    return STATUS_STYLES.get(status.lower(), COLORS["muted"])


def get_direction_icon(direction: str) -> str:
    """Get icon for trade direction."""
    direction_upper = direction.upper()
    if direction_upper == "LONG":
        return ICONS["long"]
    elif direction_upper == "SHORT":
        return ICONS["short"]
    return ICONS["bullet"]


def get_border_style(outcome: str) -> str:
    """Get border style for pipeline outcome."""
    border_key = OUTCOME_BORDERS.get(outcome.upper(), "pending")
    return BORDERS.get(border_key, BORDERS["pending"])
