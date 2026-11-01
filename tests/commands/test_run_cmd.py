import sys
import time
from pathlib import Path

import pytest

from cct.commands.run import ask_switch, cmd_resume, cmd_start, short_usage
from cct.errors import CctError
from cct.services import launcher
from cct.services.sessions import save_session
from helpers import write_usage


class FakeClaude:
    """Stands in for launcher.launch. Records calls and, like the statusline would, the session."""

    def __init__(self, records_session=True, rc=0):
        self.calls, self.records_session, self.rc = [], records_session, rc

    def __call__(self, acc, args):
        self.calls.append((acc["name"], list(args)))
        if self.records_session:
            sid = args[1] if args[:1] == ["--resume"] else f"sid-{len(self.calls)}"
            save_session(str(Path.cwd()), sid, acc["name"], time.time())
        return self.rc


class TtyStdin:
    def isatty(self):
        return True


@pytest.fixture
def claude(monkeypatch):
    fake = FakeClaude()
    monkeypatch.setattr(launcher, "launch", fake)
    return fake


@pytest.fixture
def answers(monkeypatch):
    """Type these answers at the exit prompt. The fixture returns the prompts shown."""
    queue, prompts = [], []

    def fake_input(prompt=""):
        prompts.append(prompt)
        print(prompt)
        if not queue:
            raise EOFError
        answer = queue.pop(0)
        if isinstance(answer, BaseException):
            raise answer
        return answer

    monkeypatch.setattr(sys, "stdin", TtyStdin())
    monkeypatch.setattr("builtins.input", fake_input)

    def type_answers(*items):
        queue.extend(items)
        return prompts

    return type_answers


# ------------------------------------------------------------------ cmd_start


def test_start_starts_first_account_by_default(work, three_accounts, claude, capsys):
    assert cmd_start(three_accounts, None, [], ask=False) == 0
    assert claude.calls == [("main", [])]
    assert "cct: starting Claude Code as 'main'" in capsys.readouterr().out


def test_start_named_account_with_extra_args(work, three_accounts, claude):
    cmd_start(three_accounts, "acc2", ["--model", "x"], ask=False)
    assert claude.calls == [("acc2", ["--model", "x"])]


def test_start_unknown_account_is_a_user_error(three_accounts, claude):
    with pytest.raises(CctError):
        cmd_start(three_accounts, "nobody", [])
    assert claude.calls == []


def test_start_passes_exit_code_through(work, three_accounts, monkeypatch):
    monkeypatch.setattr(launcher, "launch", FakeClaude(rc=7))
    assert cmd_start(three_accounts, None, [], ask=False) == 7


def test_start_does_not_ask_without_a_terminal(work, three_accounts, claude, monkeypatch):
    class Pipe:
        def isatty(self):
            return False

    monkeypatch.setattr(sys, "stdin", Pipe())
    cmd_start(three_accounts, None, [])
    assert claude.calls == [("main", [])]


def test_start_does_not_ask_when_no_session_ran_here(work, three_accounts, answers, monkeypatch):
    fake = FakeClaude(records_session=False)
    monkeypatch.setattr(launcher, "launch", fake)
    save_session(str(work), "old", "main", time.time() - 3600)  # from an earlier run
    prompts = answers("y")
    cmd_start(three_accounts, None, [])
    assert prompts == []
    assert fake.calls == [("main", [])]


def test_start_ignores_damaged_session_time(work, three_accounts, answers, monkeypatch):
    from cct import paths
    from cct.services.sessions import project_key
    from cct.utils.fs import write_json

    fake = FakeClaude(records_session=False)
    monkeypatch.setattr(launcher, "launch", fake)
    write_json(paths.session_dir() / f"{project_key(str(work))}.json", {"session_id": "s", "updated_at": "now"})
    prompts = answers("y")
    assert cmd_start(three_accounts, None, []) == 0
    assert prompts == []


