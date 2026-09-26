"""~/.cct/config.json: the account list, and the statusline the user had before cct."""

from __future__ import annotations

import re
from typing import TypedDict

from cct.errors import CctError

# Names become file names (usage/<name>.json), so they are checked on every load.
NAME_RE = re.compile(r"[A-Za-z0-9_-]{1,32}")


class Account(TypedDict):
    name: str
    dir: str | None  # the profile folder; None = the default folder, ~/.claude


class Config(TypedDict):
    accounts: list[Account]  # the first one is the default for `cct run`
    prev_statusline: str | None  # shown under cct's own statusline


def is_valid_name(name) -> bool:
    return isinstance(name, str) and NAME_RE.fullmatch(name) is not None


def default_config() -> Config:
    return {"accounts": [{"name": "main", "dir": None}], "prev_statusline": None}


def validate_config(data, source) -> Config:
    """Check a parsed config.json and return it. `source` names the file in error messages."""
    if not isinstance(data, dict):
        raise CctError(f"{source} is not a JSON object. Fix it or delete it.")
    accounts = data.get("accounts")
    if not isinstance(accounts, list) or not accounts:
        raise CctError(f"{source} has no accounts. Fix it or delete it.")
    for acc in accounts:
        if (
            not isinstance(acc, dict)
            or not is_valid_name(acc.get("name"))
            or not isinstance(acc.get("dir"), (str, type(None)))
        ):
            raise CctError(f"Bad account entry in {source}: {acc!r}")
    if not isinstance(data.get("prev_statusline"), (str, type(None))):
        raise CctError(f"Bad prev_statusline in {source}: {data['prev_statusline']!r}")
    return data
