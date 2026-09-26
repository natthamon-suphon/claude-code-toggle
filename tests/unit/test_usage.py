import time

import pytest

from cct import paths
from cct.services.usage import load_usage, parse_window, update_usage, usage_rows, window_view
from cct.utils.fs import read_json, write_json
from helpers import write_usage

T = 1_790_000_000.0


# ------------------------------------------------------------------ parse_window


def test_parse_window_reads_percent_and_reset():
    assert parse_window({"used_percentage": 42, "resets_at": 1790429406}) == {"pct": 42.0, "resets_at": 1790429406.0}


def test_parse_window_accepts_percent_as_text():
    assert parse_window({"used_percentage": "42.5"})["pct"] == 42.5


def test_parse_window_accepts_iso_reset_time():
    assert parse_window({"used_percentage": 1, "resets_at": "1970-01-01T00:01:40Z"})["resets_at"] == 100.0


def test_parse_window_without_reset_time():
    assert parse_window({"used_percentage": 1}) == {"pct": 1.0, "resets_at": None}


@pytest.mark.parametrize("raw", [None, [], "50%", {}, {"used_percentage": None}, {"resets_at": 1}])
def test_parse_window_missing_data_is_none(raw):
    assert parse_window(raw) is None


def test_parse_window_bad_percent_raises():
    """The statusline hook catches this and logs it."""
    with pytest.raises(ValueError):
        parse_window({"used_percentage": "lots"})


# ------------------------------------------------------------------ update_usage


def limits(five=None, seven=None):
    out = {}
    if five is not None:
        out["five_hour"] = {"used_percentage": five, "resets_at": T + 100}
    if seven is not None:
        out["seven_day"] = {"used_percentage": seven, "resets_at": T + 1000}
    return out


def test_update_usage_saves_both_windows():
    usage = update_usage("acc2", limits(40, 13), T)
    assert usage == {
        "five_hour": {"pct": 40.0, "resets_at": T + 100},
        "seven_day": {"pct": 13.0, "resets_at": T + 1000},
        "updated_at": T,
    }
    assert read_json(paths.usage_dir() / "acc2.json") == usage


def test_update_usage_keeps_the_other_window():
    update_usage("acc2", limits(40, 13), T)
    usage = update_usage("acc2", limits(five=55), T + 5)
    assert usage["five_hour"]["pct"] == 55.0
    assert usage["seven_day"]["pct"] == 13.0
    assert usage["updated_at"] == T + 5


@pytest.mark.parametrize("raw", [None, {}, [], "x", {"five_hour": None}])
def test_update_usage_without_limits_changes_nothing(raw):
    write_usage("acc2", five=(10, T + 1), updated_at=1.0)
    before = read_json(paths.usage_dir() / "acc2.json")
    assert update_usage("acc2", raw, T) == before
    assert read_json(paths.usage_dir() / "acc2.json") == before


def test_update_usage_never_saves_unknown_account():
    update_usage("unknown", limits(40, 13), T)
    assert not (paths.usage_dir() / "unknown.json").exists()


def test_load_usage_missing_or_broken_is_empty():
    assert load_usage("nobody") == {}
    write_json(paths.usage_dir() / "bad.json", [1, 2])
    assert load_usage("bad") == {}


# ------------------------------------------------------------------ window_view


def test_window_view_ok():
    assert window_view({"pct": 40.0, "resets_at": T + 10}, T) == {"state": "ok", "pct": 40.0, "resets_at": T + 10}


def test_window_view_ok_without_reset_time():
    assert window_view({"pct": 40.0, "resets_at": None}, T) == {"state": "ok", "pct": 40.0, "resets_at": None}


@pytest.mark.parametrize("resets_at", [T, T - 1])
def test_window_view_reset_once_reset_time_has_passed(resets_at):
    assert window_view({"pct": 99.0, "resets_at": resets_at}, T) == {"state": "reset", "resets_at": resets_at}


@pytest.mark.parametrize("window", [None, {}, "x", [], {"pct": "40"}, {"pct": None}, {"resets_at": T}])
def test_window_view_unknown_for_missing_or_damaged_data(window):
    assert window_view(window, T) == {"state": "unknown"}


def test_window_view_ignores_damaged_reset_time():
    assert window_view({"pct": 5, "resets_at": "tomorrow"}, T) == {"state": "ok", "pct": 5, "resets_at": None}


# ------------------------------------------------------------------ usage_rows


def test_usage_rows_one_row_per_account_in_order(three_accounts):
    now = time.time()
    write_usage("main", five=(97, now + 100), seven=(32, now + 1000), updated_at=now)
    write_usage("acc2", five=(40, now - 1), updated_at=now - 50)
    rows = usage_rows(three_accounts)
    assert [r["name"] for r in rows] == ["main", "acc2", "acc3"]
    assert rows[0]["five_hour"]["state"] == "ok" and rows[0]["five_hour"]["pct"] == 97
    assert rows[0]["updated_at"] == now
    assert rows[1]["five_hour"]["state"] == "reset"
    assert rows[1]["seven_day"] == {"state": "unknown"}
    assert rows[2] == {
        "name": "acc3",
        "updated_at": None,
        "five_hour": {"state": "unknown"},
        "seven_day": {"state": "unknown"},
    }
