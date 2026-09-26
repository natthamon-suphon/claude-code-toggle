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
        (run, "cmd_run"),
        (run, "cmd_next"),
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
        (["run"], ("cmd_run", (None, []), {"ask": True})),
        (["run", "acc2", "--no-ask"], ("cmd_run", ("acc2", []), {"ask": False})),
        (
            ["run", "acc2", "--", "--model", "x", "--", "y"],
            ("cmd_run", ("acc2", ["--model", "x", "--", "y"]), {"ask": True}),
        ),
        (["next"], ("cmd_next", (None,), {})),
        (["next", "acc3"], ("cmd_next", ("acc3",), {})),
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


@pytest.mark.parametrize("argv", [[], ["fly"], ["web", "--port", "abc"], ["add"]])
def test_bad_usage_exits_2(argv, capsys):
    with pytest.raises(SystemExit) as exit_info:
        cli.main(argv)
    assert exit_info.value.code == 2


def test_extra_args_only_for_run(capsys):
    with pytest.raises(SystemExit) as exit_info:
        cli.main(["list", "--", "x"])
    assert exit_info.value.code == 2
    assert "arguments after -- only work with `cct run`" in capsys.readouterr().err


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
