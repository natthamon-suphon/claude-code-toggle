"""`cct statusline`: Claude Code calls it with JSON on stdin. It must never crash or print a traceback."""

import io
import json
import sys

import pytest

from cct import paths
from cct.commands.statusline import cmd_statusline, statusline_text
from cct.config import save_config
from cct.services.sessions import last_session
from cct.utils.fs import read_json
from helpers import statusline_payload, write_usage

ERROR_LINE = "[cct error: see ~/.cct/error.log]"


def hook(monkeypatch, capsys, stdin: str):
    monkeypatch.setattr(sys, "stdin", io.StringIO(stdin))
    assert cmd_statusline() == 0
    captured = capsys.readouterr()
    assert "Traceback" not in captured.out + captured.err
    return captured.out.splitlines()


def logged() -> str:
    return paths.error_log().read_text(encoding="utf-8") if paths.error_log().exists() else ""


def test_records_usage_and_session_and_prints_line(work, three_accounts, monkeypatch, capsys):
    monkeypatch.setenv("CCT_ACCOUNT", "acc2")
    lines = hook(monkeypatch, capsys, json.dumps(statusline_payload(work, session_id="s-9", five=40, seven=13)))
    assert lines == ["[acc2] 5h 40% 7d 13%"]
    assert read_json(paths.usage_dir() / "acc2.json")["five_hour"]["pct"] == 40.0
    assert last_session(work)["session_id"] == "s-9"
    assert logged() == ""


def test_default_account_without_cct(work, cfg, monkeypatch, capsys):
    assert hook(monkeypatch, capsys, json.dumps(statusline_payload(work, five=5, seven=1))) == ["[main] 5h 5% 7d 1%"]


@pytest.mark.parametrize("stdin", ["", "   \n"])
def test_empty_input_prints_cached_usage(cfg, monkeypatch, capsys, stdin):
    write_usage("main", five=(12, None), seven=(3, None))
    assert hook(monkeypatch, capsys, stdin) == ["[main] 5h 12% 7d 3%"]


def test_nothing_known_yet(cfg, monkeypatch, capsys):
    assert hook(monkeypatch, capsys, "{}") == ["[main] 5h - 7d -"]


def test_unknown_account_is_shown_but_not_saved(work, three_accounts, monkeypatch, capsys, tmp_path):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "not-a-profile"))
    assert hook(monkeypatch, capsys, json.dumps(statusline_payload(work))) == ["[unknown] 5h - 7d -"]
    assert not (paths.usage_dir() / "unknown.json").exists()


def test_percent_as_text(work, cfg, monkeypatch, capsys):
    payload = statusline_payload(work)
    payload["rate_limits"]["five_hour"]["used_percentage"] = "61.6"
    assert hook(monkeypatch, capsys, json.dumps(payload))[0].startswith("[main] 5h 62%")


def test_expired_window_shows_dash(work, cfg, monkeypatch, capsys):
    payload = statusline_payload(work, resets_in=-10)
    assert hook(monkeypatch, capsys, json.dumps(payload)) == ["[main] 5h - 7d 13%"]


def test_missing_rate_limits_keeps_old_numbers(work, cfg, monkeypatch, capsys):
    write_usage("main", five=(50, None), seven=(20, None))
    payload = statusline_payload(work)
    del payload["rate_limits"]
    assert hook(monkeypatch, capsys, json.dumps(payload)) == ["[main] 5h 50% 7d 20%"]


@pytest.mark.parametrize(
    "stdin",
    [
        "{not json",
        "[1, 2, 3]",
        '"just text"',
        json.dumps({"rate_limits": {"five_hour": {"used_percentage": "lots"}}}),
        json.dumps({"rate_limits": {"five_hour": {"used_percentage": [1]}}}),
        json.dumps({"session_id": "s", "cwd": 5}),
    ],
)
def test_bad_input_logs_and_prints_short_error(cfg, monkeypatch, capsys, stdin):
    assert hook(monkeypatch, capsys, stdin) == [ERROR_LINE]
    assert "[statusline]" in logged()


@pytest.mark.parametrize("pct", ['"nan"', '"inf"', "NaN", "Infinity", "1e400", "1" + "0" * 400])
def test_percent_that_is_not_finite_is_logged_not_saved(work, cfg, monkeypatch, capsys, pct):
    stdin = '{"session_id": "s", "rate_limits": {"five_hour": {"used_percentage": PCT}}}'.replace("PCT", pct)
    assert hook(monkeypatch, capsys, stdin) == [ERROR_LINE]
    assert "[statusline]" in logged()
    assert not (paths.usage_dir() / "main.json").exists()


def test_impossible_reset_time_is_saved_as_unknown(work, cfg, monkeypatch, capsys):
    payload = statusline_payload(work, five=40, seven=13)
    payload["rate_limits"]["five_hour"]["resets_at"] = 1e17
    assert hook(monkeypatch, capsys, json.dumps(payload)) == ["[main] 5h 40% 7d 13%"]
    assert read_json(paths.usage_dir() / "main.json")["five_hour"] == {"pct": 40.0, "resets_at": None}


def run_with_code_page(monkeypatch, stdin: bytes, code_page: str) -> bytes:
    """Run the hook with stdin and stdout set up like a Windows pipe that uses the given code page."""
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(stdin), encoding=code_page))
    out = io.BytesIO()
    monkeypatch.setattr(sys, "stdout", io.TextIOWrapper(out, encoding=code_page))
    assert cmd_statusline() == 0
    sys.stdout.flush()
    return out.getvalue()


