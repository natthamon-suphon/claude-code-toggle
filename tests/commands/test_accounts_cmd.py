import os

import pytest

from cct.commands.accounts import cmd_add, cmd_link, cmd_list
from cct.config import load_config
from cct.errors import CctError
from cct.utils.fs import is_link
from helpers import needs_symlinks


@needs_symlinks
def test_add_creates_profile_links_items_and_saves(home, cfg, capsys):
    assert cmd_add(cfg, "acc2", None) == 0
    out = capsys.readouterr().out
    assert f"Profile folder: {home / '.claude-acc2'}" in out
    assert "  projects       linked" in out
    assert "  settings.json  linked" in out
    assert "  commands       skipped: not in ~/.claude" in out
    assert "Next: run `cct run acc2` and type /login with that account." in out
    assert is_link(home / ".claude-acc2" / "projects")
    assert load_config()["accounts"][-1] == {"name": "acc2", "dir": str(home / ".claude-acc2")}


@needs_symlinks
def test_add_adopting_a_folder_keeps_its_own_files(home, cfg, capsys):
    old = home / ".claude-old"
    old.mkdir()
    (old / "settings.json").write_text('{"mine": 1}', encoding="utf-8")
    os.symlink(home / ".claude" / "projects", old / "projects", target_is_directory=True)
    cmd_add(cfg, "old", str(old))
    out = capsys.readouterr().out
    assert "  projects       already linked" in out
    assert "  settings.json  SKIPPED: already exists here" in out
    assert (old / "settings.json").read_text(encoding="utf-8") == '{"mine": 1}'


def test_add_bad_name_changes_nothing(home, cfg):
    with pytest.raises(CctError):
        cmd_add(cfg, "bad name", None)
    assert load_config()["accounts"] == [{"name": "main", "dir": None}]
    assert not (home / ".claude-bad name").exists()


def test_link_default_account_is_a_user_error(cfg):
    with pytest.raises(CctError, match="nothing to link"):
        cmd_link(cfg, "main")


def test_link_unknown_account_is_a_user_error(cfg):
    with pytest.raises(CctError, match="No account named"):
        cmd_link(cfg, "nobody")


@needs_symlinks
def test_link_restores_a_missing_link(home, three_accounts, capsys):
    assert cmd_link(three_accounts, "acc2") == 0
    (home / ".claude-acc2" / "CLAUDE.md").unlink()
    capsys.readouterr()
    cmd_link(three_accounts, "acc2")
    out = capsys.readouterr().out
    assert "  CLAUDE.md      linked" in out
    assert "  projects       already linked" in out


@needs_symlinks
def test_list_shows_default_and_link_health(home, three_accounts, capsys):
    cmd_link(three_accounts, "acc2")
    capsys.readouterr()
    assert cmd_list(three_accounts) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == f"main       {home / '.claude'}  (default)"
    assert lines[1] == f"acc2       {home / '.claude-acc2'}  all shared"
    assert lines[2].startswith(f"acc3       {home / '.claude-acc3'}  NOT shared: projects, settings.json")
    assert lines[2].endswith("(move those out of the folder, then: cct link acc3)")
