"""The schema: document shapes and the checks that keep damaged files from crashing cct."""

import time

import pytest

from cct.errors import CctError
from cct.schema.common import MAX_TIMESTAMP, is_number, is_timestamp
from cct.schema.config import default_config, is_valid_name, validate_config
from cct.schema.session import Session, valid_session
from cct.schema.statusline import parse_input, parse_window, project_folder, session_id
from cct.schema.usage import Usage, Window, valid_usage, valid_window
from cct.services.sessions import last_session, save_session
from cct.services.usage import update_usage

T = 1_790_000_000.0


NAN, INF = float("nan"), float("inf")
HUGE = 10**400  # json.loads turns a long run of digits into an int too big for a float


@pytest.mark.parametrize(
    "value, expected",
    [(1, True), (1.5, True), (0, True), (-3, True), (True, False), ("1", False), (None, False),
     (NAN, False), (INF, False), (-INF, False), (HUGE, False)],
)  # fmt: skip
def test_is_number(value, expected):
    assert is_number(value) is expected


@pytest.mark.parametrize(
    "value, expected",
    [(0, True), (T, True), (MAX_TIMESTAMP, True), (-1, False), (MAX_TIMESTAMP + 1, False), (1e17, False),
     (NAN, False), (INF, False), (HUGE, False), (True, False), ("1", False)],
)  # fmt: skip
def test_is_timestamp(value, expected):
    assert is_timestamp(value) is expected


# ------------------------------------------------------------------ config


@pytest.mark.parametrize(
    "name, expected",
    [("main", True), ("Work_2-x", True), ("x" * 32, True), ("x" * 33, False), ("", False), ("a b", False),
     ("../x", False), ("acc\n", False), ("ภาษา", False), (123, False), (None, False)],
)  # fmt: skip
def test_is_valid_name(name, expected):
    assert is_valid_name(name) is expected


def test_default_config_is_valid():
    assert validate_config(default_config(), "config.json") == {
        "accounts": [{"name": "main", "dir": None}],
        "prev_statusline": None,
    }


def test_validate_config_returns_the_same_document_with_extra_keys():
    data = {"accounts": [{"name": "main", "dir": None, "note": "mine"}], "extra": 1}
    assert validate_config(data, "config.json") is data


def test_validate_config_names_the_file_in_errors():
    with pytest.raises(CctError, match="^/x/config.json has no accounts"):
        validate_config({}, "/x/config.json")


# ------------------------------------------------------------------ usage


def test_valid_window():
    assert valid_window({"pct": 40, "resets_at": T}) == {"pct": 40, "resets_at": T}
    assert valid_window({"pct": 40.5}) == {"pct": 40.5, "resets_at": None}
    assert valid_window({"pct": 40, "resets_at": "soon"}) == {"pct": 40, "resets_at": None}


@pytest.mark.parametrize(
    "raw",
    [None, [], "x", {}, {"pct": "40"}, {"pct": True}, {"resets_at": T}, {"pct": NAN}, {"pct": INF}, {"pct": HUGE}],
)
def test_valid_window_rejects_damaged_windows(raw):
    assert valid_window(raw) is None


@pytest.mark.parametrize("resets_at", [NAN, INF, -1, 1e17, HUGE])
def test_valid_window_drops_impossible_reset_times(resets_at):
    assert valid_window({"pct": 40, "resets_at": resets_at}) == {"pct": 40, "resets_at": None}


@pytest.mark.parametrize("raw", [None, [], "x", 5])
def test_valid_usage_of_missing_or_broken_file_is_empty(raw):
    assert valid_usage(raw) == {}


def test_valid_usage_keeps_good_parts_only():
    raw = {
        "five_hour": {"pct": 10, "resets_at": T},
        "seven_day": "damaged",
        "updated_at": "yesterday",
        "unknown": 1,
    }
    assert valid_usage(raw) == {"five_hour": {"pct": 10, "resets_at": T}}


@pytest.mark.parametrize("updated_at", [NAN, INF, -1, 1e17, HUGE])
def test_valid_usage_drops_impossible_update_times(updated_at):
    assert valid_usage({"five_hour": {"pct": 10, "resets_at": T}, "updated_at": updated_at}) == {
        "five_hour": {"pct": 10, "resets_at": T}
    }


