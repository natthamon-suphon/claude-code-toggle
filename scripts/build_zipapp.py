#!/usr/bin/env python3
"""Build dist/cct.pyz: all of cct in one file that any Python 3.9+ can run.

Usage: python scripts/build_zipapp.py [--output PATH], then python dist/cct.pyz --version
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
import zipapp
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "src" / "cct"

# zipapp's own generated __main__ drops main()'s return value, so exit codes would be lost.
MAIN = "import sys\nfrom cct.cli import main\nsys.exit(main())\n"


def build(output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        stage = Path(tmp)
        shutil.copytree(PACKAGE, stage / "cct", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        (stage / "__main__.py").write_text(MAIN, encoding="utf-8")
        zipapp.create_archive(stage, target=output, interpreter="/usr/bin/env python3", compressed=True)
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", type=Path, default=ROOT / "dist" / "cct.pyz")
    args = parser.parse_args()
    print(f"built {build(args.output)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
