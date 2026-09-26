import json

import pytest

from cct.commands.statusline import cmd_install_statusline
from cct.errors import CctError
from cct.services.config import load_config
from cct.services.profiles import link_item
from cct.services.statusline import statusline_command
from cct.utils.fs import is_link, read_json, write_json
from helpers import needs_symlinks


def backups(folder):
    return sorted(p.name for p in folder.glob("settings.json.cct-backup-*"))


def set_statusline(settings_path, command):
    data = read_json(settings_path) or {}
    data["statusLine"] = {"type": "command", "command": command}
    write_json(settings_path, data)


def test_install_into_fresh_settings(claude_home, cfg, capsys):
    assert cmd_install_statusline(cfg) == 0
    settings = read_json(claude_home / "settings.json")
    assert settings["statusLine"] == {"type": "command", "command": statusline_command()}
    assert settings["theme"] == "dark"  # other settings are kept
    assert "ภาษาไทย" in (claude_home / "settings.json").read_text(encoding="utf-8")  # not \u escapes
    assert len(backups(claude_home)) == 1
    out = capsys.readouterr().out
    assert f"installed: {(claude_home / 'settings.json').resolve()}" in out
    assert f"statusline command: {statusline_command()}" in out
    assert load_config()["prev_statusline"] is None


def test_install_twice_is_safe(claude_home, cfg, capsys):
    cmd_install_statusline(cfg)
    capsys.readouterr()
    cmd_install_statusline(load_config())
    assert "already installed:" in capsys.readouterr().out
    assert len(backups(claude_home)) == 1  # no second backup


def test_install_keeps_users_statusline_as_previous(claude_home, cfg, capsys):
    set_statusline(claude_home / "settings.json", "bash ~/my-status.sh")
    cmd_install_statusline(cfg)
    assert "keeping your old statusline, shown under cct's line: bash ~/my-status.sh" in capsys.readouterr().out
    assert load_config()["prev_statusline"] == "bash ~/my-status.sh"
    assert read_json(claude_home / "settings.json")["statusLine"]["command"] == statusline_command()


@pytest.mark.parametrize(
    "old", ["python3 /Users/u/.cct/cct.py statusline", "/usr/bin/python3 /old/place/cct/__main__.py statusline"]
)
def test_install_replaces_older_cct_command_without_chaining_it(claude_home, cfg, old):
    set_statusline(claude_home / "settings.json", old)
    cmd_install_statusline(cfg)
    assert load_config()["prev_statusline"] is None
    assert read_json(claude_home / "settings.json")["statusLine"]["command"] == statusline_command()


def test_install_warns_when_profiles_have_different_statuslines(home, three_accounts, capsys):
    set_statusline(home / ".claude" / "settings.json", "echo one")
    set_statusline(home / ".claude-acc2" / "settings.json", "echo two")
    cmd_install_statusline(three_accounts)
    out = capsys.readouterr().out
    assert "has a different statusline than before; keeping the first one." in out
    assert load_config()["prev_statusline"] == "echo one"
    for name in (".claude", ".claude-acc2", ".claude-acc3"):
        assert read_json(home / name / "settings.json")["statusLine"]["command"] == statusline_command()


def test_install_creates_settings_where_missing(home, three_accounts, capsys):
    cmd_install_statusline(three_accounts)
    assert read_json(home / ".claude-acc3" / "settings.json") == {
        "statusLine": {"type": "command", "command": statusline_command()}
    }
    assert backups(home / ".claude-acc3") == []  # nothing to back up


def test_install_replaces_non_object_settings(claude_home, cfg):
    write_json(claude_home / "settings.json", ["not", "an", "object"])
    cmd_install_statusline(cfg)
    assert read_json(claude_home / "settings.json") == {
        "statusLine": {"type": "command", "command": statusline_command()}
    }


def test_install_refuses_invalid_json(claude_home, cfg):
    (claude_home / "settings.json").write_text("{oops", encoding="utf-8")
    with pytest.raises(CctError, match="is not valid JSON .* Not touching it."):
        cmd_install_statusline(cfg)
    assert (claude_home / "settings.json").read_text(encoding="utf-8") == "{oops"


def test_previous_statusline_survives_a_later_failure(home, three_accounts):
    set_statusline(home / ".claude" / "settings.json", "echo mine")
    (home / ".claude-acc2" / "settings.json").write_text("{oops", encoding="utf-8")
    with pytest.raises(CctError):
        cmd_install_statusline(three_accounts)
    # ~/.claude/settings.json now runs cct, so the old command must be saved already.
    assert load_config()["prev_statusline"] == "echo mine"


@needs_symlinks
def test_install_writes_through_links(home, three_accounts, capsys):
    link = home / ".claude-acc2" / "settings.json"
    link_item(home / ".claude" / "settings.json", link)
    cmd_install_statusline(three_accounts)
    assert is_link(link)  # still a link, not replaced by a copy
    assert json.loads(link.read_text(encoding="utf-8"))["statusLine"]["command"] == statusline_command()
    assert capsys.readouterr().out.count("installed:") == 2  # ~/.claude once, acc3 once; acc2 is the same file
