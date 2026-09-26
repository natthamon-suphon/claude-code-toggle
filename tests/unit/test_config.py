import json

import pytest

from cct import paths
from cct.config import (
    account_names,
    config_home,
    get_account,
    load_config,
    next_account,
    save_config,
)
from cct.errors import CctError
from cct.utils.fs import read_json


def write_raw_config(text: str) -> None:
    paths.config_file().parent.mkdir(parents=True, exist_ok=True)
    paths.config_file().write_text(text, encoding="utf-8")


def test_first_load_creates_default_config(cct_home):
    cfg = load_config()
    assert cfg == {"accounts": [{"name": "main", "dir": None}], "prev_statusline": None}
    assert read_json(cct_home / "config.json") == cfg


def test_cct_home_env_moves_everything(tmp_path, monkeypatch):
    monkeypatch.setenv("CCT_HOME", str(tmp_path / "custom"))
    load_config()
    assert (tmp_path / "custom" / "config.json").is_file()


def test_save_then_load_round_trip(three_accounts):
    assert load_config() == three_accounts
    three_accounts["prev_statusline"] = "echo hi"
    save_config(three_accounts)
    assert load_config()["prev_statusline"] == "echo hi"


@pytest.mark.parametrize(
    "text, message",
    [
        ("{broken", "is not valid JSON"),
        ("[1, 2]", "is not a JSON object"),
        ("{}", "has no accounts"),
        ('{"accounts": []}', "has no accounts"),
        ('{"accounts": {"name": "main"}}', "has no accounts"),
        ('{"accounts": ["main"]}', "Bad account entry"),
        ('{"accounts": [{"dir": null}]}', "Bad account entry"),
        ('{"accounts": [{"name": "../evil"}]}', "Bad account entry"),
        ('{"accounts": [{"name": "has space"}]}', "Bad account entry"),
        ('{"accounts": [{"name": ""}]}', "Bad account entry"),
        (json.dumps({"accounts": [{"name": "x" * 33}]}), "Bad account entry"),
        ('{"accounts": [{"name": 123}]}', "Bad account entry"),
        ('{"accounts": [{"name": "acc\\n"}]}', "Bad account entry"),
        ('{"accounts": [{"name": "acc2", "dir": 5}]}', "Bad account entry"),
        ('{"accounts": [{"name": "main"}], "prev_statusline": 5}', "Bad prev_statusline"),
    ],
)
def test_broken_config_is_a_user_error(text, message):
    write_raw_config(text)
    with pytest.raises(CctError, match=message):
        load_config()


@pytest.mark.parametrize("name", ["main", "acc2", "Work_Account-1", "x" * 32])
def test_valid_names_load(name):
    write_raw_config(json.dumps({"accounts": [{"name": name, "dir": None}]}))
    assert account_names(load_config()) == [name]


def test_account_names_keep_config_order(three_accounts):
    assert account_names(three_accounts) == ["main", "acc2", "acc3"]


def test_get_account(three_accounts):
    assert get_account(three_accounts, "acc2")["name"] == "acc2"
    with pytest.raises(CctError, match="No account named 'nobody'. Known: main, acc2, acc3"):
        get_account(three_accounts, "nobody")


def test_config_home_default_and_profile(home, three_accounts):
    assert config_home(three_accounts["accounts"][0]) == home / ".claude"
    assert config_home(three_accounts["accounts"][1]) == home / ".claude-acc2"


def test_config_home_expands_tilde(home):
    assert config_home({"name": "x", "dir": "~/.claude-x"}) == home / ".claude-x"


@pytest.mark.parametrize(
    "current, expected",
    [("main", "acc2"), ("acc2", "acc3"), ("acc3", "main"), ("", "main"), ("unknown", "main")],
)
def test_next_account_wraps_around(three_accounts, current, expected):
    assert next_account(three_accounts, current)["name"] == expected


def test_next_account_needs_two_accounts(cfg):
    with pytest.raises(CctError, match="Only one account"):
        next_account(cfg, "main")
