#!/usr/bin/env python3
"""cct: switch Claude Code accounts, resume on another account, see usage.

Each extra account gets its own CLAUDE_CONFIG_DIR. Sessions, settings,
CLAUDE.md, skills, commands and agents are shared by linking them to ~/.claude.
Usage numbers come from the statusline data that Claude Code itself passes to
statusline scripts. This tool never reads, copies or sends OAuth tokens.

  cct add NAME [--dir PATH]     create a profile (or adopt an existing folder)
  cct list                      accounts, folders and link health
  cct link NAME                 re-create missing links for an account
  cct run [NAME] [-- ARGS]      start Claude Code as NAME (asks to switch on exit)
  cct next [NAME]               resume this folder's last session on another account
  cct status                    usage table in the terminal
  cct web [--port N]            usage page on http://127.0.0.1:N (this computer only)
  cct install-statusline        add the usage hook to settings.json (once per computer)

Needs Python 3.9+. Standard library only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import secrets
import shutil
import signal
import subprocess
import sys
import time
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HOME = Path.home()
CCT_HOME = Path(os.environ.get("CCT_HOME") or (HOME / ".cct")).expanduser()
CONFIG_FILE = CCT_HOME / "config.json"
USAGE_DIR = CCT_HOME / "usage"
SESSION_DIR = CCT_HOME / "sessions"
ERROR_LOG = CCT_HOME / "error.log"
DEFAULT_HOME = HOME / ".claude"
SHARED_ITEMS = ("projects", "settings.json", "CLAUDE.md", "skills", "commands", "agents")
NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
WINDOWS = ("five_hour", "seven_day")


class CctError(Exception):
    """A problem the user can fix. Printed without a traceback."""


# ---------------------------------------------------------------- files

def log_error(where: str, err: BaseException) -> None:
    """Append to error.log. Used where printing would break Claude's screen."""
    try:
        CCT_HOME.mkdir(parents=True, exist_ok=True)
        with ERROR_LOG.open("a", encoding="utf-8") as f:
            f.write(f"{datetime.now().isoformat(timespec='seconds')} [{where}] {err!r}\n")
    except OSError as log_err:
        # stderr is not drawn in Claude's status line, so this is safe to show.
        print(f"cct: could not write error log: {log_err!r}", file=sys.stderr)


