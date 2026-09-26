"""The last Claude Code session seen in each project folder."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from cct import paths
from cct.services.state import read_state
from cct.utils.fs import write_json


def project_key(folder: str) -> str:
    norm = os.path.normcase(os.path.realpath(folder))
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:16]


def last_session(folder: Path) -> dict | None:
    return read_state(paths.session_dir() / f"{project_key(str(folder))}.json")


def save_session(folder: str, session_id: str, account: str, t: float) -> None:
    write_json(
        paths.session_dir() / f"{project_key(folder)}.json",
        {"folder": folder, "session_id": session_id, "account": account, "updated_at": t},
    )


def recent_sessions(limit: int = 8) -> list:
    session_dir = paths.session_dir()
    if not session_dir.exists():
        return []
    items = [read_state(p) for p in session_dir.glob("*.json")]
    items = [s for s in items if isinstance(s, dict) and s.get("session_id")]
    items.sort(key=lambda s: s.get("updated_at", 0), reverse=True)
    return [
        {
            "folder": s.get("folder"),
            "account": s.get("account"),
            "updated_at": s.get("updated_at"),
            "session": s["session_id"][:8],
        }
        for s in items[:limit]
    ]
