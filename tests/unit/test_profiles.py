import os
import subprocess

import pytest

from cct.errors import CctError
from cct.services import profiles
from cct.services.config import load_config
from cct.services.profiles import (
    SHARED_ITEMS,
    create_profile_dir,
    link_item,
    link_shared,
    register_profile,
    unshared_items,
)
from cct.utils import system
from cct.utils.fs import is_link, same_file
from helpers import needs_symlinks


@pytest.fixture
def src(tmp_path):
    folder = tmp_path / "src"
    folder.mkdir()
    (folder / "dir").mkdir()
    (folder / "file.json").write_text("{}", encoding="utf-8")
    return folder


@pytest.fixture
def dst(tmp_path):
    folder = tmp_path / "dst"
    folder.mkdir()
    return folder


# ------------------------------------------------------------------ link_item


@needs_symlinks
@pytest.mark.parametrize("name", ["dir", "file.json"])
def test_link_item_links_folders_and_files(src, dst, name):
    assert link_item(src / name, dst / name) == "linked"
    assert is_link(dst / name)
    assert same_file(dst / name, src / name)


@needs_symlinks
def test_link_item_twice_says_already_linked(src, dst):
    link_item(src / "dir", dst / "dir")
    assert link_item(src / "dir", dst / "dir") == "already linked"


@needs_symlinks
def test_link_item_never_replaces_a_link_to_somewhere_else(src, dst, tmp_path):
    other = tmp_path / "other"
    other.mkdir()
    os.symlink(other, dst / "dir", target_is_directory=True)
    assert link_item(src / "dir", dst / "dir") == "SKIPPED: links somewhere else"
    assert same_file(dst / "dir", other)


def test_link_item_never_overwrites_a_real_item(src, dst):
    (dst / "file.json").write_text('{"mine": true}', encoding="utf-8")
    assert link_item(src / "file.json", dst / "file.json").startswith("SKIPPED: already exists here")
    assert (dst / "file.json").read_text(encoding="utf-8") == '{"mine": true}'


def test_link_item_skips_items_missing_from_claude_home(src, dst):
    assert link_item(src / "agents", dst / "agents") == "skipped: not in ~/.claude"
    assert not (dst / "agents").exists()


@needs_symlinks
def test_link_item_creates_missing_projects_folder(src, dst):
    assert link_item(src / "projects", dst / "projects") == "linked"
    assert (src / "projects").is_dir()


def test_link_item_symlink_error_is_raised_off_windows(src, dst, monkeypatch):
    monkeypatch.setattr(system, "IS_WINDOWS", False)
    monkeypatch.setattr(profiles.os, "symlink", _no_symlinks)
    with pytest.raises(OSError):
        link_item(src / "dir", dst / "dir")


def _no_symlinks(*args, **kwargs):
    raise OSError("A required privilege is not held by the client")


def test_link_item_windows_folder_falls_back_to_junction(src, dst, monkeypatch):
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, "Junction created", "")

    monkeypatch.setattr(system, "IS_WINDOWS", True)
    monkeypatch.setattr(profiles.os, "symlink", _no_symlinks)
    monkeypatch.setattr(profiles.subprocess, "run", fake_run)
    assert link_item(src / "dir", dst / "dir") == "linked (junction)"
    assert calls == [["cmd", "/c", "mklink", "/J", str(dst / "dir"), str(src / "dir")]]


def test_link_item_windows_junction_failure_is_a_user_error(src, dst, monkeypatch):
    monkeypatch.setattr(system, "IS_WINDOWS", True)
    monkeypatch.setattr(profiles.os, "symlink", _no_symlinks)
    monkeypatch.setattr(
        profiles.subprocess, "run", lambda cmd, **kw: subprocess.CompletedProcess(cmd, 1, "", "Access is denied.\n")
    )
    with pytest.raises(CctError, match="mklink /J failed .*Access is denied."):
        link_item(src / "dir", dst / "dir")


def test_link_item_windows_file_is_copied_as_last_resort(src, dst, monkeypatch):
    monkeypatch.setattr(system, "IS_WINDOWS", True)
    monkeypatch.setattr(profiles.os, "symlink", _no_symlinks)
    assert link_item(src / "file.json", dst / "file.json").startswith("COPIED, not linked")
    assert (dst / "file.json").read_text(encoding="utf-8") == "{}"
    assert not is_link(dst / "file.json")


# ------------------------------------------------------------------ profiles


def test_create_profile_dir_default_location(home, cfg):
    target = create_profile_dir(cfg, "acc2", None)
    assert target == home / ".claude-acc2"
    assert target.is_dir()
    assert target.is_absolute()


def test_create_profile_dir_adopts_existing_folder(home, cfg):
    existing = home / "old-profile"
    existing.mkdir()
    (existing / "keep.txt").write_text("x", encoding="utf-8")
    assert create_profile_dir(cfg, "acc2", "~/old-profile") == existing
    assert (existing / "keep.txt").exists()


@pytest.mark.parametrize("name", ["", "has space", "a/b", "..", "x" * 33, "ภาษา"])
def test_create_profile_dir_rejects_bad_names(cfg, name):
    with pytest.raises(CctError, match="Use letters, digits"):
        create_profile_dir(cfg, name, None)


def test_create_profile_dir_rejects_duplicate_name(cfg):
    with pytest.raises(CctError, match="already exists"):
        create_profile_dir(cfg, "main", None)


def test_create_profile_dir_rejects_default_folder(home, cfg):
    with pytest.raises(CctError, match="default folder"):
        create_profile_dir(cfg, "acc2", str(home / ".claude"))


def test_create_profile_dir_rejects_folder_of_another_account(home, three_accounts):
    with pytest.raises(CctError, match="already belongs to account 'acc2'"):
        create_profile_dir(three_accounts, "acc4", str(home / ".claude-acc2"))


def test_register_profile_saves_config(home, cfg):
    register_profile(cfg, "acc2", home / ".claude-acc2")
    assert load_config()["accounts"][-1] == {"name": "acc2", "dir": str(home / ".claude-acc2")}


@needs_symlinks
def test_link_shared_reports_every_item_in_order(claude_home, tmp_path):
    profile = tmp_path / "profile"
    profile.mkdir()
    results = list(link_shared(profile))
    assert [item for item, _ in results] == list(SHARED_ITEMS)
    assert dict(results) == {
        "projects": "linked",
        "settings.json": "linked",
        "CLAUDE.md": "linked",
        "skills": "linked",
        "commands": "skipped: not in ~/.claude",
        "agents": "skipped: not in ~/.claude",
    }


@needs_symlinks
def test_unshared_items(home, three_accounts):
    acc2 = three_accounts["accounts"][1]
    list(link_shared(home / ".claude-acc2"))
    assert unshared_items(acc2) == []
    (home / ".claude-acc2" / "skills").unlink()
    (home / ".claude-acc2" / "skills").mkdir()  # a real folder instead of the link
    assert unshared_items(acc2) == ["skills"]


def test_unshared_items_lists_everything_for_an_empty_profile(three_accounts):
    # commands and agents don't exist in ~/.claude, so they are not missing links.
    assert unshared_items(three_accounts["accounts"][1]) == ["projects", "settings.json", "CLAUDE.md", "skills"]
