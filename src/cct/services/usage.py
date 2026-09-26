"""Usage per account, as last seen in the statusline data."""

from __future__ import annotations

import time

from cct import paths
from cct.services.state import read_state
from cct.utils.fs import write_json
from cct.utils.timefmt import to_epoch

WINDOWS = ("five_hour", "seven_day")


def parse_window(raw):
    if not isinstance(raw, dict) or raw.get("used_percentage") is None:
        return None
    return {"pct": float(raw["used_percentage"]), "resets_at": to_epoch(raw.get("resets_at"))}


def load_usage(acc_name: str) -> dict:
    return read_state(paths.usage_dir() / f"{acc_name}.json") or {}


def update_usage(acc_name: str, limits, t: float) -> dict:
    """Merge the statusline's rate_limits into the saved usage. Returns the account's usage."""
    usage = load_usage(acc_name)
    if acc_name != "unknown" and isinstance(limits, dict):
        changed = False
        for key in WINDOWS:
            window = parse_window(limits.get(key))
            if window:
                usage[key] = window
                changed = True
        if changed:
            usage["updated_at"] = t
            write_json(paths.usage_dir() / f"{acc_name}.json", usage)
    return usage


def window_view(window, t: float) -> dict:
    # A hand-edited or damaged usage file must not crash the statusline.
    if not isinstance(window, dict) or not isinstance(window.get("pct"), (int, float)):
        return {"state": "unknown"}
    resets_at = window.get("resets_at")
    if not isinstance(resets_at, (int, float)):
        resets_at = None
    if resets_at is not None and resets_at <= t:
        return {"state": "reset", "resets_at": resets_at}  # refilled; new use not seen yet
    return {"state": "ok", "pct": window["pct"], "resets_at": resets_at}


def usage_rows(cfg: dict) -> list:
    t = time.time()
    rows = []
    for acc in cfg["accounts"]:
        usage = load_usage(acc["name"])
        row = {"name": acc["name"], "updated_at": usage.get("updated_at")}
        for key in WINDOWS:
            row[key] = window_view(usage.get(key), t)
        rows.append(row)
    return rows
