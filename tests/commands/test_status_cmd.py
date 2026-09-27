import io
import sys
import time

import pytest

from cct.commands.status import cmd_status
from cct.services.sessions import save_session
from cct.utils import system
from helpers import write_usage


class Terminal(io.StringIO):
    def __init__(self, tty=True, encoding="utf-8"):
        super().__init__()
        self._tty, self._encoding = tty, encoding

    @property
    def encoding(self):
        return self._encoding

    def isatty(self):
        return self._tty


@pytest.fixture
def usage(three_accounts):
    now = time.time()
    write_usage("main", five=(97, now + 3930), seven=(32, now + 5 * 86400), updated_at=now)
    write_usage("acc2", five=(75, now - 5), seven=(40, now + 86400), updated_at=now - 7200)
    return three_accounts


def run_status(cfg, monkeypatch, **terminal):
    term = Terminal(**terminal)
    monkeypatch.setattr(sys, "stdout", term)
    assert cmd_status(cfg) == 0
    return term.getvalue()


def test_status_table(work, usage, monkeypatch):
    out = run_status(usage, monkeypatch, tty=False)
    lines = out.splitlines()
    assert lines[0].split() == ["Account", "5", "hours", "Weekly", "Last", "seen"]
    assert lines[1].startswith("main       ████████████   97%  1h 5m")
    assert lines[1].endswith("just now")
    assert "████░░░░░░░░   32%" in lines[1]
    assert lines[2].startswith("acc2       refilled, new use not seen")
    assert "█████░░░░░░░   40%" in lines[2]  # 40% of 12 cells rounds to 5
    assert lines[2].endswith("2h ago")
    assert lines[3].startswith("acc3       not seen yet")
    assert lines[3].endswith("never")
    assert "Counts Claude Code on this computer only." in out
    assert "Last session in this folder" not in out


def test_status_ascii_bars_when_terminal_is_not_utf8(work, usage, monkeypatch):
    out = run_status(usage, monkeypatch, tty=False, encoding="cp1252")
    assert "############   97%" in out
    assert "█" not in out


def test_status_colors_by_level_on_a_terminal(work, usage, monkeypatch):
    monkeypatch.setattr(system, "IS_WINDOWS", False)
    out = run_status(usage, monkeypatch, tty=True)
    assert "\033[31m████████████\033[0m" in out  # 97%: red
    assert "\033[32m████░░░░░░░░\033[0m" in out  # 32%: green


def test_status_warn_color_from_70_percent(work, three_accounts, monkeypatch):
    monkeypatch.setattr(system, "IS_WINDOWS", False)
    write_usage("main", five=(70, time.time() + 100))
    assert "\033[33m" in run_status(three_accounts, monkeypatch, tty=True)


def test_status_no_color_when_piped_or_no_color(work, usage, monkeypatch):
    assert "\033[" not in run_status(usage, monkeypatch, tty=False)
    monkeypatch.setenv("NO_COLOR", "1")
    assert "\033[" not in run_status(usage, monkeypatch, tty=True)


def test_status_bar_clamps_out_of_range_percent(work, three_accounts, monkeypatch):
    write_usage("main", five=(130, None), seven=(-5, None))
    out = run_status(three_accounts, monkeypatch, tty=False)
    assert "████████████  130%" in out
    assert "░░░░░░░░░░░░   -5%" in out


def test_status_survives_damaged_usage_file(work, three_accounts, monkeypatch):
    from cct import paths

    paths.usage_dir().mkdir(parents=True)
    (paths.usage_dir() / "main.json").write_text(
        '{"updated_at": "yesterday", "five_hour": {"pct": 5}}', encoding="utf-8"
    )
    out = run_status(three_accounts, monkeypatch, tty=False)
    main_line = out.splitlines()[1]
    assert "5%" in main_line and main_line.endswith("never")


def test_status_survives_numbers_json_allows_but_python_cannot_use(work, three_accounts, monkeypatch):
    """NaN, Infinity, huge ints and far-future times in a hand-edited file count as no data."""
    from cct import paths

    paths.usage_dir().mkdir(parents=True)
    (paths.usage_dir() / "main.json").write_text(
        '{"updated_at": Infinity, "five_hour": {"pct": NaN, "resets_at": 1e17},'
        ' "seven_day": {"pct": 5, "resets_at": 1' + "0" * 400 + "}}",
        encoding="utf-8",
    )
    out = run_status(three_accounts, monkeypatch, tty=False)
    main_line = out.splitlines()[1]
    assert main_line.startswith("main       not seen yet")
    assert "5%" in main_line and main_line.endswith("never")


def test_status_mentions_last_session_in_this_folder(work, usage, monkeypatch):
    save_session(str(work), "s", "acc2", time.time())
    out = run_status(usage, monkeypatch, tty=False)
    assert "Last session in this folder ran on 'acc2'. Move it to another account: cct next" in out
