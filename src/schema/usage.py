"""~/.cct/usage/<account>.json: the last usage cct saw for one account."""

from __future__ import annotations

from typing import TypedDict

from cct.schema.common import is_number

WINDOWS = ("five_hour", "seven_day")


class Window(TypedDict):
    pct: float  # percent used, as Claude Code reported it
    resets_at: float | None  # Unix seconds; None when not known


class Usage(TypedDict, total=False):
    five_hour: Window
    seven_day: Window
    updated_at: float  # Unix seconds when cct last saved new numbers


def valid_window(raw) -> Window | None:
    """A saved window, or None when it is missing or damaged. A damaged reset time becomes None."""
    if not isinstance(raw, dict) or not is_number(raw.get("pct")):
        return None
    resets_at = raw.get("resets_at")
    return {"pct": raw["pct"], "resets_at": resets_at if is_number(resets_at) else None}


def valid_usage(raw) -> Usage:
    """A usage file with damaged or unknown parts left out. Missing or broken files give {}."""
    usage: Usage = {}
    if not isinstance(raw, dict):
        return usage
    for key in WINDOWS:
        window = valid_window(raw.get(key))
        if window is not None:
            usage[key] = window
    if is_number(raw.get("updated_at")):
        usage["updated_at"] = raw["updated_at"]
    return usage