def test_start_yes_resumes_same_session_on_next_account(work, three_accounts, claude, answers):
    prompts = answers("y", "")
    cmd_start(three_accounts, None, [])
    assert claude.calls == [("main", []), ("acc2", ["--resume", "sid-1"])]
    assert prompts[0].startswith("Resume this session on 'acc2'")
    assert prompts[1].startswith("Resume this session on 'acc3'")


def test_start_account_name_answer_picks_that_account(work, three_accounts, claude, answers):
    answers("acc3", "")
    cmd_start(three_accounts, None, [])
    assert claude.calls == [("main", []), ("acc3", ["--resume", "sid-1"])]


@pytest.mark.parametrize("answer", ["", "n", "N", "no", "maybe", "main", "YES please"])
def test_start_other_answers_stop(work, three_accounts, claude, answers, answer):
    answers(answer)
    cmd_start(three_accounts, None, [])
    assert claude.calls == [("main", [])]


@pytest.mark.parametrize("answer", ["Y", "yes", "YES", "  y  "])
def test_start_yes_variants(work, three_accounts, claude, answers, answer):
    answers(answer, "")
    cmd_start(three_accounts, None, [])
    assert claude.calls[1][0] == "acc2"


@pytest.mark.parametrize("error", [EOFError(), KeyboardInterrupt()])
def test_start_ctrl_d_or_ctrl_c_at_prompt_stops(work, three_accounts, claude, answers, error):
    answers(error)
    assert cmd_start(three_accounts, None, []) == 0
    assert claude.calls == [("main", [])]


def test_start_with_one_account_never_asks(work, cfg, claude, answers):
    prompts = answers("y")
    cmd_start(cfg, None, [])
    assert prompts == []
    assert claude.calls == [("main", [])]


def test_start_warns_when_api_key_is_set(work, three_accounts, claude, monkeypatch, capsys):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "placeholder-not-a-real-key")
    cmd_start(three_accounts, None, [], ask=False)
    err = capsys.readouterr().err
    assert "ANTHROPIC_API_KEY is set" in err
    assert "placeholder-not-a-real-key" not in err  # never print the key


# ------------------------------------------------------------------ ask_switch / short_usage


def test_ask_switch_shows_usage_of_both_accounts(three_accounts, answers, capsys):
    now = time.time()
    write_usage("main", five=(97, now + 100), seven=(32, now + 1000))
    write_usage("acc2", five=(40, now - 1))
    answers("")
    assert ask_switch(three_accounts, three_accounts["accounts"][0]) is None
    out = capsys.readouterr().out
    assert "'main': 5h 97%, 7d 32%" in out
    assert "Resume this session on 'acc2' (5h refilled, 7d ?)? [y / N / account name]" in out


@pytest.mark.parametrize(
    "five, seven, expected",
    [
        ({"state": "ok", "pct": 40.4}, {"state": "ok", "pct": 12.6}, "5h 40%, 7d 13%"),
        ({"state": "reset"}, {"state": "unknown"}, "5h refilled, 7d ?"),
    ],
)
def test_short_usage(five, seven, expected):
    assert short_usage({"five_hour": five, "seven_day": seven}) == expected


# ------------------------------------------------------------------ cmd_resume


def test_resume_without_session_is_a_user_error(work, three_accounts):
    with pytest.raises(CctError, match="No session recorded for this folder yet"):
        cmd_resume(three_accounts, None)


def test_resume_resumes_on_the_following_account(work, three_accounts, claude, capsys, monkeypatch):
    monkeypatch.setattr(sys, "stdin", type("Pipe", (), {"isatty": lambda self: False})())
    save_session(str(work), "12345678-aaaa", "main", time.time())
    assert cmd_resume(three_accounts, None) == 0
    assert claude.calls == [("acc2", ["--resume", "12345678-aaaa"])]
    out = capsys.readouterr().out
    assert "cct: resuming session 12345678 (last active just now) on 'acc2'." in out
    assert "close the old Claude window first" in out


def test_resume_named_account(work, three_accounts, claude, monkeypatch):
    monkeypatch.setattr(sys, "stdin", type("Pipe", (), {"isatty": lambda self: False})())
    save_session(str(work), "s", "main", time.time())
    cmd_resume(three_accounts, "acc3")
    assert claude.calls == [("acc3", ["--resume", "s"])]


