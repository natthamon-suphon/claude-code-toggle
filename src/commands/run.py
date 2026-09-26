"""cct run, cct next."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from cct.config import account_names, get_account, next_account
from cct.errors import CctError
from cct.schema.config import Account, Config
from cct.services import launcher
from cct.services.sessions import last_session
from cct.services.usage import usage_rows
from cct.utils.timefmt import fmt_ago


def short_usage(row: dict) -> str:
    parts = []
    for key, label in (("five_hour", "5h"), ("seven_day", "7d")):
        view = row[key]
        parts.append(
            f"{label} {view['pct']:.0f}%"
            if view["state"] == "ok"
            else f"{label} {'refilled' if view['state'] == 'reset' else '?'}"
        )
    return ", ".join(parts)


def launch(acc: Account, args: list) -> int:
    if os.environ.get("ANTHROPIC_API_KEY"):
        print(
            "cct: ANTHROPIC_API_KEY is set, so Claude Code may bill that API key instead of this subscription.",
            file=sys.stderr,
        )
    return launcher.launch(acc, args)


def ask_switch(cfg: Config, acc: Account):
    """After Claude exits: offer to resume the same session on another account."""
    if len(cfg["accounts"]) < 2:
        return None
    nxt = next_account(cfg, acc["name"])
    rows = {r["name"]: r for r in usage_rows(cfg)}
    print(f"\n'{acc['name']}': {short_usage(rows[acc['name']])}")
    try:
        answer = input(
            f"Resume this session on '{nxt['name']}' ({short_usage(rows[nxt['name']])})? [y / N / account name] "
        ).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return None
    if answer.lower() in ("y", "yes"):
        return nxt
    if answer in account_names(cfg) and answer != acc["name"]:
        return get_account(cfg, answer)
    return None


def cmd_run(cfg: Config, name: str | None, args: list, ask: bool = True) -> int:
    acc = get_account(cfg, name) if name else cfg["accounts"][0]
    while True:
        print(f"cct: starting Claude Code as '{acc['name']}'")
        started = time.time()
        rc = launch(acc, args)
        if not ask or not sys.stdin.isatty():
            return rc
        sess = last_session(Path.cwd())
        if not sess or sess.get("updated_at", 0) < started or not sess.get("session_id"):
            return rc  # nothing ran in this folder, so nothing to carry over
        target = ask_switch(cfg, acc)
        if target is None:
            return rc
        acc, args = target, ["--resume", sess["session_id"]]


def cmd_next(cfg: Config, name: str | None) -> int:
    sess = last_session(Path.cwd())
    if not sess or not sess.get("session_id"):
        raise CctError(
            "No session recorded for this folder yet. Start Claude here with "
            "`cct run`, and run `cct install-statusline` once per computer."
        )
    current = sess.get("account", "")
    target = get_account(cfg, name) if name else next_account(cfg, current)
    if target["name"] == current:
        print(f"cct: note: that session already ran on '{current}'.")
    print(
        f"cct: resuming session {sess['session_id'][:8]} "
        f"(last active {fmt_ago(sess.get('updated_at'))}) on '{target['name']}'."
    )
    print("cct: close the old Claude window first (/exit), so two accounts don't write to the same session.")
    return cmd_run(cfg, target["name"], ["--resume", sess["session_id"]])
