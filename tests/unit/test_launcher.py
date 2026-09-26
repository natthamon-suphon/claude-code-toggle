import signal
import subprocess

import pytest

from cct.errors import CctError
from cct.services import launcher
from cct.services.launcher import account_env, claude_path, launch

MAIN = {"name": "main", "dir": None}
ACC2 = {"name": "acc2", "dir": "~/.claude-acc2"}


def test_default_account_removes_claude_config_dir(monkeypatch):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", "/somewhere/else")
    monkeypatch.setenv("KEEP_ME", "1")
    env = account_env(MAIN)
    assert "CLAUDE_CONFIG_DIR" not in env
    assert env["CCT_ACCOUNT"] == "main"
    assert env["KEEP_ME"] == "1"


def test_extra_account_sets_its_own_config_dir(home):
    env = account_env(ACC2)
    assert env["CLAUDE_CONFIG_DIR"] == str(home / ".claude-acc2")
    assert env["CCT_ACCOUNT"] == "acc2"


def test_account_env_does_not_change_our_own_environment(monkeypatch):
    import os

    account_env(ACC2)
    assert "CCT_ACCOUNT" not in os.environ


def test_claude_path_missing_is_a_user_error(monkeypatch):
    monkeypatch.setattr(launcher.shutil, "which", lambda name: None)
    with pytest.raises(CctError, match="Can't find `claude`"):
        claude_path()


def test_claude_path_found(monkeypatch):
    monkeypatch.setattr(launcher.shutil, "which", lambda name: "/usr/local/bin/claude")
    assert claude_path() == "/usr/local/bin/claude"


def test_launch_runs_claude_with_account_env_and_ignores_ctrl_c(monkeypatch):
    seen = {}
    before = signal.getsignal(signal.SIGINT)

    def fake_run(cmd, env):
        seen.update(cmd=cmd, env=env, sigint=signal.getsignal(signal.SIGINT))
        return subprocess.CompletedProcess(cmd, 3)

    monkeypatch.setattr(launcher, "claude_path", lambda: "/bin/claude")
    monkeypatch.setattr(launcher.subprocess, "run", fake_run)
    assert launch(ACC2, ["--resume", "abc"]) == 3
    assert seen["cmd"] == ["/bin/claude", "--resume", "abc"]
    assert seen["env"]["CCT_ACCOUNT"] == "acc2"
    assert seen["sigint"] == signal.SIG_IGN  # Ctrl+C goes to Claude while it runs
    assert signal.getsignal(signal.SIGINT) == before  # and comes back afterwards


def test_launch_restores_ctrl_c_when_claude_fails_to_start(monkeypatch):
    before = signal.getsignal(signal.SIGINT)

    def broken_run(cmd, env):
        raise FileNotFoundError("claude")

    monkeypatch.setattr(launcher, "claude_path", lambda: "/bin/claude")
    monkeypatch.setattr(launcher.subprocess, "run", broken_run)
    with pytest.raises(FileNotFoundError):
        launch(MAIN, [])
    assert signal.getsignal(signal.SIGINT) == before
