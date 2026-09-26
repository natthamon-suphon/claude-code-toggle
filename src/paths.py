"""Where cct and Claude Code keep their files.

Paths are worked out on each call, not at import time, so a changed HOME or
CCT_HOME takes effect (the tests rely on this).
"""

from __future__ import annotations

import os
from pathlib import Path


def cct_home() -> Path:
    """cct's own folder: $CCT_HOME, or ~/.cct."""
    return Path(os.environ.get("CCT_HOME") or (Path.home() / ".cct")).expanduser()


def config_file() -> Path:
    return cct_home() / "config.json"


def usage_dir() -> Path:
    return cct_home() / "usage"


def session_dir() -> Path:
    return cct_home() / "sessions"


def error_log() -> Path:
    return cct_home() / "error.log"


def default_claude_home() -> Path:
    """The folder plain `claude` uses when CLAUDE_CONFIG_DIR is not set."""
    return Path.home() / ".claude"
