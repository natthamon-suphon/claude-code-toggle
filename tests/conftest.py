from __future__ import annotations

import json
from pathlib import Path

import pytest

try:
    import cct  # noqa: F401  (the package lives in src/ and is mapped to `cct` by `pip install -e .`)
except ModuleNotFoundError:
    pytest.exit('cct is not importable. Install it first: pip install -e ".[dev]"', returncode=4)

from cct.services.config import load_config, save_config  # noqa: E402

# Variables that change what cct does. No test may see the developer's real values.
CCT_ENV = ("CCT_HOME", "CLAUDE_CONFIG_DIR", "CCT_ACCOUNT", "ANTHROPIC_API_KEY", "NO_COLOR", "WT_SESSION")


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch) -> Path:
    """Every test gets its own HOME with a small ~/.claude, so nothing touches the real one."""
    home = tmp_path / "home"
    claude = home / ".claude"
    (claude / "projects").mkdir(parents=True)
    (claude / "skills").mkdir()
    (claude / "settings.json").write_text(
        json.dumps({"theme": "dark", "note": "ภาษาไทย"}, ensure_ascii=False), encoding="utf-8"
    )
    (claude / "CLAUDE.md").write_text("# memory\n", encoding="utf-8")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))  # what Path.home() reads on Windows
    for var in CCT_ENV:
        monkeypatch.delenv(var, raising=False)
    return home


@pytest.fixture
def claude_home(home) -> Path:
    return home / ".claude"


@pytest.fixture
def cct_home(home) -> Path:
    return home / ".cct"


@pytest.fixture
def work(tmp_path, monkeypatch) -> Path:
    """A project folder, set as the current directory."""
    folder = tmp_path / "work" / "api"
    folder.mkdir(parents=True)
    monkeypatch.chdir(folder)
    return folder


@pytest.fixture
def cfg(home) -> dict:
    """The default config: one account, 'main', using ~/.claude."""
    return load_config()


@pytest.fixture
def three_accounts(home) -> dict:
    """main (default), acc2 and acc3. The profile folders exist but have no links."""
    accounts = [{"name": "main", "dir": None}]
    for name in ("acc2", "acc3"):
        folder = home / f".claude-{name}"
        folder.mkdir()
        accounts.append({"name": name, "dir": str(folder)})
    config = {"accounts": accounts, "prev_statusline": None}
    save_config(config)
    return config
