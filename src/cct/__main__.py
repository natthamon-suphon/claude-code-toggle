"""Entry point for `python -m cct`, and for the statusline command.

settings.json runs this file by its path (`python .../cct/__main__.py statusline`),
so it must also work when the package is not installed.
"""

import os
import sys

if not __package__:
    # Run as a plain file: make the folder that holds the package importable. Python
    # normally puts the package folder itself first on sys.path (not with -P or
    # PYTHONSAFEPATH); replace it, so modules inside cct can't shadow the standard library.
    _package_dir = os.path.dirname(os.path.abspath(__file__))
    if sys.path and os.path.abspath(sys.path[0] or os.curdir) == _package_dir:
        sys.path[0] = os.path.dirname(_package_dir)
    else:
        sys.path.insert(0, os.path.dirname(_package_dir))

from cct.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
