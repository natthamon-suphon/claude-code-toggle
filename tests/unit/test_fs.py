import json
import os

import pytest

from cct.utils import fs, system
from cct.utils.fs import is_link, read_json, same_file, write_json
from helpers import needs_symlinks


def test_read_json_missing_file_is_none(tmp_path):
    assert read_json(tmp_path / "nope.json") is None


def test_read_json_bad_json_raises_value_error(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError):
        read_json(path)


def test_write_json_round_trip_creates_parents_and_keeps_non_ascii(tmp_path):
    path = tmp_path / "a" / "b" / "data.json"
    data = {"note": "ภาษาไทย", "n": [1, 2]}
    write_json(path, data)
    assert read_json(path) == data
    raw = path.read_text(encoding="utf-8")
    assert "ภาษาไทย" in raw  # not \u escapes
    assert raw.startswith('{\n  "note"')  # indent=2
    assert [p.name for p in path.parent.iterdir()] == ["data.json"]  # no temp file left


def test_write_json_replaces_existing_file(tmp_path):
    path = tmp_path / "data.json"
    write_json(path, {"v": 1})
    write_json(path, {"v": 2})
    assert read_json(path) == {"v": 2}


def test_write_json_retries_when_file_is_busy(tmp_path, monkeypatch):
    real_replace, calls, sleeps = os.replace, [], []

    def flaky_replace(src, dst):
        calls.append(dst)
        if len(calls) < 3:
            raise PermissionError("in use")
        real_replace(src, dst)

    monkeypatch.setattr(fs.os, "replace", flaky_replace)
    monkeypatch.setattr(fs.time, "sleep", sleeps.append)
    path = tmp_path / "data.json"
    write_json(path, {"ok": True})
    assert len(calls) == 3
    assert sleeps == [0.05, 0.05]
    assert read_json(path) == {"ok": True}


def test_write_json_gives_up_after_five_tries_and_cleans_up(tmp_path, monkeypatch):
    calls = []

    def always_busy(src, dst):
        calls.append(dst)
        raise PermissionError("in use")

    monkeypatch.setattr(fs.os, "replace", always_busy)
    monkeypatch.setattr(fs.time, "sleep", lambda s: None)
    folder = tmp_path / "out"
    with pytest.raises(PermissionError):
        write_json(folder / "data.json", {"ok": True})
    assert len(calls) == 5
    assert list(folder.iterdir()) == []  # the temp file is gone too


def test_write_json_output_is_valid_json(tmp_path):
    path = tmp_path / "x.json"
    write_json(path, {"a": None, "b": 1.5})
    assert json.loads(path.read_text(encoding="utf-8")) == {"a": None, "b": 1.5}


def test_same_file(tmp_path):
    a = tmp_path / "a"
    a.mkdir()
    (tmp_path / "b").mkdir()
    assert same_file(a, tmp_path / "b" / ".." / "a")
    assert not same_file(a, tmp_path / "b")


@needs_symlinks
def test_same_file_follows_links(tmp_path):
    a = tmp_path / "a"
    a.mkdir()
    link = tmp_path / "link"
    os.symlink(a, link, target_is_directory=True)
    assert same_file(a, link)


@needs_symlinks
def test_is_link_true_for_symlinks_to_files_and_folders(tmp_path):
    folder, file = tmp_path / "folder", tmp_path / "file"
    folder.mkdir()
    file.write_text("x", encoding="utf-8")
    os.symlink(folder, tmp_path / "l1", target_is_directory=True)
    os.symlink(file, tmp_path / "l2")
    assert is_link(tmp_path / "l1")
    assert is_link(tmp_path / "l2")


@needs_symlinks
def test_is_link_true_for_broken_symlink(tmp_path):
    os.symlink(tmp_path / "gone", tmp_path / "dangling")
    assert is_link(tmp_path / "dangling")


def test_is_link_false_for_plain_items(tmp_path):
    (tmp_path / "folder").mkdir()
    (tmp_path / "file").write_text("x", encoding="utf-8")
    assert not is_link(tmp_path / "folder")
    assert not is_link(tmp_path / "file")
    assert not is_link(tmp_path / "missing")


def test_is_link_uses_isjunction_when_python_has_it(tmp_path, monkeypatch):
    (tmp_path / "junction").mkdir()
    monkeypatch.setattr(os.path, "isjunction", lambda p: True, raising=False)
    assert is_link(tmp_path / "junction")


def test_is_link_reads_junctions_on_old_windows_python(tmp_path, monkeypatch):
    """Before Python 3.12 there is no isjunction; os.readlink succeeds on a junction."""
    (tmp_path / "junction").mkdir()
    (tmp_path / "plain").mkdir()
    monkeypatch.delattr(os.path, "isjunction", raising=False)
    monkeypatch.setattr(system, "IS_WINDOWS", True)

    def fake_readlink(p):
        if os.path.basename(p) == "junction":
            return "C:\\target"
        raise OSError("not a link")

    monkeypatch.setattr(fs.os, "readlink", fake_readlink)
    assert is_link(tmp_path / "junction")
    assert not is_link(tmp_path / "plain")
    assert not is_link(tmp_path / "missing")


def test_is_link_without_isjunction_off_windows_is_false(tmp_path, monkeypatch):
    (tmp_path / "plain").mkdir()
    monkeypatch.delattr(os.path, "isjunction", raising=False)
    monkeypatch.setattr(system, "IS_WINDOWS", False)
    assert not is_link(tmp_path / "plain")
