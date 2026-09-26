# Contributing

Thanks for helping. Bug reports, test results from real machines, and small focused pull requests are all welcome.

## Before you start

Read the **hard rules** in [CLAUDE.md](CLAUDE.md#hard-rules-never-break-these). Pull requests that read OAuth
tokens or credentials, call OAuth or usage endpoints, switch accounts automatically, or open the dashboard to the
network will not be accepted, however useful they are.

## Set up

```bash
git clone https://github.com/natthamon-suphon/claude-code-toggle
cd claude-code-toggle
python3 -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## Checks

Run these before you open a pull request. CI runs the same on Linux, macOS and Windows with Python 3.9 to 3.13.

```bash
pytest
ruff check .
ruff format --check src tests scripts    # or `ruff format src tests scripts` to fix
```

## Guidelines

- Runtime code uses the Python standard library only and must work on Python 3.9.
- Keep the layers: `cli` → `commands` (print, return exit codes) → `services` (logic, no printing) → `utils`.
- Add or update tests for every behavior change. Tests get their own fake `HOME` automatically; never write to a
  real `~/.claude` or `~/.cct`.
- The statusline hook must never crash. New code on that path handles bad input by logging it.
- Keep pull requests small and about one thing. Describe what you changed and how you tested it.
- Add a line to the `Unreleased` section of [CHANGELOG.md](CHANGELOG.md).

## Reporting real-machine results

Some behavior can only be checked with a real Claude Code install. The list is in
[docs/real-machine-testing.md](docs/real-machine-testing.md). If you test an item, open an issue with:

- the question number (for example Q5),
- your OS and version, Python version (`python3 --version`), Claude Code version (`claude --version`) and
  `cct --version`,
- what you ran and what you saw.

Please remove anything private (emails, tokens, file paths with your name) before posting.

## Security problems

Don't open a public issue. See [SECURITY.md](SECURITY.md).
