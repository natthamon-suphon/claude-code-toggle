# Changelog

All notable changes to this project are listed here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/).

## [Unreleased]

First public version, planned as 0.1.0. Before this, cct was a single file, `cct.py`.

### Added

- Installable package (`src/cct`) with a `cct` command, `python -m cct`, and `cct --version`.
- `scripts/build_zipapp.py` builds `dist/cct.pyz`, a single file that runs with any Python 3.9+.
- Test suite (unit, command, web server and end-to-end tests with a fake `claude`), and CI on Linux, macOS and
  Windows with Python 3.9 to 3.13.
- README, CLAUDE.md, CONTRIBUTING, SECURITY, MIT license, and docs for the architecture and for real-machine
  testing.

### Changed

- The statusline command in `settings.json` now runs `cct/__main__.py` (or `cct.pyz`) instead of `cct.py`.
  Run `cct install-statusline` once after upgrading: it recognizes the old `cct.py` command and replaces it.
  Your data in `~/.cct` is kept as it is.

### Fixed

- The statusline no longer crashes with a traceback when a usage or session file in `~/.cct` is damaged or
  hand-edited; the damaged file counts as "no data" and is logged.
- A `~/.cct/config.json` that is valid JSON but not an object (for example `[]`) now gives a clear error instead
  of a traceback.
- `cct install-statusline` no longer loses your previous statusline command when a later `settings.json` is
  invalid JSON.
