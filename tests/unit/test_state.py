import pytest

from cct import paths
from cct.services import state
from cct.services.state import log_error, read_state


def test_log_error_appends_lines(cct_home):
    log_error("here", ValueError("first"))
    log_error("there", OSError("second"))
    lines = (cct_home / "error.log").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert "[here] ValueError('first')" in lines[0]
    assert "[there] OSError('second')" in lines[1]


def test_log_error_falls_back_to_stderr(monkeypatch, capsys, tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x", encoding="utf-8")
    monkeypatch.setenv("CCT_HOME", str(blocker / "cct"))  # a folder under a file can't be made
    log_error("here", ValueError("boom"))
    assert "could not write error log" in capsys.readouterr().err


def test_read_state_missing_is_none(tmp_path):
    assert read_state(tmp_path / "missing.json") is None


def test_read_state_returns_objects(tmp_path):
    (tmp_path / "ok.json").write_text('{"a": 1}', encoding="utf-8")
    assert read_state(tmp_path / "ok.json") == {"a": 1}


@pytest.mark.parametrize("text", ["{broken", "[1, 2]", '"text"', "42", "null"])
def test_read_state_treats_bad_files_as_no_data_and_logs(tmp_path, text):
    path = tmp_path / "bad.json"
    path.write_text(text, encoding="utf-8")
    assert read_state(path) is None
    if text != "null":  # a JSON null is just "no data"
        assert "read bad.json" in paths.error_log().read_text(encoding="utf-8")


def test_read_state_logs_os_errors(tmp_path, monkeypatch):
    def locked(path):
        raise PermissionError("locked")

    monkeypatch.setattr(state, "read_json", locked)
    assert read_state(tmp_path / "x.json") is None
    assert "PermissionError('locked')" in paths.error_log().read_text(encoding="utf-8")
