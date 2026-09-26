"""Timestamps in, short human text out."""

from __future__ import annotations

import re
import time
from datetime import datetime


def to_epoch(value):
    """resets_at arrives as Unix seconds or ISO text, depending on version."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return value / 1000 if value > 1e11 else float(value)  # accept milliseconds too
    if isinstance(value, str):
        text = value.strip()
        if re.fullmatch(r"\d+(\.\d+)?", text):
            return to_epoch(float(text))
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            return datetime.fromisoformat(text).timestamp()
        except ValueError:
            return None
    return None


def fmt_left(ts) -> str:
    sec = int(ts - time.time())
    if sec <= 0:
        return "now"
    d, h, m = sec // 86400, sec % 86400 // 3600, sec % 3600 // 60
    return f"{d}d {h}h" if d else (f"{h}h {m}m" if h else f"{max(m, 1)}m")


def fmt_ago(ts) -> str:
    if not ts:
        return "never"
    sec = int(time.time() - ts)
    if sec < 60:
        return "just now"
    if sec < 3600:
        return f"{sec // 60}m ago"
    if sec < 86400:
        return f"{sec // 3600}h ago"
    return f"{sec // 86400}d ago"
