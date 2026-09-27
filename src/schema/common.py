from __future__ import annotations

import math

# 3000-01-01 UTC. Later times break datetime.fromtimestamp on some systems, and no real reset time is that far away.
MAX_TIMESTAMP = 32_503_680_000.0


def is_number(value) -> bool:
    """A finite int or float, but not bool (JSON true/false must not count as 1/0, and NaN or Infinity is damage)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:  # an int too big for a float
        return False


def is_timestamp(value) -> bool:
    """Unix seconds between 1970 and the year 3000."""
    return is_number(value) and 0 <= value <= MAX_TIMESTAMP
