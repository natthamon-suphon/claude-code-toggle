# Architecture

How cct is built, the data it keeps, and the facts about Claude Code that the design depends on.

Confidence tags: **[verified]** = checked in a primary source or by running code; **[inferred]** = reasoned from
evidence, not proven; **[unknown]** = must be tested (see [real-machine-testing.md](real-machine-testing.md)).

## Design decisions

| Topic | Decision | Why |
|---|---|---|
| Separating accounts | One `CLAUDE_CONFIG_DIR` per extra account. The first account uses `~/.claude` with the variable **unset**. | The official way to run Claude Code with another config folder. cct never handles credentials. |
| Moving a session | **Fast resume**: exit Claude Code, then `claude --resume <session-id>` on the other account. | The alternative, swapping credentials under a running Claude Code, needs a tool to read and write OAuth tokens. That is fragile and against the hard rules. |
| Usage numbers | From the statusline JSON that Claude Code gives to statusline scripts. | An official channel. No tokens, no network. |
| Auto-switching | Not built, on purpose. | A human confirms every switch. |
| Dashboard | Terminal table (`cct status`) and a local web page (`cct web`). | Both were requested; the page is read-only and loopback-only. |
| Runtime | Python 3.9+, standard library only. Distributed as a package and as a single-file zipapp. | Runs the same on macOS and Windows with nothing else to install. |

## Layers

```text
cli.py  →  commands/  →  services/  →  utils/
                      ↘  web/server.py (+ web/static/index.html)
```

| Module | Role |
|---|---|
| `cli.py` | Parses arguments and calls one command. `cct statusline` is handled before argparse to keep it fast. |
| `commands/accounts.py` | `add`, `link`, `list` |
| `commands/run.py` | `run`, `next`, and the exit prompt |
| `commands/status.py` | `status` (terminal table) |
| `commands/statusline.py` | `statusline` (the hook) and `install-statusline` |
| `commands/web.py` | `web` |
| `services/config.py` | Load, check and save `config.json`; look up accounts |
| `services/profiles.py` | Create profile folders; link shared items (symlink, or junction/copy on Windows) |
| `services/launcher.py` | Build the environment for an account and start `claude` |
| `services/sessions.py` | The last session per project folder |
| `services/usage.py` | Parse `rate_limits`; save usage; turn it into ok / reset / unknown views |
| `services/statusline.py` | Detect the running account; record usage and session; build the statusline command |
| `services/state.py` | Tolerant reads of state files; `error.log` |
| `utils/fs.py` | Atomic JSON writes, link detection |
| `utils/timefmt.py` | Timestamps in (seconds, milliseconds, ISO-8601), short text out |
| `utils/terminal.py` | UTF-8 and color support checks |
| `web/server.py` | The dashboard HTTP server |
| `paths.py` | Every path cct uses, worked out at call time |

## Data flow

```text
Claude Code ──stdin JSON──▶ cct statusline ──▶ ~/.cct/usage/<account>.json
   (every refresh)              │           └─▶ ~/.cct/sessions/<key>.json
                                └──stdout──▶ "[acc2] 5h 40% 7d 13%" (+ your old statusline)

cct run NAME ──env──▶ claude ... (exit) ──▶ session updated here? ──▶ ask ──▶ claude --resume <id> as next account
cct status / cct web ◀── reads ~/.cct/usage and ~/.cct/sessions
```

### Launch environment

- Extra account: `CLAUDE_CONFIG_DIR=<profile folder>`.
- First (default) account: `CLAUDE_CONFIG_DIR` is **removed** (see F2).
- Always: `CCT_ACCOUNT=<name>`, which the statusline uses to know the account (F15).
- `cct` ignores Ctrl+C while Claude Code runs, so the key goes to Claude Code.

### Account detection in the statusline

`CCT_ACCOUNT` (if it is a known name) → `CLAUDE_CONFIG_DIR` matched to a profile folder → no
`CLAUDE_CONFIG_DIR` means the default account → otherwise `unknown`. Usage for `unknown` is never saved.

### The statusline command

`install-statusline` writes `<python> <entry> statusline`, where `<entry>` is the `.pyz` file when cct runs as a
zipapp, and otherwise the package's `__main__.py` (`site-packages/cct/__main__.py` when installed,
`src/__main__.py` in a source checkout). Run by path, `__main__.py` loads the package from its own folder under
the name `cct`, so the command works for pipx, pip, a source checkout and the zipapp. `<python>` is `sys.executable` unless
its path contains spaces (then `py -3` or `python` on Windows, `python3` elsewhere). Paths use forward slashes.
Which shell Claude Code uses to run it on Windows is [unknown] (Q5).

## Files and data shapes

