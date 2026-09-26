"""Shared test helpers (importable because pyproject puts tests/ on sys.path)."""

from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path

import pytest

from cct import paths
from cct.utils.fs import write_json


def _symlinks_work() -> bool:
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "target"
        target.mkdir()
        try:
            os.symlink(target, Path(tmp) / "link", target_is_directory=True)
        except (OSError, NotImplementedError):
            return False
    return True


SYMLINKS = _symlinks_work()
needs_symlinks = pytest.mark.skipif(not SYMLINKS, reason="this system can't create symlinks")
posix_only = pytest.mark.skipif(os.name == "nt", reason="POSIX-only behavior")
windows_only = pytest.mark.skipif(os.name != "nt", reason="Windows-only behavior")


def write_usage(name: str, five=None, seven=None, updated_at=None) -> Path:
    """Save a usage file. five/seven are (pct, resets_at) tuples."""
    usage = {"updated_at": time.time() if updated_at is None else updated_at}
    for key, window in (("five_hour", five), ("seven_day", seven)):
        if window is not None:
            usage[key] = {"pct": window[0], "resets_at": window[1]}
    path = paths.usage_dir() / f"{name}.json"
    write_json(path, usage)
    return path


def statusline_payload(folder, session_id="sess-0001", five=40, seven=13, resets_in=4000) -> dict:
    """The part of Claude Code's statusline JSON that cct reads."""
    now = int(time.time())
    return {
        "session_id": session_id,
        "cwd": str(folder),
        "workspace": {"project_dir": str(folder), "current_dir": str(folder)},
        "rate_limits": {
            "five_hour": {"used_percentage": five, "resets_at": now + resets_in},
            "seven_day": {"used_percentage": seven, "resets_at": "2099-01-02T03:04:05Z"},
        },
    }
