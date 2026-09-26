"""Profile folders: one CLAUDE_CONFIG_DIR per extra account, with shared items linked to ~/.claude."""

from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path

from cct import paths
from cct.config import account_names, config_home, save_config
from cct.errors import CctError
from cct.schema.config import Account, Config, is_valid_name
from cct.utils import system
from cct.utils.fs import is_link, same_file

SHARED_ITEMS = ("projects", "settings.json", "CLAUDE.md", "skills", "commands", "agents")


def link_item(src: Path, dst: Path) -> str:
    """Make dst point at src. Returns what happened, in words."""
    if is_link(dst):
        return "already linked" if same_file(dst, src) else "SKIPPED: links somewhere else"
    if dst.exists():
        return "SKIPPED: already exists here (move it away to share it)"
    if not src.exists():
        if src.name != "projects":
            return "skipped: not in ~/.claude"
        src.mkdir(parents=True)  # sessions must be shared, or `cct next` can't resume
    try:
        os.symlink(src, dst, target_is_directory=src.is_dir())
        return "linked"
    except OSError:
        if not system.IS_WINDOWS:
            raise
    # Windows without Developer Mode can't make symlinks. Folders can use a junction.
    if src.is_dir():
        r = subprocess.run(["cmd", "/c", "mklink", "/J", str(dst), str(src)], capture_output=True, text=True)
        if r.returncode != 0:
            raise CctError(f"mklink /J failed for {dst}: {(r.stderr or r.stdout).strip()}")
        return "linked (junction)"
    shutil.copy2(src, dst)
    return "COPIED, not linked (turn on Windows Developer Mode, then re-add)"


def link_shared(home: Path) -> Iterator[tuple]:
    """Link every shared item into a profile folder. Yields (item, what happened)."""
    default = paths.default_claude_home()
    for item in SHARED_ITEMS:
        yield item, link_item(default / item, home / item)


def create_profile_dir(cfg: Config, name: str, folder: str | None) -> Path:
    """Check the name and folder, then create the folder. Does not link or save."""
    if not is_valid_name(name):
        raise CctError("Use letters, digits, '-' or '_' (max 32) for the name.")
    if name in account_names(cfg):
        raise CctError(f"Account '{name}' already exists.")
    target = (Path(folder).expanduser() if folder else Path.home() / f".claude-{name}").absolute()
    if same_file(target, paths.default_claude_home()):
        raise CctError("That is the default folder. It already belongs to the first account.")
    for acc in cfg["accounts"]:
        if acc.get("dir") and same_file(target, config_home(acc)):
            raise CctError(f"That folder already belongs to account '{acc['name']}'.")
    target.mkdir(parents=True, exist_ok=True)
    return target


def register_profile(cfg: Config, name: str, target: Path) -> None:
    cfg["accounts"].append({"name": name, "dir": str(target)})
    save_config(cfg)


def unshared_items(acc: Account) -> list:
    """Shared items that exist in ~/.claude but are not linked into this profile."""
    home, default = config_home(acc), paths.default_claude_home()
    return [
        item
        for item in SHARED_ITEMS
        if (default / item).exists() and not (is_link(home / item) and same_file(home / item, default / item))
    ]
