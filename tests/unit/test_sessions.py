import os
import re

from cct import paths
from cct.services.sessions import last_session, project_key, recent_sessions, save_session
from cct.utils.fs import write_json
from helpers import needs_symlinks


def test_project_key_is_short_hex_and_stable(tmp_path):
    key = project_key(str(tmp_path))
    assert re.fullmatch(r"[0-9a-f]{16}", key)
    assert project_key(str(tmp_path)) == key


def test_project_key_ignores_spelling_differences(tmp_path, monkeypatch):
    (tmp_path / "a").mkdir()
    monkeypatch.chdir(tmp_path)
    assert project_key(str(tmp_path / "a")) == project_key("a")
    assert project_key(str(tmp_path / "a")) == project_key(str(tmp_path / "a") + os.sep)
    assert project_key(str(tmp_path / "a")) == project_key(str(tmp_path / "a" / ".." / "a"))


def test_project_key_differs_between_folders(tmp_path):
    assert project_key(str(tmp_path / "a")) != project_key(str(tmp_path / "b"))


@needs_symlinks
def test_project_key_same_through_a_symlink(tmp_path):
    (tmp_path / "real").mkdir()
    os.symlink(tmp_path / "real", tmp_path / "link", target_is_directory=True)
    assert project_key(str(tmp_path / "link")) == project_key(str(tmp_path / "real"))


def test_save_and_read_last_session(work):
    save_session(str(work), "uuid-1", "acc2", 123.0)
    assert last_session(work) == {"folder": str(work), "session_id": "uuid-1", "account": "acc2", "updated_at": 123.0}


def test_newer_session_replaces_older(work):
    save_session(str(work), "uuid-1", "main", 1.0)
    save_session(str(work), "uuid-2", "acc2", 2.0)
    assert last_session(work)["session_id"] == "uuid-2"


def test_last_session_none_when_nothing_recorded(work):
    assert last_session(work) is None


def test_last_session_broken_file_is_none(work):
    path = paths.session_dir() / f"{project_key(str(work))}.json"
    path.parent.mkdir(parents=True)
    path.write_text("[1]", encoding="utf-8")
    assert last_session(work) is None


def test_recent_sessions_empty_without_folder():
    assert recent_sessions() == []


def test_recent_sessions_newest_first_with_limit(tmp_path):
    for i in range(10):
        save_session(str(tmp_path / f"p{i}"), f"session-{i:02d}-long-id", "main", float(i))
    rows = recent_sessions(limit=3)
    assert [r["folder"] for r in rows] == [str(tmp_path / f"p{i}") for i in (9, 8, 7)]
    assert rows[0] == {"folder": str(tmp_path / "p9"), "account": "main", "updated_at": 9.0, "session": "session-"}


def test_recent_sessions_default_limit_is_eight(tmp_path):
    for i in range(10):
        save_session(str(tmp_path / f"p{i}"), f"s{i}", "main", float(i))
    assert len(recent_sessions()) == 8


def test_recent_sessions_skips_broken_and_empty_entries(tmp_path):
    save_session(str(tmp_path / "good"), "good-id", "main", 5.0)
    write_json(paths.session_dir() / "nosession.json", {"folder": "x", "updated_at": 9.0})
    (paths.session_dir() / "broken.json").write_text("{", encoding="utf-8")
    assert [r["session"] for r in recent_sessions()] == ["good-id"]
