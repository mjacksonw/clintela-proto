"""Utility functions for patient authentication."""

import re
from datetime import date


def parse_flexible_date(date_string):
    """Parse a date string in various formats.

    Supported formats:
    - MM/DD/YYYY
    - MM-DD-YYYY
    - M/D/YY (single digit)
    - MM/DD/YY

    Args:
        date_string: String containing date

    Returns:
        date: Parsed date object, or None if parsing fails
    """
    if not date_string or not isinstance(date_string, str):
        return None

    date_string = date_string.strip()
    if not date_string:
        return None

    # Common date patterns
    patterns = [
        # MM/DD/YYYY or MM-DD-YYYY
        (
            r"^(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})$",
            lambda m: (int(m.group(1)), int(m.group(2)), int(m.group(3))),
        ),
        # MM/DD/YY or MM-DD-YY (2-digit year, pivot at 25)
        (
            r"^(\d{1,2})[/\-](\d{1,2})[/\-](\d{2})$",
            lambda m: (
                int(m.group(1)),
                int(m.group(2)),
                1900 + int(m.group(3)) if int(m.group(3)) > 25 else 2000 + int(m.group(3)),
            ),
        ),
    ]

    for pattern, extractor in patterns:
        match = re.match(pattern, date_string)
        if match:
            try:
                month, day, year = extractor(match)
                return date(year, month, day)
            except ValueError:
                # Invalid date (e.g., 13/45/2020)
                continue

    # Try dateutil as fallback if available
    try:
        from dateutil import parser

        parsed = parser.parse(date_string)
        return parsed.date()
    except (ImportError, ValueError):
        pass

    return None
