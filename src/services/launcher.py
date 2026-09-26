"""Start the real `claude` as one account."""

from __future__ import annotations

import os
import shutil
import signal
import subprocess

from cct.config import config_home
from cct.errors import CctError
from cct.schema.config import Account


def claude_path() -> str:
    path = shutil.which("claude")
    if not path:
        raise CctError("Can't find `claude` in PATH. Install Claude Code first.")
    return path


def account_env(acc: Account) -> dict:
    env = dict(os.environ)
    if acc.get("dir"):
        env["CLAUDE_CONFIG_DIR"] = str(config_home(acc))
    else:
        # Default profile: leave CLAUDE_CONFIG_DIR unset. Pointing it at ~/.claude
        # makes Claude Code look for its global config and (on macOS) its
        # Keychain item under other names, so it would look logged out.
        env.pop("CLAUDE_CONFIG_DIR", None)
    env["CCT_ACCOUNT"] = acc["name"]
    return env


def launch(acc: Account, args: list) -> int:
    cmd = [claude_path(), *args]
    old = signal.signal(signal.SIGINT, signal.SIG_IGN)  # Ctrl+C belongs to Claude, not cct
    try:
        return subprocess.run(cmd, env=account_env(acc)).returncode
    finally:
        signal.signal(signal.SIGINT, old)
