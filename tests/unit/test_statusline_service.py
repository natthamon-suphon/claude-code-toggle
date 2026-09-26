import re
import subprocess
import sys
from pathlib import Path

import pytest

import cct
from cct import paths
from cct.services import statusline as sl
from cct.services.profiles import link_item
from cct.services.sessions import last_session
from cct.utils import system
from cct.utils.fs import read_json
from helpers import needs_symlinks, statusline_payload, windows_only

# ------------------------------------------------------------------ detect_account


def test_detect_account_trusts_known_cct_account(monkeypatch, three_accounts):
    monkeypatch.setenv("CCT_ACCOUNT", "acc3")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", "/whatever")
    assert sl.detect_account(three_accounts) == "acc3"


def test_detect_account_ignores_unknown_cct_account(monkeypatch, three_accounts):
    monkeypatch.setenv("CCT_ACCOUNT", "stranger")
    assert sl.detect_account(three_accounts) == "main"


def test_detect_account_matches_config_dir(monkeypatch, home, three_accounts):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(home / ".claude-acc2"))
    assert sl.detect_account(three_accounts) == "acc2"


def test_detect_account_matches_config_dir_spelled_differently(monkeypatch, home, three_accounts):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(home / "x" / ".." / ".claude-acc3"))
    assert sl.detect_account(three_accounts) == "acc3"


def test_detect_account_plain_claude_is_the_default_account(three_accounts):
    assert sl.detect_account(three_accounts) == "main"


def test_detect_account_unmatched_config_dir_is_unknown(monkeypatch, tmp_path, three_accounts):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "elsewhere"))
    assert sl.detect_account(three_accounts) == "unknown"


def test_detect_account_without_default_account_is_unknown(home):
    cfg = {"accounts": [{"name": "acc2", "dir": str(home / ".claude-acc2")}]}
    assert sl.detect_account(cfg) == "unknown"


# ------------------------------------------------------------------ record


def test_record_saves_usage_and_session(work):
    usage = sl.record("acc2", statusline_payload(work, session_id="s-1", five=40, seven=13))
    assert usage["five_hour"]["pct"] == 40.0
    assert read_json(paths.usage_dir() / "acc2.json") == usage
    session = last_session(work)
    assert session["session_id"] == "s-1"
    assert session["account"] == "acc2"


def test_record_prefers_project_dir_over_cwd(tmp_path):
    project, sub = tmp_path / "project", tmp_path / "project" / "sub"
    sub.mkdir(parents=True)
    sl.record("main", {"session_id": "s", "cwd": str(sub), "workspace": {"project_dir": str(project)}})
    assert last_session(project)["session_id"] == "s"
    assert last_session(sub) is None


def test_record_falls_back_to_cwd_then_current_dir(tmp_path):
    sl.record("main", {"session_id": "a", "cwd": str(tmp_path / "one")})
    sl.record("main", {"session_id": "b", "workspace": {"current_dir": str(tmp_path / "two")}})
    assert last_session(tmp_path / "one")["session_id"] == "a"
    assert last_session(tmp_path / "two")["session_id"] == "b"


def test_record_without_session_id_saves_no_session(work):
    sl.record("main", {"cwd": str(work)})
    assert last_session(work) is None


def test_record_tolerates_odd_workspace(work):
    sl.record("main", {"session_id": "s", "cwd": str(work), "workspace": "not-an-object"})
    assert last_session(work)["session_id"] == "s"


def test_record_session_for_unknown_account_but_no_usage(work):
    sl.record("unknown", statusline_payload(work))
    assert last_session(work)["account"] == "unknown"
    assert not (paths.usage_dir() / "unknown.json").exists()


# ------------------------------------------------------------------ run_previous


def py_cmd(code: str) -> str:
    return f'"{sys.executable}" -c "{code}"'


def test_run_previous_passes_input_and_returns_output():
    assert sl.run_previous(py_cmd("import sys; print(sys.stdin.read().upper())"), "abc") == "ABC"


def test_run_previous_failing_command_returns_its_output():
    assert sl.run_previous(py_cmd("import sys; sys.exit(1)"), "") == ""


def test_run_previous_timeout_is_logged(monkeypatch):
    def slow(*args, **kwargs):
        raise subprocess.TimeoutExpired("x", 5)

    monkeypatch.setattr(sl.subprocess, "run", slow)
    assert sl.run_previous("sleep 10", "") == ""
    assert "previous statusline" in paths.error_log().read_text(encoding="utf-8")


def test_run_previous_os_error_is_logged(monkeypatch):
    def broken(*args, **kwargs):
        raise OSError("no shell")

    monkeypatch.setattr(sl.subprocess, "run", broken)
    assert sl.run_previous("x", "") == ""
    assert "no shell" in paths.error_log().read_text(encoding="utf-8")


# ------------------------------------------------------------------ command string


def test_entry_script_is_the_package_main():
    entry = sl.entry_script()
    assert entry == (Path(cct.__file__).resolve().parent / "__main__.py")
    assert entry.is_file()


def test_entry_script_inside_a_zipapp_is_the_archive(tmp_path, monkeypatch):
    archive = tmp_path / "cct.pyz"
    archive.write_bytes(b"PK")
    monkeypatch.setattr(cct, "__file__", str(archive / "cct" / "__init__.py"))
    assert sl.entry_script() == archive.resolve()


