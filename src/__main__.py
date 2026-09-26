"""Entry point for `python -m cct`, and for the statusline command.

settings.json runs this file by its path (`python .../__main__.py statusline`), so
it must also work when the package is not installed. In the repository the package
folder is `src/`, not `cct/`, so the folder name can't be used to import it.
"""

import os
import sys

if not __package__:
    # Run as a plain file. Load the package from this file's own folder under the
    # name `cct`, so the entry always runs the code next to it.
    import importlib.util

    _package_dir = os.path.dirname(os.path.abspath(__file__))
    # Python put this folder first on sys.path (not with -P or PYTHONSAFEPATH).
    # Drop it, so modules like `utils` or `web` in here can't shadow other imports.
    if sys.path and os.path.abspath(sys.path[0] or os.curdir) == _package_dir:
        del sys.path[0]
    if "cct" not in sys.modules:
        _spec = importlib.util.spec_from_file_location(
            "cct", os.path.join(_package_dir, "__init__.py"), submodule_search_locations=[_package_dir]
        )
        _module = importlib.util.module_from_spec(_spec)
        sys.modules["cct"] = _module
        _spec.loader.exec_module(_module)

from cct.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
