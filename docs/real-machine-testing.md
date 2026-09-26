# Real-machine testing

The automated tests use a fake `claude`. These questions need a real Claude Code install and real accounts.
Test them in order. When one is answered, change its status and write down the result, the date, the OS and the
Claude Code version.

Status: **[unknown]** = not tested yet · **[verified]** = tested, result below · **[broken]** = needs a fix.

| # | Question | How to check | Status |
|---|---|---|---|
| Q1 | Does the current Claude Code still send `rate_limits` to statusline scripts? | `cct install-statusline`, then `cct run`, send "hi", and look at `~/.cct/usage/main.json`. If it's missing, look at `~/.cct/error.log`. To see the raw keys, set the statusLine command for one test to `python3 -c "import json,sys;print(sorted(json.load(sys.stdin)))"`. | [unknown] |
| Q2 | Does `CCT_ACCOUNT` reach the statusline process? | `cct run work`: the status bar should say `[work]`, not `[unknown]`. | [unknown] |
| Q3 | Does each profile keep its own login (macOS Keychain, Windows file)? | Run `claude auth status` in plain `claude`, and with `CLAUDE_CONFIG_DIR=~/.claude-work claude auth status`. The emails must differ. (`claude auth status` exists: [verified] with `claude auth --help`, 2.1.283.) | [unknown] |
| Q4 | Does `--resume <id>` work under another account with a shared `projects/`? | `cct run`, send a message, `/exit`, answer `y`. The earlier messages must be visible on the new account. Also note whether MCP servers and `/rewind` checkpoints still work after the switch. | [unknown] |
| Q5 | Windows: which shell runs the statusline command, and does `C:/…/python.exe C:/…/cct/__main__.py statusline` (or `py -3 …`) work in it? | After `cct install-statusline`, check that cct's line shows in Claude Code. If not, check `error.log`, and try the exact command from `settings.json` in PowerShell, cmd and Git Bash. | [unknown] |
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

No results yet.
