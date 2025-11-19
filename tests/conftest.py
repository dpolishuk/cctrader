"""Pytest configuration and fixtures."""
import sqlite3
from datetime import datetime, timezone


def adapt_datetime_iso(val):
    """Adapt datetime.datetime to UTC ISO 8601 date."""
    # Handle both timezone-aware and naive datetimes
    if val.tzinfo is None:
        # Assume naive datetime is UTC
        val = val.replace(tzinfo=timezone.utc)
    return val.astimezone(timezone.utc).isoformat()


def convert_datetime(val):
    """Convert ISO 8601 datetime to datetime.datetime object."""
    # Handle both bytes and string input
    if isinstance(val, bytes):
        val = val.decode()
    return datetime.fromisoformat(val)


# Register custom datetime adapters to fix Python 3.12 deprecation warnings
sqlite3.register_adapter(datetime, adapt_datetime_iso)
sqlite3.register_converter("DATETIME", convert_datetime)