def test_resume_same_account_prints_a_note(work, three_accounts, claude, capsys, monkeypatch):
    monkeypatch.setattr(sys, "stdin", type("Pipe", (), {"isatty": lambda self: False})())
    save_session(str(work), "s", "acc2", time.time())
    cmd_resume(three_accounts, "acc2")
    assert "note: that session already ran on 'acc2'" in capsys.readouterr().out


def test_resume_unknown_account_is_a_user_error(work, three_accounts, claude):
    save_session(str(work), "s", "main", time.time())
    with pytest.raises(CctError, match="No account named"):
        cmd_resume(three_accounts, "nobody")
    assert claude.calls == []


# ------------------------------------------------------------------ cmd_resume --session


@pytest.fixture
def pipe_stdin(monkeypatch):
    monkeypatch.setattr(sys, "stdin", type("Pipe", (), {"isatty": lambda self: False})())


def test_resume_given_session_instead_of_the_folders_last(work, three_accounts, claude, pipe_stdin, capsys):
    save_session(str(work.parent / "other"), "older-id", "acc2", time.time() - 600)
    save_session(str(work), "latest-id", "main", time.time())  # this folder's last session: not used
    assert cmd_resume(three_accounts, None, "older-id") == 0
    assert claude.calls == [("acc3", ["--resume", "older-id"])]  # the account after acc2, where it last ran
    assert "cct: resuming session older-id (last active 10m ago) on 'acc3'." in capsys.readouterr().out


def test_resume_given_session_on_a_named_account(work, three_accounts, claude, pipe_stdin):
    save_session(str(work), "s-1", "main", time.time())
    cmd_resume(three_accounts, "acc3", "s-1")
    assert claude.calls == [("acc3", ["--resume", "s-1"])]


def test_resume_given_session_from_another_folder_prints_a_note(work, three_accounts, claude, pipe_stdin, capsys):
    other = work.parent / "other"
    save_session(str(other), "s-2", "main", time.time())
    cmd_resume(three_accounts, None, "s-2")
    assert claude.calls == [("acc2", ["--resume", "s-2"])]
    assert f"cct: note: cct last saw that session in {other}. If Claude Code can't find it" in capsys.readouterr().out


def test_resume_unseen_session_needs_an_account_name(work, three_accounts, claude):
    with pytest.raises(CctError, match="doesn't know which account it ran on. Name the account: cct resume NAME"):
        cmd_resume(three_accounts, None, "0b7c1e7e-unseen")
    assert claude.calls == []


def test_resume_unseen_session_on_a_named_account(work, three_accounts, claude, pipe_stdin, capsys):
    cmd_resume(three_accounts, "acc2", "0b7c1e7e-unseen")
    assert claude.calls == [("acc2", ["--resume", "0b7c1e7e-unseen"])]
    out = capsys.readouterr().out
    assert "cct: resuming session 0b7c1e7e on 'acc2'." in out  # no "last active": cct never saw it
    assert "note:" not in out


@pytest.mark.parametrize("bad", ["--model", "-x", "a b", "a;rm -rf", ""])
def test_resume_rejects_what_is_not_a_session_id(work, three_accounts, claude, bad):
    with pytest.raises(CctError, match="isn't a session ID"):
        cmd_resume(three_accounts, "acc2", bad)
    assert claude.calls == []


def test_resume_ignores_a_saved_id_that_looks_like_an_option(work, three_accounts, claude):
    """A damaged or hand-edited record must never start `claude` with an option the user didn't ask for."""
    from cct import paths
    from cct.services.sessions import project_key
    from cct.utils.fs import write_json

    record = {"folder": str(work), "session_id": "--dangerously-skip-permissions", "account": "main", "updated_at": 1.0}
    write_json(paths.session_dir() / f"{project_key(str(work))}.json", record)
    with pytest.raises(CctError, match="No session recorded for this folder yet"):
        cmd_resume(three_accounts, None)
    assert claude.calls == []
