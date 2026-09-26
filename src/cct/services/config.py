"""~/.cct/config.json: the account list and the user's previous statusline."""

from __future__ import annotations

import re
from pathlib import Path

from cct import paths
from cct.errors import CctError
from cct.utils.fs import read_json, write_json

NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,32}$")


def load_config() -> dict:
    config_file = paths.config_file()
    try:
        cfg = read_json(config_file)
    except ValueError as err:
        raise CctError(f"{config_file} is not valid JSON ({err}). Fix it or delete it.") from err
    if cfg is None:
        cfg = {"accounts": [{"name": "main", "dir": None}], "prev_statusline": None}
        write_json(config_file, cfg)
    if not isinstance(cfg, dict):
        raise CctError(f"{config_file} is not a JSON object. Fix it or delete it.")
    accounts = cfg.get("accounts")
    if not isinstance(accounts, list) or not accounts:
        raise CctError(f"{config_file} has no accounts. Fix it or delete it.")
    for acc in accounts:
        # Names become file names, so check them on every load.
        if not isinstance(acc, dict) or not NAME_RE.match(str(acc.get("name", ""))):
            raise CctError(f"Bad account entry in {config_file}: {acc!r}")
    return cfg


def save_config(cfg: dict) -> None:
    write_json(paths.config_file(), cfg)


def account_names(cfg: dict) -> list:
    return [a["name"] for a in cfg["accounts"]]


def get_account(cfg: dict, name: str) -> dict:
    for acc in cfg["accounts"]:
        if acc["name"] == name:
            return acc
    raise CctError(f"No account named '{name}'. Known: {', '.join(account_names(cfg))}")


def config_home(acc: dict) -> Path:
    return Path(acc["dir"]).expanduser() if acc.get("dir") else paths.default_claude_home()


def next_account(cfg: dict, current: str) -> dict:
    order = account_names(cfg)
    if len(order) < 2:
        raise CctError("Only one account. Add another with: cct add NAME")
    i = order.index(current) if current in order else -1
    return cfg["accounts"][(i + 1) % len(order)]
