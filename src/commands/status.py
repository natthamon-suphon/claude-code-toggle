"""cct status: the usage table in the terminal."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

from cct.schema.config import Config
from cct.services.sessions import last_session
from cct.services.usage import usage_rows
from cct.utils.terminal import supports_color, supports_utf8
from cct.utils.timefmt import fmt_ago, fmt_left

BAR_CELLS = 12


def cmd_status(cfg: Config) -> int:
    full, empty = ("█", "░") if supports_utf8(sys.stdout) else ("#", ".")
    color = supports_color(sys.stdout)

    def cell(view: dict, weekly: bool) -> str:
        if view["state"] == "unknown":
            return f"{'not seen yet':<30}"
        if view["state"] == "reset":
            return f"{'refilled, new use not seen':<30}"
        pct = view["pct"]
        filled = round(min(max(pct, 0), 100) / 100 * BAR_CELLS)
        bar = full * filled + empty * (BAR_CELLS - filled)
        if color:
            code = "31" if pct >= 90 else ("33" if pct >= 70 else "32")
            bar = f"\033[{code}m{bar}\033[0m"
        ra = view.get("resets_at")
        when = "" if ra is None else (datetime.fromtimestamp(ra).strftime("%a %H:%M") if weekly else fmt_left(ra))
        return f"{bar} {pct:>4.0f}%  {when:<10}"

    print(f"{'Account':<10} {'5 hours':<30} {'Weekly':<30} Last seen")
    for row in usage_rows(cfg):
        five_hour, weekly = cell(row["five_hour"], False), cell(row["seven_day"], True)
        print(f"{row['name']:<10} {five_hour} {weekly} {fmt_ago(row['updated_at'])}")
    print("\nCounts Claude Code on this computer only. claude.ai and your other computers aren't included.")
    here = last_session(Path.cwd())
    if here:
        print(f"Last session in this folder ran on '{here.get('account')}'. Move it to another account: cct next")
    return 0
