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


def recent_sessions(limit: int = 8) -> list:
    session_dir = paths.session_dir()
    if not session_dir.exists():
        return []
    items = [valid_session(read_state(p)) for p in session_dir.glob("*.json")]
    items = [s for s in items if s is not None]
    items.sort(key=lambda s: s["updated_at"], reverse=True)
    return [
        {"folder": s["folder"], "account": s["account"], "updated_at": s["updated_at"], "session": s["session_id"][:8]}
        for s in items[:limit]
    ]
