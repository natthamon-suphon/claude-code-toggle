"""~/.cct/sessions/<key>.json: the last Claude Code session seen in one project folder.

<key> is sha256(normcase(realpath(folder)))[:16] (see services/sessions.project_key).
"""

from __future__ import annotations

import re
from typing import TypedDict

from cct.schema.common import is_timestamp

# Letters, digits, '-' and '_'. No spaces, and no leading '-' that `claude` could read as an option.
_SESSION_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}")


class Session(TypedDict):
    folder: str  # the project folder, as Claude Code reported it
    session_id: str  # what `claude --resume` takes
    account: str  # the account it last ran on
    updated_at: float  # Unix seconds


def valid_session(raw) -> Session | None:
    """A saved session, or None without a usable session ID. Other damaged fields get safe defaults."""
    # The ID goes to `claude --resume`, so one that could be read as an option counts as damage.
    if not isinstance(raw, dict) or not is_session_id(raw.get("session_id")):
        return None
    folder, account, updated_at = raw.get("folder"), raw.get("account"), raw.get("updated_at")
    return {
        "folder": folder if isinstance(folder, str) else "",
        "session_id": raw["session_id"],
        "account": account if isinstance(account, str) else "",
        "updated_at": updated_at if is_timestamp(updated_at) else 0.0,
    }


def is_session_id(value) -> bool:
    """A session ID that is safe to pass to `claude --resume`: typed by the user, saved, or sent by Claude Code."""
    return isinstance(value, str) and _SESSION_ID.fullmatch(value) is not None
