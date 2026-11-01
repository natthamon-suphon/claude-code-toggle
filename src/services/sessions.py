"""The last Claude Code session seen in each project folder."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from cct import paths
from cct.schema.session import Session, valid_session
from cct.services.state import read_state
from cct.utils.fs import write_json


def project_key(folder: str) -> str:
    norm = os.path.normcase(os.path.realpath(folder))
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:16]


def last_session(folder: Path) -> Session | None:
    return valid_session(read_state(paths.session_dir() / f"{project_key(str(folder))}.json"))


def save_session(folder: str, session_id: str, account: str, t: float) -> None:
    session: Session = {"folder": folder, "session_id": session_id, "account": account, "updated_at": t}
    write_json(paths.session_dir() / f"{project_key(folder)}.json", session)


def saved_sessions() -> list:
    """Every folder's last session that cct has saved, damaged files left out."""
    session_dir = paths.session_dir()
    if not session_dir.exists():
        return []
    items = [valid_session(read_state(p)) for p in session_dir.glob("*.json")]
    return [s for s in items if s is not None]


def find_session(session_id: str) -> Session | None:
    """The newest saved record of this session ID, in any folder. None if cct hasn't seen it."""
    found = [s for s in saved_sessions() if s["session_id"] == session_id]
    return max(found, key=lambda s: s["updated_at"], default=None)


def recent_sessions(limit: int = 8) -> list:
    items = saved_sessions()
    items.sort(key=lambda s: s["updated_at"], reverse=True)
    return [
        {"folder": s["folder"], "account": s["account"], "updated_at": s["updated_at"], "session": s["session_id"][:8]}
        for s in items[:limit]
    ]