def read_json(path: Path):
    """Parsed JSON, or None when the file does not exist."""
    try:
        with path.open(encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None


def read_state(path: Path):
    """Like read_json, but a broken or locked state file counts as 'no data'."""
    try:
        return read_json(path)
    except (OSError, ValueError) as err:
        log_error(f"read {path.name}", err)
        return None


def write_json(path: Path, data) -> None:
    """Atomic write, so readers never see half a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    for attempt in range(5):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            # Windows refuses to replace a file that another process has open.
            if attempt == 4:
                tmp.unlink(missing_ok=True)
                raise
            time.sleep(0.05)


def same_file(a: Path, b: Path) -> bool:
    return os.path.normcase(os.path.realpath(a)) == os.path.normcase(os.path.realpath(b))


def is_link(p: Path) -> bool:
    """True for symlinks and Windows junctions."""
    if p.is_symlink():
        return True
    isjunction = getattr(os.path, "isjunction", None)  # Python 3.12+
    if isjunction is not None:
        return isjunction(p)
    if os.name == "nt" and p.exists():
        try:
            os.readlink(p)  # reads junctions too (Python 3.8+)
            return True
        except OSError:
            return False  # a plain file or folder
    return False


# ---------------------------------------------------------------- config

def load_config() -> dict:
    try:
        cfg = read_json(CONFIG_FILE)
    except ValueError as err:
        raise CctError(f"{CONFIG_FILE} is not valid JSON ({err}). Fix it or delete it.") from err
    if cfg is None:
        cfg = {"accounts": [{"name": "main", "dir": None}], "prev_statusline": None}
        write_json(CONFIG_FILE, cfg)
    accounts = cfg.get("accounts")
    if not isinstance(accounts, list) or not accounts:
        raise CctError(f"{CONFIG_FILE} has no accounts. Fix it or delete it.")
    for acc in accounts:
        if not isinstance(acc, dict) or not NAME_RE.match(str(acc.get("name", ""))):
            raise CctError(f"Bad account entry in {CONFIG_FILE}: {acc!r}")
    return cfg


def account_names(cfg: dict) -> list:
    return [a["name"] for a in cfg["accounts"]]


def get_account(cfg: dict, name: str) -> dict:
    for acc in cfg["accounts"]:
        if acc["name"] == name:
            return acc
    raise CctError(f"No account named '{name}'. Known: {', '.join(account_names(cfg))}")


def config_home(acc: dict) -> Path:
    return Path(acc["dir"]).expanduser() if acc.get("dir") else DEFAULT_HOME


def next_account(cfg: dict, current: str) -> dict:
    order = account_names(cfg)
    if len(order) < 2:
        raise CctError("Only one account. Add another with: cct add NAME")
    i = order.index(current) if current in order else -1
    return cfg["accounts"][(i + 1) % len(order)]


# ---------------------------------------------------------------- add / list

def link_item(src: Path, dst: Path) -> str:
    """Make dst point at src. Returns what happened, in words."""
    if is_link(dst):
        return "already linked" if same_file(dst, src) else "SKIPPED: links somewhere else"
    if dst.exists():
        return "SKIPPED: already exists here (move it away to share it)"
    if not src.exists():
        if src.name != "projects":
            return "skipped: not in ~/.claude"
        src.mkdir(parents=True)  # sessions must be shared, or `cct next` can't resume
    try:
        os.symlink(src, dst, target_is_directory=src.is_dir())
        return "linked"
    except OSError:
        if os.name != "nt":
            raise
    # Windows without Developer Mode can't make symlinks. Folders can use a junction.
    if src.is_dir():
        r = subprocess.run(["cmd", "/c", "mklink", "/J", str(dst), str(src)],
                           capture_output=True, text=True)
        if r.returncode != 0:
            raise CctError(f"mklink /J failed for {dst}: {(r.stderr or r.stdout).strip()}")
        return "linked (junction)"
    shutil.copy2(src, dst)
    return "COPIED, not linked (turn on Windows Developer Mode, then re-add)"


def cmd_add(cfg: dict, name: str, folder: str | None) -> int:
    if not NAME_RE.match(name):
        raise CctError("Use letters, digits, '-' or '_' (max 32) for the name.")
    if name in account_names(cfg):
        raise CctError(f"Account '{name}' already exists.")
    target = (Path(folder).expanduser() if folder else HOME / f".claude-{name}").absolute()
    if same_file(target, DEFAULT_HOME):
        raise CctError("That is the default folder. It already belongs to the first account.")
    for acc in cfg["accounts"]:
        if acc.get("dir") and same_file(target, config_home(acc)):
            raise CctError(f"That folder already belongs to account '{acc['name']}'.")
    target.mkdir(parents=True, exist_ok=True)
    print(f"Profile folder: {target}")
    for item in SHARED_ITEMS:
        print(f"  {item:<14} {link_item(DEFAULT_HOME / item, target / item)}")
    cfg["accounts"].append({"name": name, "dir": str(target)})
    write_json(CONFIG_FILE, cfg)
    print(f"\nNext: run `cct run {name}` and type /login with that account.")
    return 0


def cmd_link(cfg: dict, name: str) -> int:
    acc = get_account(cfg, name)
    if not acc.get("dir"):
        raise CctError("The default account uses ~/.claude itself; nothing to link.")
    home = config_home(acc)
    for item in SHARED_ITEMS:
        print(f"  {item:<14} {link_item(DEFAULT_HOME / item, home / item)}")
    return 0


def cmd_list(cfg: dict) -> int:
    for acc in cfg["accounts"]:
        home = config_home(acc)
        if not acc.get("dir"):
            print(f"{acc['name']:<10} {home}  (default)")
            continue
        broken = [item for item in SHARED_ITEMS
                  if (DEFAULT_HOME / item).exists()
                  and not (is_link(home / item) and same_file(home / item, DEFAULT_HOME / item))]
        health = ("all shared" if not broken
                  else f"NOT shared: {', '.join(broken)} (move those out of the folder, then: cct link {acc['name']})")
        print(f"{acc['name']:<10} {home}  {health}")
    return 0


# ---------------------------------------------------------------- run / next

def claude_path() -> str:
    path = shutil.which("claude")
    if not path:
        raise CctError("Can't find `claude` in PATH. Install Claude Code first.")
    return path


def account_env(acc: dict) -> dict:
    env = dict(os.environ)
    if acc.get("dir"):
        env["CLAUDE_CONFIG_DIR"] = str(config_home(acc))
    else:
        # Default profile: leave CLAUDE_CONFIG_DIR unset. Pointing it at ~/.claude
        # makes Claude Code look for its global config and (on macOS) its
        # Keychain item under other names, so it would look logged out.
        env.pop("CLAUDE_CONFIG_DIR", None)
    env["CCT_ACCOUNT"] = acc["name"]
    return env


def launch(acc: dict, args: list) -> int:
    if os.environ.get("ANTHROPIC_API_KEY"):
        print("cct: ANTHROPIC_API_KEY is set, so Claude Code may bill that API key "
              "instead of this subscription.", file=sys.stderr)
    cmd = [claude_path(), *args]
    old = signal.signal(signal.SIGINT, signal.SIG_IGN)  # Ctrl+C belongs to Claude, not cct
    try:
        return subprocess.run(cmd, env=account_env(acc)).returncode
    finally:
        signal.signal(signal.SIGINT, old)


def project_key(folder: str) -> str:
    norm = os.path.normcase(os.path.realpath(folder))
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:16]


def last_session(folder: Path):
    return read_state(SESSION_DIR / f"{project_key(str(folder))}.json")


def ask_switch(cfg: dict, acc: dict):
    """After Claude exits: offer to resume the same session on another account."""
    if len(cfg["accounts"]) < 2:
        return None
    nxt = next_account(cfg, acc["name"])
    rows = {r["name"]: r for r in usage_rows(cfg)}
    print(f"\n'{acc['name']}': {short_usage(rows[acc['name']])}")
    try:
        answer = input(f"Resume this session on '{nxt['name']}' ({short_usage(rows[nxt['name']])})? "
                       "[y / N / account name] ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return None
    if answer.lower() in ("y", "yes"):
        return nxt
    if answer in account_names(cfg) and answer != acc["name"]:
        return get_account(cfg, answer)
    return None


def cmd_run(cfg: dict, name: str | None, args: list, ask: bool = True) -> int:
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


def cmd_next(cfg: dict, name: str | None) -> int:
    sess = last_session(Path.cwd())
    if not sess or not sess.get("session_id"):
        raise CctError("No session recorded for this folder yet. Start Claude here with "
                       "`cct run`, and run `cct install-statusline` once per computer.")
    current = sess.get("account", "")
    target = get_account(cfg, name) if name else next_account(cfg, current)
    if target["name"] == current:
        print(f"cct: note: that session already ran on '{current}'.")
    print(f"cct: resuming session {sess['session_id'][:8]} "
          f"(last active {fmt_ago(sess.get('updated_at'))}) on '{target['name']}'.")
    print("cct: close the old Claude window first (/exit), so two accounts "
          "don't write to the same session.")
    return cmd_run(cfg, target["name"], ["--resume", sess["session_id"]])


# ---------------------------------------------------------------- statusline

def to_epoch(value):
    """resets_at arrives as Unix seconds or ISO text, depending on version."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return value / 1000 if value > 1e11 else float(value)  # accept milliseconds too
    if isinstance(value, str):
        text = value.strip()
        if re.fullmatch(r"\d+(\.\d+)?", text):
            return to_epoch(float(text))
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            return datetime.fromisoformat(text).timestamp()
        except ValueError:
            return None
    return None


def parse_window(raw):
    if not isinstance(raw, dict) or raw.get("used_percentage") is None:
        return None
    return {"pct": float(raw["used_percentage"]), "resets_at": to_epoch(raw.get("resets_at"))}


def detect_account(cfg: dict) -> str:
    env_name = os.environ.get("CCT_ACCOUNT")
    if env_name in account_names(cfg):
        return env_name
    cfg_dir = os.environ.get("CLAUDE_CONFIG_DIR")
    for acc in cfg["accounts"]:
        if cfg_dir and acc.get("dir") and same_file(Path(cfg_dir), config_home(acc)):
            return acc["name"]
        if not cfg_dir and not acc.get("dir"):
            return acc["name"]  # plain `claude` without cct = default profile
    return "unknown"


def record(acc_name: str, data: dict) -> dict:
    """Save usage and 'last session in this folder'. Returns the account's usage."""
    t = time.time()
    usage_path = USAGE_DIR / f"{acc_name}.json"
    usage = read_state(usage_path) or {}
    limits = data.get("rate_limits")
    if acc_name != "unknown" and isinstance(limits, dict):
        changed = False
        for key in WINDOWS:
            window = parse_window(limits.get(key))
            if window:
                usage[key] = window
                changed = True
        if changed:
            usage["updated_at"] = t
            write_json(usage_path, usage)
    ws = data.get("workspace") if isinstance(data.get("workspace"), dict) else {}
    folder = ws.get("project_dir") or data.get("cwd") or ws.get("current_dir")
    sid = data.get("session_id")
    if sid and folder:
        write_json(SESSION_DIR / f"{project_key(folder)}.json",
                   {"folder": folder, "session_id": sid, "account": acc_name, "updated_at": t})
    return usage


def statusline_text(acc_name: str, usage: dict) -> str:
    t = time.time()
    parts = [f"[{acc_name}]"]
    for key, label in (("five_hour", "5h"), ("seven_day", "7d")):
        view = window_view(usage.get(key), t)
        parts.append(f"{label} {view['pct']:.0f}%" if view["state"] == "ok" else f"{label} -")
    return " ".join(parts)


def run_previous(cmd: str, raw: str) -> str:
    """Run the statusline the user had before cct, with the same input."""
    try:
        r = subprocess.run(cmd, shell=True, input=raw, capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError) as err:
        log_error("previous statusline", err)
        return ""
    return r.stdout.rstrip()


def cmd_statusline() -> int:
    """Called by Claude Code with JSON on stdin. Must never crash its screen."""
    raw = sys.stdin.read()
    prev_cmd = None
    try:
        cfg = load_config()
        prev_cmd = cfg.get("prev_statusline")
        data = json.loads(raw) if raw.strip() else {}
        if not isinstance(data, dict):
            raise ValueError("statusline input is not a JSON object")
        acc_name = detect_account(cfg)
        text = statusline_text(acc_name, record(acc_name, data))
    except (CctError, OSError, ValueError, TypeError) as err:
        log_error("statusline", err)
        text = "[cct error: see ~/.cct/error.log]"
    print(text)
    if prev_cmd:
        out = run_previous(prev_cmd, raw)
        if out:
            print(out)
    return 0


def statusline_command() -> str:
    """Command string for settings.json. Forward slashes work in bash, cmd and PowerShell."""
    script = Path(__file__).resolve().as_posix()
    py = sys.executable
    if not py or " " in py:
        py = ("py -3" if shutil.which("py") else "python") if os.name == "nt" else "python3"
    else:
        py = Path(py).as_posix()
    script_part = f'"{script}"' if " " in script else script
    return f"{py} {script_part} statusline"


def cmd_install_statusline(cfg: dict) -> int:
    ours = statusline_command()
    done = set()
    for acc in cfg["accounts"]:
        # Write through links to the real file, or the link would be replaced by a copy.
        path = Path(os.path.realpath(config_home(acc) / "settings.json"))
        if os.path.normcase(str(path)) in done:
            continue
        done.add(os.path.normcase(str(path)))
        try:
            settings = read_json(path)
        except ValueError as err:
            raise CctError(f"{path} is not valid JSON ({err}). Not touching it.") from err
        settings = settings if isinstance(settings, dict) else {}
        current = settings.get("statusLine")
        cur_cmd = current.get("command") if isinstance(current, dict) else None
        if cur_cmd == ours:
            print(f"already installed: {path}")
            continue
        is_old_cct = bool(cur_cmd) and "cct.py" in cur_cmd and cur_cmd.rstrip().endswith("statusline")
        if cur_cmd and not is_old_cct:
            if cfg.get("prev_statusline") not in (None, cur_cmd):
                print(f"warning: {path} has a different statusline than before; keeping the first one.")
            else:
                cfg["prev_statusline"] = cur_cmd
                print(f"keeping your old statusline, shown under cct's line: {cur_cmd}")
        if path.exists():
            backup = path.with_name(f"settings.json.cct-backup-{datetime.now():%Y%m%d-%H%M%S}")
            shutil.copy2(path, backup)
            print(f"backup: {backup}")
        settings["statusLine"] = {"type": "command", "command": ours}
        write_json(path, settings)
        print(f"installed: {path}")
    write_json(CONFIG_FILE, cfg)
    print(f"\nstatusline command: {ours}")
    print("Restart Claude Code, send one message, then check `cct status`.")
    return 0


# ---------------------------------------------------------------- dashboard data

def window_view(window, t: float) -> dict:
    if not window:
        return {"state": "unknown"}
    resets_at = window.get("resets_at")
    if resets_at is not None and resets_at <= t:
        return {"state": "reset", "resets_at": resets_at}  # refilled; new use not seen yet
    return {"state": "ok", "pct": window["pct"], "resets_at": resets_at}


def usage_rows(cfg: dict) -> list:
    t = time.time()
    rows = []
    for acc in cfg["accounts"]:
        usage = read_state(USAGE_DIR / f"{acc['name']}.json") or {}
        row = {"name": acc["name"], "updated_at": usage.get("updated_at")}
        for key in WINDOWS:
            row[key] = window_view(usage.get(key), t)
        rows.append(row)
    return rows


def recent_sessions(limit: int = 8) -> list:
    if not SESSION_DIR.exists():
        return []
    items = [read_state(p) for p in SESSION_DIR.glob("*.json")]
    items = [s for s in items if isinstance(s, dict) and s.get("session_id")]
    items.sort(key=lambda s: s.get("updated_at", 0), reverse=True)
    return [{"folder": s.get("folder"), "account": s.get("account"),
             "updated_at": s.get("updated_at"), "session": s["session_id"][:8]}
            for s in items[:limit]]


# ---------------------------------------------------------------- terminal view

def fmt_left(ts) -> str:
    sec = int(ts - time.time())
    if sec <= 0:
        return "now"
    d, h, m = sec // 86400, sec % 86400 // 3600, sec % 3600 // 60
    return f"{d}d {h}h" if d else (f"{h}h {m}m" if h else f"{max(m, 1)}m")


def fmt_ago(ts) -> str:
    if not ts:
        return "never"
    sec = int(time.time() - ts)
    if sec < 60:
        return "just now"
    if sec < 3600:
        return f"{sec // 60}m ago"
    if sec < 86400:
        return f"{sec // 3600}h ago"
    return f"{sec // 86400}d ago"


def short_usage(row: dict) -> str:
    parts = []
    for key, label in (("five_hour", "5h"), ("seven_day", "7d")):
        view = row[key]
        parts.append(f"{label} {view['pct']:.0f}%" if view["state"] == "ok"
                     else f"{label} {'refilled' if view['state'] == 'reset' else '?'}")
    return ", ".join(parts)


def cmd_status(cfg: dict) -> int:
    utf = (sys.stdout.encoding or "").lower().startswith("utf")
    full, empty = ("█", "░") if utf else ("#", ".")
    color = (sys.stdout.isatty() and not os.environ.get("NO_COLOR")
             and (os.name != "nt" or os.environ.get("WT_SESSION")))  # Windows Terminal speaks ANSI

    def cell(view: dict, weekly: bool) -> str:
        if view["state"] == "unknown":
            return f"{'not seen yet':<30}"
        if view["state"] == "reset":
            return f"{'refilled, new use not seen':<30}"
        pct = view["pct"]
        filled = round(min(max(pct, 0), 100) / 100 * 12)
        bar = full * filled + empty * (12 - filled)
        if color:
            code = "31" if pct >= 90 else ("33" if pct >= 70 else "32")
            bar = f"\033[{code}m{bar}\033[0m"
        ra = view.get("resets_at")
        when = "" if ra is None else (datetime.fromtimestamp(ra).strftime("%a %H:%M") if weekly else fmt_left(ra))
        return f"{bar} {pct:>4.0f}%  {when:<10}"

    print(f"{'Account':<10} {'5 hours':<30} {'Weekly':<30} Last seen")
    for row in usage_rows(cfg):
        print(f"{row['name']:<10} {cell(row['five_hour'], False)} "
              f"{cell(row['seven_day'], True)} {fmt_ago(row['updated_at'])}")
    print("\nCounts Claude Code on this computer only. claude.ai and your other computers aren't included.")
    here = last_session(Path.cwd())
    if here:
        print(f"Last session in this folder ran on '{here.get('account')}'. "
              "Move it to another account: cct next")
    return 0


# ---------------------------------------------------------------- web view

PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Claude accounts</title>
<style>
:root{--paper:#EEF2F5;--ink:#1C2A36;--muted:#5C6E7E;--track:#D3DCE4;--line:#C3CED8;
--ok:#2F7D6D;--warn:#B7791F;--full:#B23A48}
@media (prefers-color-scheme:dark){:root{--paper:#17222C;--ink:#E4EBF1;--muted:#93A3B2;
--track:#2A3844;--line:#304050;--ok:#4DB6A0;--warn:#E0A43C;--full:#E8707E}}
*{box-sizing:border-box}
html,body{margin:0;background:var(--paper);color:var(--ink)}
body{font:16px/1.45 "DIN Alternate","Bahnschrift","D-DIN",system-ui,sans-serif;padding:40px 20px 64px}
main{max-width:820px;margin:0 auto}
header{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:baseline;gap:8px 16px;
border-bottom:3px solid var(--ink);padding-bottom:12px}
h1{margin:0;font-size:30px;line-height:1.1;font-weight:700}
.updated{color:var(--muted);font-size:14px;font-variant-numeric:tabular-nums}
.account{display:grid;grid-template-columns:150px 1fr;gap:6px 28px;padding:24px 0;border-bottom:1px solid var(--line)}
.name{font-size:26px;font-weight:700;line-height:1.1;overflow-wrap:anywhere}
.seen{color:var(--muted);font-size:14px;margin-top:4px}
.gauge{display:grid;grid-template-columns:70px 1fr 64px;grid-template-areas:"label track pct" ". when when";
align-items:center;column-gap:14px}
.gauge+.gauge{margin-top:14px}
.label{grid-area:label;color:var(--muted);font-size:14px}
.track{grid-area:track;position:relative;height:20px;background:var(--track);border-radius:2px;overflow:hidden}
.fill{position:absolute;top:0;bottom:0;left:0;background:var(--c);
background-image:repeating-linear-gradient(135deg,transparent 0 5px,rgba(255,255,255,.22) 5px 8px)}
.track::after{content:"";position:absolute;inset:0;
background:repeating-linear-gradient(to right,transparent 0 calc(25% - 2px),var(--paper) calc(25% - 2px) 25%)}
.pct{grid-area:pct;text-align:right;font-size:22px;font-weight:700;font-variant-numeric:tabular-nums}
.when{grid-area:when;color:var(--muted);font-size:14px;margin-top:3px;font-variant-numeric:tabular-nums}
.ok{--c:var(--ok)}.warn{--c:var(--warn)}.full{--c:var(--full)}
h2{font-size:18px;margin:40px 0 8px}
table{width:100%;border-collapse:collapse;font-size:15px;font-variant-numeric:tabular-nums}
th{text-align:left;font-weight:400;color:var(--muted);padding:6px 12px 6px 0;border-bottom:1px solid var(--line)}
td{padding:8px 12px 8px 0;border-bottom:1px solid var(--line);vertical-align:top}
td.folder{overflow-wrap:anywhere}
.scroll{overflow-x:auto}
p.note{color:var(--muted);font-size:14px;max-width:62ch;margin:14px 0 0}
code{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:.92em;background:var(--track);padding:1px 5px;border-radius:2px}
.alert{margin-top:20px;padding:12px 14px;border-left:4px solid var(--full);background:var(--track)}
@media (max-width:560px){.account{grid-template-columns:1fr}.gauge{grid-template-columns:60px 1fr 56px}}
</style></head>
<body><main>
<header><h1>Claude accounts</h1><span class="updated" id="updated">Loading…</span></header>
<div id="alert" class="alert" hidden></div>
<section id="accounts" aria-label="Usage per account"></section>
<h2>Recent sessions on this computer</h2>
<div class="scroll"><table><thead><tr><th>Folder</th><th>Account</th><th>Last active</th></tr></thead>
<tbody id="sessions"></tbody></table></div>
<p class="note">To move a session to another account, close it, open a terminal in that folder and run <code>cct next</code>.</p>
<p class="note">These numbers come from Claude Code on this computer. Use on claude.ai or your other computers doesn't show here.</p>
</main>
<script nonce="__NONCE__">
const el=(tag,cls,text)=>{const e=document.createElement(tag);if(cls)e.className=cls;if(text!=null)e.textContent=text;return e};
let data=null,skew=0;
const nowSec=()=>Date.now()/1000+skew;
function left(s){s=Math.floor(s);if(s<=0)return"now";const d=Math.floor(s/86400),h=Math.floor(s%86400/3600),m=Math.floor(s%3600/60);
return d?`${d}d ${h}h`:h?`${h}h ${m}m`:`${Math.max(m,1)}m`}
function ago(ts){if(!ts)return"never";const s=nowSec()-ts;if(s<60)return"just now";if(s<3600)return`${Math.floor(s/60)} min ago`;
if(s<86400)return`${Math.floor(s/3600)} h ago`;return`${Math.floor(s/86400)} days ago`}
const level=p=>p>=90?"full":p>=70?"warn":"ok";
function gauge(label,v,weekly){
  const g=el("div","gauge");g.append(el("span","label",label));
  const t=el("div","track");g.append(t);
  const pct=el("span","pct");const when=el("span","when");g.append(pct,when);
  let state=v.state,p=v.pct,ra=v.resets_at;
  if(state==="ok"&&ra!=null&&ra<=nowSec())state="reset";
  if(state==="ok"){
    const f=el("div","fill "+level(p));f.style.width=Math.min(Math.max(p,0),100)+"%";t.append(f);
    t.setAttribute("role","meter");t.setAttribute("aria-valuemin","0");t.setAttribute("aria-valuemax","100");
    t.setAttribute("aria-valuenow",String(Math.round(p)));t.setAttribute("aria-label",label+" used");
    pct.textContent=Math.round(p)+"%";
    if(ra!=null){const inS=ra-nowSec();
      when.textContent=weekly?`Refills ${new Date(ra*1000).toLocaleString([], {weekday:"short",hour:"2-digit",minute:"2-digit"})}, in ${left(inS)}`:`Refills in ${left(inS)}`}
  }else if(state==="reset"){pct.textContent="–";when.textContent="Refilled. No use seen since then."}
  else{pct.textContent="–";when.textContent="Not seen yet. Send one message on this account."}
  return g}
function render(){
  if(!data)return;
  const box=document.getElementById("accounts");box.replaceChildren();
  for(const a of data.accounts){
    const row=el("article","account");const who=el("div");
    who.append(el("div","name",a.name),el("div","seen","Seen "+ago(a.updated_at)));
    const gs=el("div");gs.append(gauge("5 hours",a.five_hour,false),gauge("Weekly",a.seven_day,true));
    row.append(who,gs);box.append(row)}
  const tb=document.getElementById("sessions");tb.replaceChildren();
  if(!data.sessions.length){const tr=el("tr");const td=el("td",null,"No sessions yet. Start Claude with cct run.");td.colSpan=3;tr.append(td);tb.append(tr)}
  for(const s of data.sessions){const tr=el("tr");tr.append(el("td","folder",s.folder),el("td",null,s.account),el("td",null,ago(s.updated_at)));tb.append(tr)}
  document.getElementById("updated").textContent="Updated "+ago(data.now)+" on "+data.host}
async function load(){
  const alert=document.getElementById("alert");
  try{const r=await fetch("/api/status",{cache:"no-store"});const j=await r.json();
    if(!r.ok)throw new Error(j.error||("HTTP "+r.status));
    data=j;skew=j.now-Date.now()/1000;alert.hidden=true;render()}
  catch(e){alert.textContent="Can't read usage: "+e.message+". Is `cct web` still running?";alert.hidden=false}}
load();setInterval(load,10000);setInterval(render,1000);
</script></body></html>
"""


def make_handler(port: int, nonce: str):
    allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
    page = PAGE.replace("__NONCE__", nonce).encode("utf-8")
    csp = (f"default-src 'none'; script-src 'nonce-{nonce}'; style-src 'unsafe-inline'; "
           "connect-src 'self'; base-uri 'none'; form-action 'none'")

    class Handler(BaseHTTPRequestHandler):
        server_version = "cct"

        def do_GET(self):
            # A web page on some other site can point a DNS name at 127.0.0.1;
            # checking Host stops it from reading this data.
            if self.headers.get("Host") not in allowed_hosts:
                self.send_error(403, "Host not allowed")
                return
            path = self.path.split("?", 1)[0]
            if path == "/":
                self._send(200, "text/html; charset=utf-8", page)
            elif path == "/api/status":
                try:
                    cfg = load_config()
                except CctError as err:
                    self._send(500, "application/json", json.dumps({"error": str(err)}).encode())
                    return
                body = {"now": time.time(), "host": platform.node(),
                        "accounts": usage_rows(cfg), "sessions": recent_sessions()}
                self._send(200, "application/json", json.dumps(body).encode("utf-8"))
            else:
                self.send_error(404)

        def _send(self, code: int, ctype: str, body: bytes):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", csp)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            return  # quiet on purpose: the page polls every 10 seconds

    return Handler


def cmd_web(port: int, open_browser: bool) -> int:
    load_config()  # fail early on a broken config
    try:
        # 127.0.0.1 only: nothing on your network can reach this page.
        server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(port, secrets.token_urlsafe(16)))
    except OSError as err:
        raise CctError(f"Can't use port {port} ({err.strerror}). Try: cct web --port {port + 1}") from err
    url = f"http://127.0.0.1:{port}/"
    print(f"cct: dashboard at {url}  (Ctrl+C to stop)")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\ncct: stopped.")
    finally:
        server.server_close()
    return 0


# ---------------------------------------------------------------- main

def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["statusline"]:
        return cmd_statusline()
    extra = []
    if "--" in argv:
        cut = argv.index("--")
        argv, extra = argv[:cut], argv[cut + 1:]

    parser = argparse.ArgumentParser(prog="cct", description="Switch Claude Code accounts and see usage.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("add", help="create a profile or adopt a folder")
    p.add_argument("name")
    p.add_argument("--dir", help="existing folder to adopt (default: ~/.claude-NAME)")
    sub.add_parser("list", help="accounts, folders and link health")
    sub.add_parser("link", help="re-create missing shared links").add_argument("name")
    p = sub.add_parser("run", help="start Claude Code as an account; extra args after --")
    p.add_argument("name", nargs="?")
    p.add_argument("--no-ask", action="store_true", help="don't offer to switch when Claude exits")
    sub.add_parser("next", help="resume this folder's last session on another account").add_argument("name", nargs="?")
    sub.add_parser("status", help="usage table")
    p = sub.add_parser("web", help="usage page on 127.0.0.1")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--no-open", action="store_true", help="don't open the browser")
    sub.add_parser("install-statusline", help="add the usage hook to settings.json")
    args = parser.parse_args(argv)
    if extra and args.cmd != "run":
        parser.error("arguments after -- only work with `cct run`")

    try:
        cfg = load_config()
        if args.cmd == "add":
            return cmd_add(cfg, args.name, args.dir)
        if args.cmd == "list":
            return cmd_list(cfg)
        if args.cmd == "link":
            return cmd_link(cfg, args.name)
        if args.cmd == "run":
            return cmd_run(cfg, args.name, extra, ask=not args.no_ask)
        if args.cmd == "next":
            return cmd_next(cfg, args.name)
        if args.cmd == "status":
            return cmd_status(cfg)
        if args.cmd == "web":
            return cmd_web(args.port, not args.no_open)
        return cmd_install_statusline(cfg)
    except CctError as err:
        print(f"cct: {err}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
