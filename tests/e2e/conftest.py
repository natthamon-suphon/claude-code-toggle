from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SRC = REPO / "src"
ENTRY = SRC / "__main__.py"
FAKE_CLAUDE = Path(__file__).with_name("fake_claude.py")


class Env:
    """A fake computer: HOME, a fake `claude` on PATH, and helpers to run cct in it."""

    def __init__(self, root: Path, home: Path):
        self.home, self.work, self.log = home, root / "work" / "api", root / "fake.log"
        self.entry = ENTRY
        self.work.mkdir(parents=True)
        bin_dir = root / "bin"
        bin_dir.mkdir()
        if os.name == "nt":
            (bin_dir / "claude.cmd").write_text(f'@"{sys.executable}" "{FAKE_CLAUDE}" %*\r\n', encoding="utf-8")
        else:
            script = bin_dir / "claude"
            script.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{FAKE_CLAUDE}" "$@"\n', encoding="utf-8")
            script.chmod(0o755)
        self.env = dict(os.environ)  # already has the test HOME and a clean cct environment
        self.env.update(
            PATH=f"{bin_dir}{os.pathsep}{self.env.get('PATH', '')}",
            FAKE_LOG=str(self.log),
            FAKE_STATUSLINE_ARGV=json.dumps([sys.executable, str(ENTRY), "statusline"]),
            PYTHONIOENCODING="utf-8",
        )
        self.env.pop("PYTHONPATH", None)  # prove the entry file works without an install

    def cct(self, *args, stdin=subprocess.DEVNULL, **env) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(ENTRY), *args],
            cwd=self.work,
            env={**self.env, **env},
            stdin=stdin,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
        )

    def starts(self) -> list:
        """One entry per time the fake claude was started."""
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines()]


@pytest.fixture
def machine(tmp_path, home) -> Env:
    return Env(tmp_path, home)