@pytest.mark.parametrize("code_page", ["cp1252", "cp874"])
def test_utf8_input_is_read_whatever_the_code_page(tmp_path, cfg, monkeypatch, code_page):
    """Claude Code sends UTF-8. On Windows, Python would decode the pipe with the local code page."""
    folder = tmp_path / "โปรเจกต์"  # "ก" is the byte 0x81 in UTF-8, which cp1252 can't decode
    folder.mkdir()
    payload = json.dumps(statusline_payload(folder, session_id="s-th"), ensure_ascii=False).encode("utf-8")
    assert run_with_code_page(monkeypatch, payload, code_page) == b"[main] 5h 40% 7d 13%\n"
    assert logged() == ""
    assert last_session(folder)["folder"] == str(folder)


def test_previous_statusline_output_is_passed_on_unchanged(cfg, monkeypatch):
    """Its output may hold characters the console code page can't encode, or bytes that aren't UTF-8."""
    code = "import sys; sys.stdout.buffer.write(b'\\xe0\\xb9\\x84\\xe0\\xb8\\x97\\xe0\\xb8\\xa2 \\xff')"
    cfg["prev_statusline"] = f'"{sys.executable}" -c "{code}"'
    save_config(cfg)
    out = run_with_code_page(monkeypatch, b"{}", "cp1252")
    assert out == b"[main] 5h - 7d -\n" + "ไทย".encode() + b" \xff\n"


def test_text_only_stdout_still_gets_the_line(cfg, monkeypatch):
    """Some wrappers replace sys.stdout with a text stream that has no byte buffer."""
    monkeypatch.setattr(sys, "stdin", io.StringIO("{}"))
    out = io.StringIO()
    monkeypatch.setattr(sys, "stdout", out)
    assert cmd_statusline() == 0
    assert out.getvalue() == "[main] 5h - 7d -\n"


def test_missing_stdin_and_stdout_do_not_crash(cfg, monkeypatch):
    """Python sets them to None when the parent process gives none."""
    monkeypatch.setattr(sys, "stdin", None)
    monkeypatch.setattr(sys, "stdout", None)
    assert cmd_statusline() == 0
    assert logged() == ""


@pytest.mark.parametrize(
    "stdin",
    [
        json.dumps({"rate_limits": []}),
        json.dumps({"rate_limits": {"five_hour": "90%"}}),
        json.dumps({"workspace": "x", "session_id": None}),
        json.dumps({"session_id": "s"}),
    ],
)
def test_odd_but_harmless_input_is_ignored(cfg, monkeypatch, capsys, stdin):
    assert hook(monkeypatch, capsys, stdin) == ["[main] 5h - 7d -"]


def test_broken_config_prints_error_line(monkeypatch, capsys):
    paths.config_file().parent.mkdir(parents=True)
    paths.config_file().write_text("{", encoding="utf-8")
    assert hook(monkeypatch, capsys, "{}") == [ERROR_LINE]
    assert "not valid JSON" in logged()


@pytest.mark.parametrize(
    "damage",
    [
        "[1]",
        "{",
        '{"five_hour": "x", "seven_day": {"pct": "10"}}',
        '{"five_hour": {"pct": NaN}, "seven_day": {"pct": Infinity}}',
        '{"five_hour": {"pct": 1e999}, "seven_day": {"pct": 1' + "0" * 400 + "}}",
    ],
)
def test_damaged_usage_file_does_not_crash(cfg, monkeypatch, capsys, damage):
    paths.usage_dir().mkdir(parents=True)
    (paths.usage_dir() / "main.json").write_text(damage, encoding="utf-8")
    assert hook(monkeypatch, capsys, "") == ["[main] 5h - 7d -"]


def test_previous_statusline_is_shown_under_ours(work, cfg, monkeypatch, capsys):
    cfg["prev_statusline"] = f'"{sys.executable}" -c "import sys, json; print(json.load(sys.stdin)[\'session_id\'])"'
    save_config(cfg)
    lines = hook(monkeypatch, capsys, json.dumps(statusline_payload(work, session_id="abc")))
    assert lines == ["[main] 5h 40% 7d 13%", "abc"]


def test_previous_statusline_still_runs_when_our_part_fails(cfg, monkeypatch, capsys):
    cfg["prev_statusline"] = f'"{sys.executable}" -c "print(42)"'
    save_config(cfg)
    assert hook(monkeypatch, capsys, "{broken") == [ERROR_LINE, "42"]


def test_silent_or_failing_previous_statusline_adds_nothing(cfg, monkeypatch, capsys):
    cfg["prev_statusline"] = f'"{sys.executable}" -c "import sys; sys.exit(2)"'
    save_config(cfg)
    assert hook(monkeypatch, capsys, "{}") == ["[main] 5h - 7d -"]


def test_bad_prev_statusline_in_config_does_not_crash(cfg, monkeypatch, capsys):
    cfg["prev_statusline"] = 5
    save_config(cfg)
    assert hook(monkeypatch, capsys, "{}") == [ERROR_LINE]
    assert "Bad prev_statusline" in logged()


def test_non_text_session_id_is_not_saved(work, cfg, monkeypatch, capsys):
    payload = statusline_payload(work)
    payload["session_id"] = 12345
    assert hook(monkeypatch, capsys, json.dumps(payload)) == ["[main] 5h 40% 7d 13%"]
    assert last_session(work) is None


def test_statusline_text_rounds_percent():
    usage = {"five_hour": {"pct": 99.5, "resets_at": None}, "seven_day": {"pct": 0.4, "resets_at": None}}
    assert statusline_text("acc2", usage) == "[acc2] 5h 100% 7d 0%"
