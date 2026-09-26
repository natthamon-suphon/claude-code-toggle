"""cct's state files (usage, sessions) and its error log."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

from cct import paths
from cct.utils.fs import read_json


def log_error(where: str, err: BaseException) -> None:
    """Append to error.log. Used where printing would break Claude's screen."""
    try:
        paths.cct_home().mkdir(parents=True, exist_ok=True)
        with paths.error_log().open("a", encoding="utf-8") as f:
            f.write(f"{datetime.now().isoformat(timespec='seconds')} [{where}] {err!r}\n")
    except OSError as log_err:
        # stderr is not drawn in Claude's status line, so this is safe to show.
        print(f"cct: could not write error log: {log_err!r}", file=sys.stderr)


def read_state(path: Path) -> dict | None:
    """Like read_json, but a broken, locked or non-object state file counts as 'no data'."""
    try:
        data = read_json(path)
    except (OSError, ValueError) as err:
        log_error(f"read {path.name}", err)
        return None
    if data is not None and not isinstance(data, dict):
        log_error(f"read {path.name}", ValueError("not a JSON object"))
        return None
    return data
