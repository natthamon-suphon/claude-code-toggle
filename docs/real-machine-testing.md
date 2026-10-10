# Real-machine testing

The automated tests use a fake `claude`. These questions need a real Claude Code install and real accounts.
Test them in order. When one is answered, change its status and write down the result, the date, the OS and the
Claude Code version.

Status: **[unknown]** = not tested yet · **[verified]** = tested, result below · **[broken]** = needs a fix.

| # | Question | How to check | Status |
|---|---|---|---|
| Q1 | Does the current Claude Code still send `rate_limits` to statusline scripts? | `cct install-statusline`, then `cct run`, send "hi", and look at `~/.cct/usage/main.json`. If it's missing, look at `~/.cct/error.log`. To see the raw keys, set the statusLine command for one test to `python3 -c "import json,sys;print(sorted(json.load(sys.stdin)))"`. | [verified] |
| Q2 | Does `CCT_ACCOUNT` reach the statusline process? | `cct run work`: the status bar should say `[work]`, not `[unknown]`. | [unknown] |
| Q3 | Does each profile keep its own login (macOS Keychain, Windows file)? | Run `claude auth status` in plain `claude`, and with `CLAUDE_CONFIG_DIR=~/.claude-work claude auth status`. The emails must differ. (`claude auth status` exists: [verified] with `claude auth --help`, 2.1.283.) | [verified] |
| Q4 | Does `--resume <id>` work under another account with a shared `projects/`? | `cct run`, send a message, `/exit`, answer `y`. The earlier messages must be visible on the new account. Also note whether MCP servers and `/rewind` checkpoints still work after the switch. | [verified] |
| Q5 | Windows: which shell runs the statusline command, and does `C:/…/python.exe C:/…/__main__.py statusline` (or `py -3 …`) work in it? | After `cct install-statusline`, check that cct's line shows in Claude Code. If not, check `error.log`, and try the exact command from `settings.json` in PowerShell, cmd and Git Bash. | [unknown] |
| Q6 | Windows: does `cct run` work with both `claude.exe` (native) and `claude.cmd` (npm)? | `cct run`, and `where claude`. | [unknown] |
| Q7 | Windows links, with and without Developer Mode. | `cct add test`, then `cct list`. Check that the `projects` junction works. | [unknown] |
| Q8 | When Claude Code saves user settings (for example through `/config`), does it replace a linked `settings.json` with a normal file? | Change a setting inside `cct run work`, then run `cct list`. | [unknown] |
| Q9 | Windows: do Ctrl+C and Esc inside Claude Code still work under `cct run`, and does the exit prompt show? | Manual test. | [unknown] |
| Q10 | The statusline command stores the absolute Python path. Does it break when Homebrew Python (or the pipx venv) is upgraded or moved? | After an upgrade, check the status bar. The fix is to run `cct install-statusline` again (it is safe to repeat). | [unknown] |

## Results

<!-- Add one entry per test, newest first. Example:
### Q2 — [verified] — 2026-10-01, macOS 15.1, Claude Code 2.1.290, cct 0.1.0
`cct run work` showed `[work] 5h 12% 7d 3%`.
-->

### Q8 — [unknown], partly tested — 2026-10-10, macOS 27.0.1, Claude Code 2.1.296, cct 0.1.1

`claude plugin install` run with the second account's `CLAUDE_CONFIG_DIR` wrote the shared `settings.json`
through the link (only the final newline changed), and the link stayed a link. Saving a setting through `/config`
is not tested yet.

### Q4 — [verified] — 2026-10-10, macOS 27.0.1, Claude Code 2.1.296, cct 0.1.1

A session started on the first account. After `/exit`, cct resumed it on the second account with the same session
ID. All earlier messages were there, and a stdio MCP server worked after the switch.

Not shared between accounts, found in the same test:

- `/rewind` checkpoints: `file-history/` is kept in each config folder, so checkpoints made before the switch stay
  in the first account's folder. [inferred] `/rewind` to a point before the switch can't restore those files. Not
  tried.
- Plugins: `enabledPlugins` is in the shared `settings.json`, but each folder has its own
  `plugins/installed_plugins.json`. Install each plugin once per account:
  `CLAUDE_CONFIG_DIR=~/.claude-work claude plugin install NAME@MARKETPLACE`.
- User-scope MCP servers: they are in each folder's `.claude.json`. Add them once per account:
  `CLAUDE_CONFIG_DIR=~/.claude-work claude mcp add -s user ...`.
- claude.ai connectors and plugins synced from claude.ai follow the account that is logged in.

### Q3 — [verified] — 2026-10-10, macOS 27.0.1, Claude Code 2.1.296, cct 0.1.1

`claude auth status` without `CLAUDE_CONFIG_DIR` and with `CLAUDE_CONFIG_DIR=~/.claude-work`: both are logged in
with claude.ai, and the emails differ (one Team plan, one Pro plan). Logging in to the second account did not log
out the first.

### Q1 — [verified] — 2026-10-10, macOS 27.0.1, Claude Code 2.1.296, cct 0.1.1

After `cct install-statusline` and one message on each account, `~/.cct/usage/main.json` and the second account's
file had `five_hour` and `seven_day`, and `cct status` showed the numbers. There was no `~/.cct/error.log`. Both a
Team plan and a Pro plan sent `rate_limits`. On this machine `ANTHROPIC_BASE_URL` pointed at a local
pass-through proxy.
