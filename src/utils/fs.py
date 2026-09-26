"""JSON files and links."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from cct.utils import system


def read_json(path: Path):
    """Parsed JSON, or None when the file does not exist."""
    try:
        with path.open(encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None


def write_json(path: Path, data) -> None:
    """Atomic write, so readers never see half a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    for attempt in range(5):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            # Windows refuses to replace a file that another process has open.
            if attempt == 4:
                tmp.unlink(missing_ok=True)
                raise
            time.sleep(0.05)


def same_file(a: Path, b: Path) -> bool:
    return os.path.normcase(os.path.realpath(a)) == os.path.normcase(os.path.realpath(b))


def is_link(p: Path) -> bool:
    """True for symlinks and Windows junctions."""
    if p.is_symlink():
        return True
    isjunction = getattr(os.path, "isjunction", None)  # Python 3.12+
    if isjunction is not None:
        return isjunction(p)
    if system.IS_WINDOWS and p.exists():
        try:
            os.readlink(p)  # reads junctions too (Python 3.8+)
            return True
        except OSError:
            return False  # a plain file or folder
    return False