def test_saved_usage_matches_the_schema():
    usage = update_usage("main", {"five_hour": {"used_percentage": 5, "resets_at": T}}, T)
    assert valid_usage(usage) == usage
    assert set(usage) <= set(Usage.__annotations__)
    assert set(usage["five_hour"]) == set(Window.__annotations__)


# ------------------------------------------------------------------ session


def test_valid_session_passes_good_sessions_through():
    good = {"folder": "/p", "session_id": "abc", "account": "main", "updated_at": T}
    assert valid_session(good) == good


@pytest.mark.parametrize("raw", [None, [], {}, {"session_id": ""}, {"session_id": 12345}, {"session_id": None}])
def test_valid_session_needs_a_session_id(raw):
    assert valid_session(raw) is None


def test_valid_session_repairs_other_damaged_fields():
    raw = {"session_id": "abc", "folder": 5, "account": ["x"], "updated_at": "yesterday"}
    assert valid_session(raw) == {"folder": "", "session_id": "abc", "account": "", "updated_at": 0.0}


@pytest.mark.parametrize("updated_at", [NAN, INF, 1e17, HUGE])
def test_valid_session_repairs_impossible_update_times(updated_at):
    raw = {"folder": "/p", "session_id": "abc", "account": "main", "updated_at": updated_at}
    assert valid_session(raw)["updated_at"] == 0.0


def test_saved_session_matches_the_schema(work):
    save_session(str(work), "abc", "main", time.time())
    session = last_session(work)
    assert set(session) == Session.__required_keys__


# ------------------------------------------------------------------ statusline input


@pytest.mark.parametrize("raw", ["", "  \n"])
def test_parse_input_empty_is_an_empty_object(raw):
    assert parse_input(raw) == {}


def test_parse_input_object():
    assert parse_input('{"session_id": "s"}') == {"session_id": "s"}


@pytest.mark.parametrize("raw", ["{broken", "[1, 2]", '"text"', "42", "null"])
def test_parse_input_rejects_non_objects(raw):
    with pytest.raises(ValueError):
        parse_input(raw)


@pytest.mark.parametrize(
    "data, expected",
    [
        ({"cwd": "/c", "workspace": {"project_dir": "/p", "current_dir": "/w"}}, "/p"),
        ({"cwd": "/c", "workspace": {"current_dir": "/w"}}, "/c"),
        ({"workspace": {"current_dir": "/w"}}, "/w"),
        ({"cwd": "/c", "workspace": "not-an-object"}, "/c"),
        ({}, None),
    ],
)
def test_project_folder_order(data, expected):
    assert project_folder(data) == expected


@pytest.mark.parametrize(
    "data, expected", [({"session_id": "s"}, "s"), ({"session_id": ""}, None), ({"session_id": 5}, None), ({}, None)]
)
def test_session_id(data, expected):
    assert session_id(data) == expected


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


@pytest.mark.parametrize("pct, error", [("lots", ValueError), ([1], TypeError)])
def test_parse_window_bad_percent_raises(pct, error):
    """The statusline hook catches these and logs them."""
    with pytest.raises(error):
        parse_window({"used_percentage": pct})


@pytest.mark.parametrize("pct", ["nan", "inf", "-Infinity", "1e400", NAN, INF, HUGE])
def test_parse_window_rejects_percent_that_is_not_finite(pct):
    """Saved, it would break `cct status` and the dashboard's JSON. The statusline hook logs it instead."""
    with pytest.raises(ValueError):
        parse_window({"used_percentage": pct})


@pytest.mark.parametrize("resets_at", [1e17, INF, NAN, HUGE, "1" * 400, "9999-12-31T00:00:00Z", -5])
def test_parse_window_drops_impossible_reset_time(resets_at):
    assert parse_window({"used_percentage": 1, "resets_at": resets_at}) == {"pct": 1.0, "resets_at": None}


def test_parsed_window_matches_the_saved_shape():
    window = parse_window({"used_percentage": 1, "resets_at": 100})
    assert valid_window(window) == window
