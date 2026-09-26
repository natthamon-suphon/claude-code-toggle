"""The single-file build (cct.pyz) must behave like the package."""

from __future__ import annotations

import json
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from cct import __version__

pytestmark = pytest.mark.e2e

BUILD_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "build_zipapp.py"


@pytest.fixture(scope="module")
def pyz(tmp_path_factory):
    output = tmp_path_factory.mktemp("dist") / "cct.pyz"
    subprocess.run([sys.executable, str(BUILD_SCRIPT), "--output", str(output)], check=True, timeout=60)
    return output


def run_pyz(pyz, machine, *args, stdin=None):
    return subprocess.run(
        [sys.executable, str(pyz), *args],
        input=stdin,
        env=machine.env,
        cwd=machine.work,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )


def test_archive_contents(pyz):
    names = zipfile.ZipFile(pyz).namelist()
    assert "__main__.py" in names
    assert "cct/cli.py" in names
    assert "cct/web/static/index.html" in names
    assert not [n for n in names if "__pycache__" in n or n.endswith(".pyc")]


def test_pyz_version(pyz, machine):
    result = run_pyz(pyz, machine, "--version")
    assert result.returncode == 0
    assert result.stdout.strip() == f"cct {__version__}"


def test_pyz_keeps_exit_codes(pyz, machine):
    assert run_pyz(pyz, machine, "link", "nobody").returncode == 1


def test_pyz_installs_itself_as_the_statusline(pyz, machine):
    assert run_pyz(pyz, machine, "install-statusline").returncode == 0
    settings = json.loads((machine.home / ".claude" / "settings.json").read_text(encoding="utf-8"))
    command = settings["statusLine"]["command"]
    assert command.endswith(f"{pyz.resolve().as_posix()} statusline")
    payload = json.dumps({"rate_limits": {"five_hour": {"used_percentage": 33}}})
    assert run_pyz(pyz, machine, "statusline", stdin=payload).stdout.strip() == "[main] 5h 33% 7d -"


def test_pyz_serves_the_dashboard_page(pyz, machine):
    code = "from cct.web.server import load_page; print(len(load_page('n')) > 1000)"
    result = subprocess.run(
        [sys.executable, "-c", f"import sys; sys.path.insert(0, {str(pyz)!r}); {code}"],
        env=machine.env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.stdout.strip() == "True", result.stderr
