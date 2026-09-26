import io

import pytest

from cct.utils import system
from cct.utils.terminal import supports_color, supports_utf8


class Stream:
    def __init__(self, tty=True, encoding="utf-8"):
        self._tty, self.encoding = tty, encoding

    def isatty(self):
        return self._tty


@pytest.mark.parametrize(
    "encoding, expected",
    [("utf-8", True), ("UTF-8", True), ("utf8", True), ("cp1252", False), ("ascii", False), (None, False)],
)
def test_supports_utf8(encoding, expected):
    assert supports_utf8(Stream(encoding=encoding)) is expected


def test_supports_utf8_on_stream_without_encoding():
    assert supports_utf8(io.BytesIO()) is False


def test_color_on_a_posix_tty(monkeypatch):
    monkeypatch.setattr(system, "IS_WINDOWS", False)
    assert supports_color(Stream(tty=True)) is True


def test_no_color_when_not_a_tty(monkeypatch):
    monkeypatch.setattr(system, "IS_WINDOWS", False)
    assert supports_color(Stream(tty=False)) is False


def test_no_color_when_no_color_is_set(monkeypatch):
    monkeypatch.setattr(system, "IS_WINDOWS", False)
    monkeypatch.setenv("NO_COLOR", "1")
    assert supports_color(Stream(tty=True)) is False


def test_windows_console_needs_windows_terminal(monkeypatch):
    monkeypatch.setattr(system, "IS_WINDOWS", True)
    assert supports_color(Stream(tty=True)) is False
    monkeypatch.setenv("WT_SESSION", "some-guid")
    assert supports_color(Stream(tty=True)) is True
