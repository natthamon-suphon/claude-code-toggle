"""Command-line interface: parse arguments and hand off to a command."""

from __future__ import annotations

import argparse
import sys

from cct import __version__
from cct.errors import CctError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cct", description="Switch Claude Code accounts and see usage.")
    parser.add_argument("--version", action="version", version=f"cct {__version__}")
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
    if extra and args.cmd != "run":
        parser.error("arguments after -- only work with `cct run`")

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
        if args.cmd == "run":
            return run.cmd_run(cfg, args.name, extra, ask=not args.no_ask)
        if args.cmd == "next":
            return run.cmd_next(cfg, args.name)
        if args.cmd == "status":
            return status.cmd_status(cfg)
        if args.cmd == "web":
            return web.cmd_web(args.port, not args.no_open)
        return statusline.cmd_install_statusline(cfg)
    except CctError as err:
        print(f"cct: {err}", file=sys.stderr)
        return 1
