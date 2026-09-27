"""cct statusline (called by Claude Code) and cct install-statusline."""

from __future__ import annotations

import sys
import time

from cct.config import load_config, save_config
from cct.errors import CctError
from cct.schema.config import Config
from cct.schema.statusline import parse_input
from cct.services.state import log_error
from cct.services.statusline import (
    backup_file,
    detect_account,
    is_cct_command,
    record,
    run_previous,
    settings_files,
    statusline_command,
)
from cct.services.usage import window_view
from cct.utils.fs import read_json, write_json


def statusline_text(acc_name: str, usage: dict) -> str:
    t = time.time()
    parts = [f"[{acc_name}]"]
    for key, label in (("five_hour", "5h"), ("seven_day", "7d")):
        view = window_view(usage.get(key), t)
        parts.append(f"{label} {view['pct']:.0f}%" if view["state"] == "ok" else f"{label} -")
    return " ".join(parts)


def read_stdin() -> bytes:
    # Read bytes: on Windows, Python decodes pipes with the local code page (cp1252, cp874, ...),
    # which garbles or rejects the UTF-8 that Claude Code sends, for example a Thai folder name.
    if sys.stdin is None:
        return b""
    buffer = getattr(sys.stdin, "buffer", None)
    return buffer.read() if buffer is not None else sys.stdin.read().encode("utf-8")


def write_out(data: bytes) -> None:
    """Write bytes to stdout as they are, so the console code page can't reject or change any character."""
    if sys.stdout is None:
        return
    buffer = getattr(sys.stdout, "buffer", None)
    if buffer is None:
        sys.stdout.write(data.decode("utf-8", errors="replace"))
        return
    sys.stdout.flush()
    buffer.write(data)
    buffer.flush()


def cmd_statusline() -> int:
    """Called by Claude Code with JSON on stdin. Must never crash its screen."""
    raw = b""
    prev_cmd = None
    try:
        raw = read_stdin()
        cfg = load_config()
        prev_cmd = cfg.get("prev_statusline")
        data = parse_input(raw.decode("utf-8", errors="replace"))
        acc_name = detect_account(cfg)
        text = statusline_text(acc_name, record(acc_name, data))
    except (CctError, OSError, ValueError, TypeError) as err:
        log_error("statusline", err)
        text = "[cct error: see ~/.cct/error.log]"
    write_out(text.encode("utf-8", errors="replace") + b"\n")
    if prev_cmd:
        out = run_previous(prev_cmd, raw)
        if out:
            write_out(out + b"\n")
    return 0


def cmd_install_statusline(cfg: Config) -> int:
    ours = statusline_command()
    for path in settings_files(cfg):
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
        if cur_cmd and not is_cct_command(cur_cmd):
            if cfg.get("prev_statusline") not in (None, cur_cmd):
                print(f"warning: {path} has a different statusline than before; keeping the first one.")
            else:
                cfg["prev_statusline"] = cur_cmd
                # Save now: if a later settings file fails, the old command must not be lost.
                save_config(cfg)
                print(f"keeping your old statusline, shown under cct's line: {cur_cmd}")
        if path.exists():
            print(f"backup: {backup_file(path)}")
        settings["statusLine"] = {"type": "command", "command": ours}
        write_json(path, settings)
        print(f"installed: {path}")
    save_config(cfg)
    print(f"\nstatusline command: {ours}")
    print("Restart Claude Code, send one message, then check `cct status`.")
    return 0
