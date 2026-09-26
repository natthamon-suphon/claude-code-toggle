"""cct as a real process, with a fake `claude` that feeds the statusline like Claude Code does."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time

import pytest

from cct import __version__
from helpers import SYMLINKS, posix_only

pytestmark = pytest.mark.e2e


def run_statusline(machine, stdin: str, cwd=None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(machine.entry), "statusline"],
        input=stdin,
        env=machine.env,
        cwd=cwd or machine.work,
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_version(machine):
    result = machine.cct("--version")
    assert result.returncode == 0
    assert result.stdout.strip() == f"cct {__version__}"


def test_python_dash_m(machine):
    result = subprocess.run(
        [sys.executable, "-m", "cct", "--version"],
        env={**machine.env, "PYTHONPATH": str(machine.src)},  # stands in for an install
        cwd=machine.work,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == f"cct {__version__}"


@pytest.mark.parametrize("flags, env", [(["-I"], {}), ([], {"PYTHONSAFEPATH": "1"})])
def test_entry_file_works_when_python_does_not_add_its_folder(machine, flags, env):
    """With -I or PYTHONSAFEPATH (Python 3.11+), the script's folder is not on sys.path."""
    result = subprocess.run(
        [sys.executable, *flags, str(machine.entry), "--version"],
        env={**machine.env, **env},
        cwd=machine.work,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == f"cct {__version__}"


def test_full_day(machine):
    """add → list → run → next → status, as in the README's daily use."""
    for name in ("acc2", "acc3"):
        added = machine.cct("add", name)
        assert added.returncode == 0, added.stderr
        assert "  projects" in added.stdout

    listed = machine.cct("list")
    assert listed.returncode == 0
    lines = listed.stdout.splitlines()
    assert lines[0].startswith("main") and lines[0].endswith("(default)")
    if SYMLINKS:
        assert lines[1].endswith("all shared") and lines[2].endswith("all shared")

    ran = machine.cct("run")
    assert ran.returncode == 0, ran.stderr
    assert "STATUSLINE> [main] 5h 97% 7d 32%" in ran.stdout
    first = machine.starts()[0]
    assert first["CCT_ACCOUNT"] == "main"
    assert first["CLAUDE_CONFIG_DIR"] is None  # the default account never sets it

    moved = machine.cct("next")
    assert moved.returncode == 0, moved.stderr
    assert "STATUSLINE> [acc2] 5h 40% 7d 13%" in moved.stdout
    second = machine.starts()[1]
    assert second["CCT_ACCOUNT"] == "acc2"
    assert os.path.samefile(second["CLAUDE_CONFIG_DIR"], machine.home / ".claude-acc2")
    assert second["args"][0] == "--resume"

    shown = machine.cct("status")
    assert shown.returncode == 0
    out = shown.stdout
    assert "97%" in out and "40%" in out
    assert "acc3       not seen yet" in out
    assert "Last session in this folder ran on 'acc2'" in out


def test_next_resumes_the_exact_session(machine):
    machine.cct("add", "acc2")
    machine.cct("run")
    machine.cct("next")
    first, second = machine.starts()
    session_file = next((machine.home / ".cct" / "sessions").glob("*.json"))
    assert second["args"] == ["--resume", json.loads(session_file.read_text(encoding="utf-8"))["session_id"]]
    assert first["args"] == []


def test_run_passes_args_and_exit_code(machine):
    result = machine.cct("run", "--", "--model", "some-model", FAKE_EXIT="3")
    assert result.returncode == 3
    assert machine.starts()[0]["args"] == ["--model", "some-model"]


def test_user_error_exit_codes(machine):
    missing = machine.cct("link", "nobody")
    assert missing.returncode == 1
    assert missing.stderr.startswith("cct: No account named 'nobody'")
    assert machine.cct("list", "--", "x").returncode == 2
    no_session = machine.cct("next")
    assert no_session.returncode == 1
    assert "No session recorded" in no_session.stderr


def test_claude_not_installed(machine):
    result = machine.cct("run", PATH=str(machine.work))  # a PATH without claude
    assert result.returncode == 1
    assert "Can't find `claude` in PATH" in result.stderr


@posix_only
def test_exit_prompt_moves_session_to_next_account(machine):
    """The prompt only shows on a terminal, so stdin is a pseudo-terminal here."""
    import pty

    machine.cct("add", "acc2")
    machine.cct("add", "acc3")
    controller, terminal = pty.openpty()
    try:
        os.write(controller, b"y\n\n")  # "y" to move to acc3, then Enter (= no) at the next prompt
        result = machine.cct("run", "acc2", stdin=terminal)
    finally:
        os.close(controller)
        os.close(terminal)
    assert result.returncode == 0, result.stderr
    first, second = machine.starts()
    assert (first["CCT_ACCOUNT"], second["CCT_ACCOUNT"]) == ("acc2", "acc3")
    assert second["args"][0] == "--resume"
    assert "Resume this session on 'acc3'" in result.stdout
    assert "Resume this session on 'main'" in result.stdout


@posix_only
def test_installed_command_runs_in_a_shell_from_any_folder(machine, tmp_path):
    installed = machine.cct("install-statusline")
    assert installed.returncode == 0, installed.stderr
    settings = json.loads((machine.home / ".claude" / "settings.json").read_text(encoding="utf-8"))
    command = settings["statusLine"]["command"]
    assert command.endswith("/cct/__main__.py statusline")
    payload = {"session_id": "s", "cwd": str(tmp_path), "rate_limits": {"five_hour": {"used_percentage": 12}}}
    shell = subprocess.run(
        command, shell=True, input=json.dumps(payload), cwd=tmp_path, env=machine.env, capture_output=True, text=True
    )
    assert shell.returncode == 0
    assert shell.stdout.strip() == "[main] 5h 12% 7d -"


@pytest.mark.parametrize(
    "stdin", ["", "{broken", "[]", json.dumps({"rate_limits": {"five_hour": {"used_percentage": "x"}}})]
)
def test_statusline_process_never_fails(machine, stdin):
    result = run_statusline(machine, stdin)
    assert result.returncode == 0
    assert result.stdout.startswith("[")
    assert "Traceback" not in result.stdout + result.stderr


def test_statusline_is_quick(machine):
    """Claude Code runs it on every refresh. The budget is generous; it catches accidental heavy work."""
    started = time.perf_counter()
    assert run_statusline(machine, "{}").returncode == 0
    assert time.perf_counter() - started < 5
