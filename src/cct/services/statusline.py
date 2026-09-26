"""The statusline hook: which account is running, what to record, and the command for settings.json."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import cct
from cct.services.config import account_names, config_home
from cct.services.sessions import save_session
from cct.services.state import log_error
from cct.services.usage import update_usage
from cct.utils import system
from cct.utils.fs import same_file

# A statusline command that runs cct: the old single file (cct.py), the zipapp
# (cct.pyz), the package entry (cct/__main__.py), or `python -m cct`.
_CCT_COMMAND = re.compile(r"""(?:^|[\s/\\"'])cct\.pyz?\b|[/\\]cct[/\\]__main__\.py\b|-m\s+cct\b""")


def detect_account(cfg: dict) -> str:
    env_name = os.environ.get("CCT_ACCOUNT")
    if env_name in account_names(cfg):
        return env_name
    cfg_dir = os.environ.get("CLAUDE_CONFIG_DIR")
    for acc in cfg["accounts"]:
        if cfg_dir and acc.get("dir") and same_file(Path(cfg_dir), config_home(acc)):
            return acc["name"]
        if not cfg_dir and not acc.get("dir"):
            return acc["name"]  # plain `claude` without cct = default profile
    return "unknown"


def record(acc_name: str, data: dict) -> dict:
    """Save usage and 'last session in this folder'. Returns the account's usage."""
    t = time.time()
    usage = update_usage(acc_name, data.get("rate_limits"), t)
    ws = data.get("workspace") if isinstance(data.get("workspace"), dict) else {}
    folder = ws.get("project_dir") or data.get("cwd") or ws.get("current_dir")
    sid = data.get("session_id")
    if sid and folder:
        save_session(folder, sid, acc_name, t)
    return usage


def run_previous(cmd: str, raw: str) -> str:
    """Run the statusline the user had before cct, with the same input."""
    try:
        r = subprocess.run(cmd, shell=True, input=raw, capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError) as err:
        log_error("previous statusline", err)
        return ""
    return r.stdout.rstrip()


def entry_script() -> Path:
    """The file that runs cct: the .pyz when running as a zipapp, else cct/__main__.py."""
    package_dir = Path(os.path.abspath(cct.__file__)).parent
    if package_dir.parent.is_file():  # .../cct.pyz/cct/__init__.py
        return package_dir.parent.resolve()
    return (package_dir / "__main__.py").resolve()


def statusline_command() -> str:
    """Command string for settings.json. Forward slashes work in bash, cmd and PowerShell."""
    script = entry_script().as_posix()
    py = sys.executable
    if not py or " " in py:
        py = ("py -3" if shutil.which("py") else "python") if system.IS_WINDOWS else "python3"
    else:
        py = Path(py).as_posix()
    script_part = f'"{script}"' if " " in script else script
    return f"{py} {script_part} statusline"


def is_cct_command(cmd) -> bool:
    """True for a statusline command that some version of cct installed."""
    return bool(cmd) and cmd.rstrip().endswith("statusline") and bool(_CCT_COMMAND.search(cmd))


def settings_files(cfg: dict) -> list:
    """Each account's settings.json, followed through links, without repeats."""
    files, seen = [], set()
    for acc in cfg["accounts"]:
        # Write through links to the real file, or the link would be replaced by a copy.
        path = Path(os.path.realpath(config_home(acc) / "settings.json"))
        key = os.path.normcase(str(path))
        if key not in seen:
            seen.add(key)
            files.append(path)
    return files


def backup_file(path: Path) -> Path:
    backup = path.with_name(f"{path.name}.cct-backup-{datetime.now():%Y%m%d-%H%M%S}")
    shutil.copy2(path, backup)
    return backup
