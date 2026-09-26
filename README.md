# cct: Claude Code Toggle

[![CI](https://github.com/natthamon-suphon/claude-code-toggle/actions/workflows/ci.yml/badge.svg)](https://github.com/natthamon-suphon/claude-code-toggle/actions/workflows/ci.yml)
![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue)
![Dependencies: none](https://img.shields.io/badge/dependencies-none-brightgreen)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

Use more than one Claude Code account on the same computer. Switch accounts, move a session to another
account without losing the conversation, and see each account's usage in the terminal or on a local web page.

> [!NOTE]
> cct is an unofficial community tool. Anthropic does not make, endorse or support it.
> "Claude" and "Claude Code" are trademarks of Anthropic.

- **It never touches your login.** cct does not read, copy, store or send OAuth tokens, `.credentials.json`
  or Keychain items. It never calls Anthropic's OAuth endpoints. Usage numbers come from the data Claude Code
  itself gives to statusline scripts.
- **You stay in control.** cct never switches accounts on its own. You confirm every switch.
- **Nothing extra to install.** It uses the Python standard library only, and runs on macOS, Linux and Windows.

```text
$ cct status
Account    5 hours                        Weekly                         Last seen
main       ███████████░   91%  1h 12m     █████░░░░░░░   38%  Fri 09:00  just now
work       ███░░░░░░░░░   24%  3h 40m     ██░░░░░░░░░░   15%  Sat 14:00  2h ago
personal   not seen yet                   not seen yet                   never

Counts Claude Code on this computer only. claude.ai and your other computers aren't included.
```

## Contents

- [How it works](#how-it-works)
- [Requirements](#requirements)
- [Install](#install)
- [Set up your accounts](#set-up-your-accounts)
- [Daily use](#daily-use)
- [Commands](#commands)
- [What is shared between accounts](#what-is-shared-between-accounts)
- [Files cct writes](#files-cct-writes)
- [Security and privacy](#security-and-privacy)
- [Known limits](#known-limits)
- [Terms of service](#terms-of-service)
- [Project status](#project-status)
- [Development](#development)
- [License](#license)

## How it works

1. **One config folder per account.** `CLAUDE_CONFIG_DIR` tells Claude Code which config folder to use
   ([docs](https://code.claude.com/docs/en/env-vars)), and each folder signs in separately. cct gives each extra
   account its own folder, `~/.claude-NAME`. Your first account keeps using `~/.claude`.
2. **Shared work.** Inside each extra folder, cct links sessions, settings, `CLAUDE.md`, skills, commands and
   agents back to `~/.claude`. Every account sees the same sessions and setup.
3. **Usage from the statusline.** Claude Code sends JSON to statusline scripts, including `rate_limits` for
   Pro and Max plans ([docs](https://code.claude.com/docs/en/statusline)). `cct install-statusline` makes cct
   your statusline. Each time it runs, it saves the usage numbers and the current session ID.
4. **Moving a session.** When you leave Claude Code, cct asks if you want to continue on another account. If you
   say yes, it starts `claude --resume <session-id>` on that account. It is the same conversation, just a
   different login.

## Requirements

- [Claude Code](https://code.claude.com/docs), with `claude` on your `PATH`.
- Python 3.9 or newer.
- macOS, Linux or Windows. On Windows, turn on **Developer Mode** (Settings → System → For developers) before you
  add accounts. Without it, Windows can't make symlinks, so cct links folders with junctions and copies files
  instead.

## Install

**Option A: pipx (recommended).** This puts a `cct` command on your `PATH`:

```bash
pipx install git+https://github.com/natthamon-suphon/claude-code-toggle
```

**Option B: one file, nothing to install.** Build `cct.pyz` from a clone, then run it with any Python 3.9+:

```bash
git clone https://github.com/natthamon-suphon/claude-code-toggle
cd claude-code-toggle
python3 scripts/build_zipapp.py            # writes dist/cct.pyz
mkdir -p ~/.cct && cp dist/cct.pyz ~/.cct/
echo "alias cct='python3 ~/.cct/cct.pyz'" >> ~/.zshrc   # or ~/.bashrc
```

On Windows (PowerShell), copy `cct.pyz` to `$HOME\.cct\`, run `notepad $PROFILE`, and add:

```powershell
function cct { py -3 "$HOME\.cct\cct.pyz" @args }
```

**Option C: pip.** `pip install git+https://github.com/natthamon-suphon/claude-code-toggle` into a virtual
environment you keep. The statusline runs cct with that environment's Python, so don't delete it.

Check the install with `cct --version`.

## Set up your accounts

Your current login in `~/.claude` becomes the first account, `main`.

```bash
cct add work              # creates ~/.claude-work and links the shared items
cct run work              # starts Claude Code as "work"; type /login and sign in with that account
cct install-statusline    # once per computer
```

Then restart Claude Code and send one message. `cct status` now shows numbers for that account.

If you already have a separate config folder, adopt it with `cct add work --dir ~/.claude-old`.

`install-statusline` keeps a statusline you already had. It shows your old line under cct's line. It makes a
timestamped backup of every `settings.json` it changes, and it is safe to run again (for example, after you
move cct or upgrade Python).

## Daily use

```bash
cd my-project
cct run                   # start Claude Code as the first account (or: cct run work)
```

When you want to continue on another account:

1. Type `/exit` in Claude Code.
2. cct shows the usage of both accounts and asks
   `Resume this session on 'work' (5h 24%, 7d 15%)? [y / N / account name]`.
3. Answer `y`, or type an account name. The same session opens on that account.

You can also do this later, from the same folder: `cct next` (the next account in the list) or `cct next work`.
Close the old Claude Code window first, so two accounts don't write to the same session.

## Commands

| Command | What it does |
|---|---|
| `cct add NAME [--dir PATH]` | Create `~/.claude-NAME` (or adopt `PATH`) and link the shared items. It never overwrites a file. |
| `cct list` | Show accounts, their folders, and whether all shared items are linked. |
| `cct link NAME` | Create missing links again for one account. |
| `cct run [NAME] [--no-ask] [-- ARGS]` | Start Claude Code as an account. Anything after `--` goes to `claude`. When Claude Code exits, cct offers to move the session (only in an interactive terminal). |
| `cct next [NAME]` | Resume this folder's last session on the next account, or on `NAME`. |
| `cct status` | Usage table: 5-hour and weekly windows, reset times, when each account was last seen. |
| `cct web [--port 8765] [--no-open]` | The same data as a web page on `http://127.0.0.1:8765`, for this computer only. |
| `cct install-statusline` | Make cct the statusline in every account's `settings.json`. |
| `cct --version` | Print the version. |

Exit codes: `0` success, `1` a problem you can fix (the message says what), `2` wrong command-line usage.
`cct run` returns Claude Code's own exit code.

## What is shared between accounts

| Shared (linked to `~/.claude`) | Separate for each account |
|---|---|
| `projects/` (sessions), `settings.json`, `CLAUDE.md`, `skills/`, `commands/`, `agents/` | The login, and everything else Claude Code keeps in the config folder |

cct only links an item that exists in `~/.claude` (it always creates `projects/`, because sessions must be
shared). It never replaces a file or folder that is already there: it prints `SKIPPED` and leaves it alone.
`cct list` tells you what is not shared yet.

## Files cct writes

| Path | Content |
|---|---|
| `~/.cct/config.json` | Your account list, and the statusline you had before cct |
| `~/.cct/usage/NAME.json` | The last usage numbers seen for each account |
| `~/.cct/sessions/*.json` | The last session in each project folder (folder path, session ID, account) |
| `~/.cct/error.log` | Statusline errors. The statusline must never print a traceback into Claude Code |
| `~/.claude-NAME/` | The config folder of each extra account |
| `settings.json.cct-backup-*` | Backups made by `cct install-statusline` |

Set `CCT_HOME` to keep cct's own files somewhere other than `~/.cct`. cct stores no passwords, tokens or keys.

## Security and privacy

- cct never reads, copies, stores, refreshes or sends OAuth tokens, `.credentials.json` or Keychain items.
- cct never calls `api.anthropic.com/api/oauth/*` or any other OAuth endpoint. It makes no network requests.
- The only data sources are local files and the JSON that Claude Code sends to the statusline.
- `cct web` listens on `127.0.0.1` only, so other devices can't reach it. It refuses requests whose `Host`
  header isn't `127.0.0.1` or `localhost` (this blocks DNS rebinding). It is read-only and sends a strict
  Content Security Policy.
- If `ANTHROPIC_API_KEY` is set, Claude Code may use that key instead of your subscription. `cct run` warns you.

To report a security problem, see [SECURITY.md](SECURITY.md).

## Known limits

- **This computer only.** Usage limits are shared by claude.ai, Claude Code and Claude Desktop, but cct only sees
  Claude Code on this computer. Use elsewhere doesn't show up.
- **Numbers appear after the first reply.** Claude Code sends `rate_limits` only after the first API response
  of a session. An account you haven't used lately shows old numbers until its reset time, then "refilled".
- **If Claude Code stops sending `rate_limits`,** the numbers show `-`. This has happened in some versions.
  cct does not fall back to calling usage APIs with your tokens, by design.
- **Only the 5-hour and weekly windows.** Per-model weekly limits aren't in the statusline data.
- **Sessions stay on one computer.** `projects/` is not synced between machines.
- **Close the old window first.** Two Claude Code processes writing the same session can damage it.
- **The first message after a switch may cost more,** because the prompt cache starts empty on the new account.

## Terms of service

Using Claude Code is subject to Anthropic's
[Consumer Terms](https://www.anthropic.com/legal/consumer-terms) (or your organization's agreement) and the
[Usage Policy](https://www.anthropic.com/legal/aup). Read them before you use cct. In particular:

- Every account you add must be your own. Don't share accounts or logins with other people.
- Using more than one account to get around usage limits may not be allowed. cct can't decide this for you.
- Claude Code's [legal and compliance page](https://code.claude.com/docs/en/legal-and-compliance) says
  subscription OAuth tokens may only be used by Claude Code and Claude.ai. This is why cct never touches them.

cct is provided "as is", without warranty (see the [license](LICENSE)).

## Project status

Version 0.1.0, alpha. CI runs the full test suite on Linux, macOS and Windows with Python 3.9 to 3.13, using a
fake `claude`. Some behavior still needs checking against a real Claude Code install, mostly on Windows. The
list is in [docs/real-machine-testing.md](docs/real-machine-testing.md). Results from your machine are welcome:
please open an issue.

## Development

```bash
git clone https://github.com/natthamon-suphon/claude-code-toggle
cd claude-code-toggle
python3 -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -e ".[dev]"                 # needed before the tests: it maps src/ to the package `cct`

pytest                                  # all tests, about 15 seconds
pytest --cov                            # with coverage
ruff check . && ruff format --check src tests scripts
python scripts/build_zipapp.py          # dist/cct.pyz
```

```text
src/                  the package `cct` (pyproject maps src/ to `cct`; there is no src/cct/ folder)
├── __main__.py       entry for `python -m cct` and for the statusline command
├── cli.py            argument parsing; hands off to a command
├── config.py         load and save ~/.cct/config.json; look up accounts
├── commands/         one module per command group; prints output, returns an exit code
├── services/         the logic: profiles, launcher, sessions, usage, statusline
├── schema/           the shape of every JSON file cct reads or writes, and its checks
├── utils/            generic helpers: JSON files and links, time text, terminal checks
└── web/              the local dashboard server and its page (static/index.html)
tests/
├── unit/             config, schema, services and utils
├── commands/         each command, the CLI and the web server
└── e2e/              cct as a real process with a fake `claude`, and the zipapp build
```

More detail: [docs/architecture.md](docs/architecture.md). How to contribute: [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE)
