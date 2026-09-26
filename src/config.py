"""Load and save ~/.cct/config.json, and look up accounts in it. The shape is in schema/config.py."""

from __future__ import annotations

from pathlib import Path

from cct import paths
from cct.errors import CctError
from cct.schema.config import Account, Config, default_config, validate_config
from cct.utils.fs import read_json, write_json


def load_config() -> Config:
    config_file = paths.config_file()
    try:
        cfg = read_json(config_file)
    except ValueError as err:
        raise CctError(f"{config_file} is not valid JSON ({err}). Fix it or delete it.") from err
    if cfg is None:
        cfg = default_config()
        write_json(config_file, cfg)
    return validate_config(cfg, config_file)


def save_config(cfg: Config) -> None:
    write_json(paths.config_file(), cfg)


def account_names(cfg: Config) -> list:
    return [a["name"] for a in cfg["accounts"]]


def get_account(cfg: Config, name: str) -> Account:
    for acc in cfg["accounts"]:
        if acc["name"] == name:
            return acc
    raise CctError(f"No account named '{name}'. Known: {', '.join(account_names(cfg))}")


def config_home(acc: Account) -> Path:
    return Path(acc["dir"]).expanduser() if acc.get("dir") else paths.default_claude_home()


def next_account(cfg: Config, current: str) -> Account:
    order = account_names(cfg)
    if len(order) < 2:
        raise CctError("Only one account. Add another with: cct add NAME")
    i = order.index(current) if current in order else -1
    return cfg["accounts"][(i + 1) % len(order)]
