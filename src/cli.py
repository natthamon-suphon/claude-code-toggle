"""Command-line interface: parse arguments and hand off to a command."""

from __future__ import annotations

import argparse
import os
import sys

from cct import __version__
from cct.errors import CctError


def port(text: str) -> int:
    number = int(text)
    if not 0 <= number <= 65535:
        raise argparse.ArgumentTypeError("use a port from 0 to 65535")
    return number


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cct", description="Switch Claude Code accounts and see usage.")
    parser.add_argument("--version", action="version", version=f"cct {__version__}")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("add", help="create a profile or adopt a folder")
    p.add_argument("name")
    p.add_argument("--dir", help="existing folder to adopt (default: ~/.claude-NAME)")
    sub.add_parser("list", help="accounts, folders and link health")
    sub.add_parser("link", help="re-create missing shared links").add_argument("name")
    p = sub.add_parser("start", help="start Claude Code as an account; extra args after --")
    p.add_argument("name", nargs="?")
    p.add_argument("--no-ask", action="store_true", help="don't offer to switch when Claude exits")
    p = sub.add_parser("resume", help="resume a session on another account (default: this folder's last one)")
    p.add_argument("name", nargs="?")
    p.add_argument("-s", "--session", metavar="ID", help="the session to resume (default: this folder's last one)")
    sub.add_parser("status", help="usage table")
    p = sub.add_parser("web", help="usage page on 127.0.0.1")
    p.add_argument("--port", type=port, default=8765)
    p.add_argument("--no-open", action="store_true", help="don't open the browser")
    sub.add_parser("install-statusline", help="add the usage hook to settings.json")
    return parser


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["statusline"]:
        # Hidden command for Claude Code. Runs on every status refresh, so skip argparse.
        from cct.commands.statusline import cmd_statusline

        return cmd_statusline()
    extra = []
    if "--" in argv:
        cut = argv.index("--")
        argv, extra = argv[:cut], argv[cut + 1 :]

    parser = build_parser()
    args = parser.parse_args(argv)
    if extra and args.cmd != "start":
        parser.error("arguments after -- only work with `cct start`")

    # Imported here so `cct statusline` and `cct --help` stay fast.
    from cct.commands import accounts, run, status, statusline, web
    from cct.config import load_config

    try:
        cfg = load_config()
        if args.cmd == "add":
            return accounts.cmd_add(cfg, args.name, args.dir)
        if args.cmd == "list":
            return accounts.cmd_list(cfg)
        if args.cmd == "link":
            return accounts.cmd_link(cfg, args.name)
        if args.cmd == "start":
            return run.cmd_start(cfg, args.name, extra, ask=not args.no_ask)
        if args.cmd == "resume":
            return run.cmd_resume(cfg, args.name, args.session)
        if args.cmd == "status":
            return status.cmd_status(cfg)
        if args.cmd == "web":
            return web.cmd_web(args.port, not args.no_open)
        return statusline.cmd_install_statusline(cfg)
    except CctError as err:
        print(f"cct: {err}", file=sys.stderr)
        return 1
    except BrokenPipeError:
        # The reader went away, as in `cct status | head -1`. Send the rest of the output nowhere,
        # so Python's final flush doesn't fail again.
        try:
            os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        except (OSError, ValueError) as err:  # stdout is not a real file (in tests)
            print(f"cct: {err}", file=sys.stderr)
        return 1
    except OSError as err:  # a file or folder problem, such as a read-only ~/.cct
        print(f"cct: {err}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print(file=sys.stderr)
        return 130
