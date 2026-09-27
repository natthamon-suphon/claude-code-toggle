"""The JSON that Claude Code sends to statusline scripts on stdin. Only the fields cct reads.

Reference: https://code.claude.com/docs/en/statusline. `rate_limits` is only sent to Pro and Max
subscribers, only after the first API response of a session, and has been missing in some
Claude Code versions, so every field is optional.
"""

from __future__ import annotations

import json
from typing import Any, TypedDict

from cct.schema.common import is_number, is_timestamp
from cct.schema.usage import Window
from cct.utils.timefmt import to_epoch


class RateLimitWindow(TypedDict, total=False):
    used_percentage: float  # sometimes sent as text, e.g. "42.5"
    resets_at: Any  # Unix seconds, milliseconds or ISO-8601 text, depending on the version


class RateLimits(TypedDict, total=False):
    five_hour: RateLimitWindow
    seven_day: RateLimitWindow


class Workspace(TypedDict, total=False):
    project_dir: str
    current_dir: str


class StatuslineInput(TypedDict, total=False):
    session_id: str
    cwd: str
    workspace: Workspace
    rate_limits: RateLimits


def parse_input(raw: str) -> StatuslineInput:
    """Parse stdin. Empty input means {}; anything but a JSON object raises ValueError."""
    data = json.loads(raw) if raw.strip() else {}
    if not isinstance(data, dict):
        raise ValueError("statusline input is not a JSON object")
    return data


def project_folder(data: StatuslineInput):
    """The project folder of the session: workspace.project_dir, then cwd, then workspace.current_dir."""
    ws = data.get("workspace") if isinstance(data.get("workspace"), dict) else {}
    return ws.get("project_dir") or data.get("cwd") or ws.get("current_dir")


def session_id(data: StatuslineInput) -> str | None:
    sid = data.get("session_id")
    return sid if isinstance(sid, str) and sid else None


def parse_window(raw) -> Window | None:
    """One rate_limits window as cct saves it. A percent that isn't a finite number raises ValueError or TypeError."""
    if not isinstance(raw, dict) or raw.get("used_percentage") is None:
        return None
    try:
        pct = float(raw["used_percentage"])
    except OverflowError as err:  # an int too big for a float
        raise ValueError("used_percentage is too large") from err
    if not is_number(pct):
        raise ValueError(f"used_percentage is not a finite number: {pct}")
    resets_at = to_epoch(raw.get("resets_at"))
    return {"pct": pct, "resets_at": resets_at if is_timestamp(resets_at) else None}
