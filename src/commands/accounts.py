"""cct add, cct link, cct list."""

from __future__ import annotations

from cct.config import config_home, get_account
from cct.errors import CctError
from cct.schema.config import Config
from cct.services.profiles import create_profile_dir, link_shared, register_profile, unshared_items


def cmd_add(cfg: Config, name: str, folder: str | None) -> int:
    target = create_profile_dir(cfg, name, folder)
    print(f"Profile folder: {target}")
    for item, result in link_shared(target):
        print(f"  {item:<14} {result}")
    register_profile(cfg, name, target)
    print(f"\nNext: run `cct run {name}` and type /login with that account.")
    return 0


def cmd_link(cfg: Config, name: str) -> int:
    acc = get_account(cfg, name)
    if not acc.get("dir"):
        raise CctError("The default account uses ~/.claude itself; nothing to link.")
    for item, result in link_shared(config_home(acc)):
        print(f"  {item:<14} {result}")
    return 0


def cmd_list(cfg: Config) -> int:
    for acc in cfg["accounts"]:
        home = config_home(acc)
        if not acc.get("dir"):
            print(f"{acc['name']:<10} {home}  (default)")
            continue
        broken = unshared_items(acc)
        health = (
            "all shared"
            if not broken
            else f"NOT shared: {', '.join(broken)} (move those out of the folder, then: cct link {acc['name']})"
        )
        print(f"{acc['name']:<10} {home}  {health}")
    return 0