def fixed_entry(monkeypatch, path: str):
    monkeypatch.setattr(sl, "entry_script", lambda: Path(path))


def test_statusline_command_uses_this_python(monkeypatch):
    fixed_entry(monkeypatch, "/opt/cct/cct/__main__.py")
    monkeypatch.setattr(sl.sys, "executable", "/opt/py/bin/python3")
    assert sl.statusline_command() == "/opt/py/bin/python3 /opt/cct/cct/__main__.py statusline"


def test_statusline_command_quotes_script_with_spaces(monkeypatch):
    fixed_entry(monkeypatch, "/Users/A B/cct.pyz")
    monkeypatch.setattr(sl.sys, "executable", "/usr/bin/python3")
    assert sl.statusline_command() == '/usr/bin/python3 "/Users/A B/cct.pyz" statusline'


@pytest.mark.parametrize("executable", ["", None, "/Applications/My Python/python3"])
def test_statusline_command_falls_back_to_python3_off_windows(monkeypatch, executable):
    fixed_entry(monkeypatch, "/x/cct.pyz")
    monkeypatch.setattr(system, "IS_WINDOWS", False)
    monkeypatch.setattr(sl.sys, "executable", executable)
    assert sl.statusline_command() == "python3 /x/cct.pyz statusline"


@pytest.mark.parametrize("has_py, expected", [(True, "py -3"), (False, "python")])
def test_statusline_command_falls_back_to_launcher_on_windows(monkeypatch, has_py, expected):
    fixed_entry(monkeypatch, "/x/cct.pyz")
    monkeypatch.setattr(system, "IS_WINDOWS", True)
    monkeypatch.setattr(sl.sys, "executable", "C:/Program Files/Python/python.exe")
    monkeypatch.setattr(sl.shutil, "which", lambda name: "C:/Windows/py.exe" if has_py else None)
    assert sl.statusline_command() == f"{expected} /x/cct.pyz statusline"


@windows_only
def test_statusline_command_uses_forward_slashes_on_windows():
    assert "\\" not in sl.statusline_command()


def test_statusline_command_is_recognized_as_ours():
    assert sl.is_cct_command(sl.statusline_command())


@pytest.mark.parametrize(
    "cmd",
    [
        "python3 /Users/u/.cct/cct.py statusline",  # the old single-file version
        "py -3 C:/Users/u/.cct/cct.py statusline",
        "python3 cct.py statusline  ",
        '"C:/Program Files/Python/python.exe" "C:/Users/A B/cct.pyz" statusline',
        "/usr/bin/python3 /home/u/.cct/cct.pyz statusline",
        "/usr/bin/python3 /repo/src/cct/__main__.py statusline",
        "C:\\Python\\python.exe C:\\site-packages\\cct\\__main__.py statusline",
        "python -m cct statusline",
    ],
)
def test_is_cct_command_true(cmd):
    assert sl.is_cct_command(cmd)


@pytest.mark.parametrize(
    "cmd",
    [
        None,
        "",
        "echo hi",
        "bash ~/.claude/statusline.sh",
        "python3 /x/my-cct.py statusline",
        "python3 /x/cct.py other",
        "python3 /x/cct.python statusline",
        "python -m cctx statusline",
        "npx ccstatusline@latest",
    ],
)
def test_is_cct_command_false(cmd):
    assert not sl.is_cct_command(cmd)


def test_is_cct_command_source_checkout_entry():
    """A source checkout runs src/__main__.py; it is recognized by cct's files next to it."""
    entry = (Path(cct.__file__).resolve().parent / "__main__.py").as_posix()
    assert sl.is_cct_command(f"/usr/bin/python3 {entry} statusline")
    assert sl.is_cct_command(f'"C:/Program Files/Python/python.exe" "{entry}" statusline')


def test_is_cct_command_other_main_py_is_not_ours(tmp_path):
    other = tmp_path / "src" / "__main__.py"
    other.parent.mkdir()
    other.write_text("print('mine')", encoding="utf-8")
    assert not sl.is_cct_command(f"python3 {other.as_posix()} statusline")
    assert not sl.is_cct_command(f"python3 {(tmp_path / 'missing' / '__main__.py').as_posix()} statusline")


# ------------------------------------------------------------------ settings files


@needs_symlinks
def test_settings_files_follow_links_without_repeats(home, three_accounts):
    for name in ("acc2", "acc3"):
        link_item(home / ".claude" / "settings.json", home / f".claude-{name}" / "settings.json")
    files = sl.settings_files(three_accounts)
    assert len(files) == 1
    assert files[0] == Path(home / ".claude" / "settings.json").resolve()


def test_settings_files_one_per_unlinked_profile(home, three_accounts):
    files = sl.settings_files(three_accounts)
    assert [f.parent.name for f in files] == [".claude", ".claude-acc2", ".claude-acc3"]


def test_backup_file_copies_with_timestamp(claude_home):
    original = claude_home / "settings.json"
    backup = sl.backup_file(original)
    assert re.fullmatch(r"settings\.json\.cct-backup-\d{8}-\d{6}", backup.name)
    assert backup.read_bytes() == original.read_bytes()
