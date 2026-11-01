import pytest

from cct import __version__, cli, paths
from cct.commands import accounts, run, status, statusline, web


@pytest.fixture
def calls(monkeypatch):
    """Replace every command with a recorder."""
    seen = []

    def recorder(name):
        def fake(*args, **kwargs):
            seen.append((name, args[1:] if args and isinstance(args[0], dict) else args, kwargs))
            return 0

        return fake

    for module, fn in [
        (accounts, "cmd_add"),
        (accounts, "cmd_list"),
        (accounts, "cmd_link"),
        (run, "cmd_start"),
        (run, "cmd_resume"),
        (status, "cmd_status"),
        (web, "cmd_web"),
        (statusline, "cmd_install_statusline"),
        (statusline, "cmd_statusline"),
    ]:
        monkeypatch.setattr(module, fn, recorder(fn))
    return seen


@pytest.mark.parametrize(
    "argv, expected",
    [
        (["add", "acc2"], ("cmd_add", ("acc2", None), {})),
        (["add", "acc2", "--dir", "~/x"], ("cmd_add", ("acc2", "~/x"), {})),
        (["list"], ("cmd_list", (), {})),
        (["link", "acc2"], ("cmd_link", ("acc2",), {})),
        (["start"], ("cmd_start", (None, []), {"ask": True})),
        (["start", "acc2", "--no-ask"], ("cmd_start", ("acc2", []), {"ask": False})),
        (
            ["start", "acc2", "--", "--model", "x", "--", "y"],
            ("cmd_start", ("acc2", ["--model", "x", "--", "y"]), {"ask": True}),
        ),
        (["resume"], ("cmd_resume", (None, None), {})),
        (["resume", "acc3"], ("cmd_resume", ("acc3", None), {})),
        (["resume", "acc3", "--session", "abc-1"], ("cmd_resume", ("acc3", "abc-1"), {})),
        (["resume", "-s", "abc-1"], ("cmd_resume", (None, "abc-1"), {})),
        (["resume", "--session", "abc-1", "acc2"], ("cmd_resume", ("acc2", "abc-1"), {})),
        (["status"], ("cmd_status", (), {})),
        (["web"], ("cmd_web", (8765, True), {})),
        (["web", "--port", "9000", "--no-open"], ("cmd_web", (9000, False), {})),
        (["install-statusline"], ("cmd_install_statusline", (), {})),
        (["statusline"], ("cmd_statusline", (), {})),
    ],
)
def test_dispatch(calls, argv, expected):
    assert cli.main(argv) == 0
    assert calls == [expected]


def test_statusline_does_not_touch_config_or_argparse(calls, monkeypatch):
    monkeypatch.setattr(cli, "build_parser", lambda: pytest.fail("argparse must not run"))
    cli.main(["statusline", "ignored", "--args"])
    assert calls == [("cmd_statusline", (), {})]
    assert not paths.config_file().exists()


def test_version(capsys):
    with pytest.raises(SystemExit) as exit_info:
        cli.main(["--version"])
    assert exit_info.value.code == 0
    assert capsys.readouterr().out.strip() == f"cct {__version__}"


@pytest.mark.parametrize(
    "argv",
    [[], ["fly"], ["web", "--port", "abc"], ["web", "--port", "99999"], ["web", "--port", "-1"], ["add"]],
)
def test_bad_usage_exits_2(argv, capsys):
    with pytest.raises(SystemExit) as exit_info:
        cli.main(argv)
    assert exit_info.value.code == 2


@pytest.mark.parametrize("old_name", ["run", "next"])
def test_old_command_names_are_gone(capsys, old_name):
    """`cct run` became `cct start`, and `cct next` became `cct resume`."""
    with pytest.raises(SystemExit) as exit_info:
        cli.main([old_name])
    assert exit_info.value.code == 2
    assert "invalid choice" in capsys.readouterr().err


def test_extra_args_only_for_start(capsys):
    with pytest.raises(SystemExit) as exit_info:
        cli.main(["list", "--", "x"])
    assert exit_info.value.code == 2
    assert "arguments after -- only work with `cct start`" in capsys.readouterr().err


def test_user_errors_exit_1_with_a_message(capsys):
    assert cli.main(["link", "nobody"]) == 1
    err = capsys.readouterr().err
    assert err.startswith("cct: No account named 'nobody'")
    assert "Traceback" not in err


def test_broken_config_exits_1(capsys):
    paths.config_file().parent.mkdir(parents=True)
    paths.config_file().write_text("[]", encoding="utf-8")
    assert cli.main(["list"]) == 1
    assert "is not a JSON object" in capsys.readouterr().err


def test_main_reads_sys_argv(monkeypatch, calls):
    monkeypatch.setattr(cli.sys, "argv", ["cct", "status"])
    assert cli.main() == 0
    assert calls == [("cmd_status", (), {})]


@pytest.mark.parametrize("port", ["0", "65535"])
def test_web_port_range_ends_are_accepted(calls, port):
    assert cli.main(["web", "--port", port]) == 0
    assert calls == [("cmd_web", (int(port), True), {})]


def test_file_problems_exit_1_without_a_traceback(capsys, monkeypatch):
    """For example a read-only ~/.cct, or ~/.cct being a file."""
    monkeypatch.setattr(paths, "cct_home", lambda: paths.Path(__file__))  # a file, not a folder
    assert cli.main(["list"]) == 1
    err = capsys.readouterr().err
    assert err.startswith("cct: [Errno")
    assert "Traceback" not in err


def test_closed_output_pipe_exits_1_quietly(capsys, monkeypatch):
    def closed(cfg):
        raise BrokenPipeError(32, "Broken pipe")

    monkeypatch.setattr(status, "cmd_status", closed)
    assert cli.main(["status"]) == 1
    assert "Traceback" not in capsys.readouterr().err


def test_ctrl_c_exits_130_without_a_traceback(capsys, monkeypatch):
    def interrupted(cfg):
        raise KeyboardInterrupt

    monkeypatch.setattr(status, "cmd_status", interrupted)
    assert cli.main(["status"]) == 130
    assert "Traceback" not in capsys.readouterr().err