```jsonc
// ~/.cct/config.json
{ "accounts": [ {"name": "main", "dir": null},                    // null = ~/.claude
                {"name": "work", "dir": "/Users/you/.claude-work"} ],
  "prev_statusline": "your old statusLine command, or null" }

// ~/.cct/usage/<account>.json
{ "five_hour": {"pct": 42.0, "resets_at": 1790429406.0},
  "seven_day": {"pct": 15.0, "resets_at": 1790700000.0},
  "updated_at": 1790425406.1 }

// ~/.cct/sessions/<key>.json   key = sha256(normcase(realpath(folder)))[:16]
{ "folder": "/path/to/project", "session_id": "uuid", "account": "work", "updated_at": 1790425406.1 }
```

Account names must match `^[A-Za-z0-9_-]{1,32}$`, checked on every load, because they become file names.
All writes are atomic (write a temp file, then `os.replace`, retried on Windows `PermissionError`).

## Web page

- `ThreadingHTTPServer(("127.0.0.1", port))`. The `Host` header must be `127.0.0.1:port` or `localhost:port`,
  otherwise 403. Headers: `Cache-Control: no-store`, `X-Content-Type-Options: nosniff`, and
  `Content-Security-Policy: default-src 'none'; script-src 'nonce-…'; style-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; form-action 'none'`.
- Routes: `/` (the page) and `/api/status` (JSON). Everything else is 404. Request logging is off.
- The page polls every 10 s, redraws every 1 s for the countdowns, and builds the DOM with `textContent` only.
- The page is `web/static/index.html`, loaded with `pkgutil.get_data`, which also works inside the zipapp.

## Technical facts the design depends on

| # | Fact | Confidence / source |
|---|---|---|
| F1 | `CLAUDE_CONFIG_DIR` makes Claude Code use another config folder. Project and local settings can't set it. | [verified] https://code.claude.com/docs/en/env-vars · https://github.com/anthropics/claude-code/issues/33430 |
| F2 | Leave `CLAUDE_CONFIG_DIR` unset for the default profile. With it set, the global config moves from `$HOME/.claude.json` to `$CLAUDE_CONFIG_DIR/.claude.json`, and on macOS the Keychain service name changes, so `CLAUDE_CONFIG_DIR=~/.claude` can look logged out. | [inferred] from claude-swap source comments |
| F3 | Each `CLAUDE_CONFIG_DIR` has its own login (on macOS, its own Keychain item). | [inferred], Q3 |
| F4 | The statusline JSON has `rate_limits.five_hour` and `rate_limits.seven_day`, each with `used_percentage` and `resets_at`. | [verified] https://code.claude.com/docs/en/statusline |
| F5 | `rate_limits` is sent only to Pro/Max subscribers, and only after the first API response of a session. | [verified] community statusline projects, e.g. https://github.com/Max2535/claude-code-statusline |
| F6 | `rate_limits` has been missing in some versions. | [verified] issues #40094, #45133, #95918 |
| F7 | `resets_at` has been seen as Unix seconds and as ISO-8601 text. cct accepts both, and milliseconds. | [verified] issues #45133 (seconds), #40094 (ISO) |
| F8 | The statusline JSON also has `session_id`, `transcript_path`, `cwd` and `workspace`. cct prefers `workspace.project_dir`. | [verified] key list in #40094 · [inferred] for `project_dir` |
| F9 | `claude --resume <id>` resumes a session by ID; `claude -c/--continue` resumes the most recent one. | [verified] `claude --help` (2.1.283) |
| F10 | `--continue` finds "most recent" through per-config-folder history, so cct always uses `--resume <id>`. | [inferred] issue #10063 |
| F11 | With `projects/` shared, another account can `--resume` the same session. | [inferred], Q4 |
| F12 | If `ANTHROPIC_API_KEY` is set, Claude Code uses it instead of the subscription. | [verified] https://support.claude.com/en/articles/11145838-use-claude-code-with-your-pro-or-max-plan |
| F13 | Usage limits are a 5-hour window plus a weekly window, shared by claude.ai, Claude Code and Claude Desktop. | [verified] https://support.claude.com/en/articles/11647753-how-do-usage-and-length-limits-work |
| F14 | The first message after switching accounts may use more usage, because the prompt cache starts empty. | [inferred] |
| F15 | The statusline process inherits Claude Code's environment, so `CCT_ACCOUNT` reaches it. | [verified] in the sense that `CLAUDECODE` is set for it (env-vars docs) · [inferred] for `CCT_ACCOUNT`, Q2 |
| F16 | `claude auth status` exists and shows the signed-in account. | [verified] `claude auth --help` (2.1.283) |

Claude Code issues referenced: [#10063](https://github.com/anthropics/claude-code/issues/10063),
[#33430](https://github.com/anthropics/claude-code/issues/33430),
[#40094](https://github.com/anthropics/claude-code/issues/40094),
[#45133](https://github.com/anthropics/claude-code/issues/45133),
[#91920](https://github.com/anthropics/claude-code/issues/91920) (per-model weekly limit not in the statusline),
[#95918](https://github.com/anthropics/claude-code/issues/95918).
