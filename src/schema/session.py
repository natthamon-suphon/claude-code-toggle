"""~/.cct/sessions/<key>.json: the last Claude Code session seen in one project folder.

<key> is sha256(normcase(realpath(folder)))[:16] (see services/sessions.project_key).
"""

from __future__ import annotations

from typing import TypedDict

from cct.schema.common import is_number


class Session(TypedDict):
    folder: str  # the project folder, as Claude Code reported it
    session_id: str  # what `claude --resume` takes
    account: str  # the account it last ran on
    updated_at: float  # Unix seconds


def valid_session(raw) -> Session | None:
    """A saved session, or None without a usable session ID. Other damaged fields get safe defaults."""
    if not isinstance(raw, dict) or not isinstance(raw.get("session_id"), str) or not raw["session_id"]:
        return None
    folder, account, updated_at = raw.get("folder"), raw.get("account"), raw.get("updated_at")
    return {
        "folder": folder if isinstance(folder, str) else "",
        "session_id": raw["session_id"],
        "account": account if isinstance(account, str) else "",
        "updated_at": updated_at if is_number(updated_at) else 0.0,
    }
