import time
from datetime import datetime, timezone

import pytest

from cct.utils.timefmt import fmt_ago, fmt_left, to_epoch

NOW = 1_790_000_000.0
UTC_10AM = datetime(2026, 9, 26, 10, tzinfo=timezone.utc).timestamp()


@pytest.fixture
def frozen(monkeypatch):
    monkeypatch.setattr(time, "time", lambda: NOW)
    return NOW


@pytest.mark.parametrize(
    "value, expected",
    [
        (1790429406, 1790429406.0),
        (1790429406.5, 1790429406.5),
        (1790429406000, 1790429406.0),  # milliseconds
        (0, 0.0),
        ("1790429406", 1790429406.0),
        (" 1790429406.25 ", 1790429406.25),
        ("1790429406000", 1790429406.0),
        ("2026-09-26T10:00:00Z", UTC_10AM),
        ("2026-09-26T10:00:00+00:00", UTC_10AM),
        ("2026-09-26T17:00:00+07:00", UTC_10AM),
        ("2026-09-26T10:00:00.500000Z", UTC_10AM + 0.5),
    ],
)
def test_to_epoch_accepts_seconds_milliseconds_and_iso(value, expected):
    assert to_epoch(value) == pytest.approx(expected)


@pytest.mark.parametrize(
    "value",
    [None, True, False, "", "soon", "12abc", "2026-13-45T00:00:00Z", "0001-01-01T00:00:00", 10**400, [], {}, object()],
)
def test_to_epoch_returns_none_for_anything_else(value):
    assert to_epoch(value) is None


def test_to_epoch_always_returns_float():
    assert isinstance(to_epoch(1790429406), float)


@pytest.mark.parametrize(
    "offset, expected",
    [
        (-5, "now"),
        (0, "now"),
        (30, "1m"),  # under a minute still shows 1m, never 0m
        (90, "1m"),
        (59 * 60, "59m"),
        (3 * 3600 + 5 * 60, "3h 5m"),
        (2 * 86400 + 3 * 3600 + 59, "2d 3h"),
    ],
)
def test_fmt_left(frozen, offset, expected):
    assert fmt_left(NOW + offset) == expected


@pytest.mark.parametrize(
    "ts, expected",
    [
        (None, "never"),
        (0, "never"),
        (NOW - 10, "just now"),
        (NOW + 100, "just now"),  # clock skew: a time in the future is not an error
        (NOW - 120, "2m ago"),
        (NOW - 7200, "2h ago"),
        (NOW - 3 * 86400, "3d ago"),
    ],
)
def test_fmt_ago(frozen, ts, expected):
    assert fmt_ago(ts) == expected
