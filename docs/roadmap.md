# Roadmap

Planned work, in priority order. Nothing here may break the hard rules in [CLAUDE.md](../CLAUDE.md).

## Next

1. **Fix what the real-machine tests find** ([real-machine-testing.md](real-machine-testing.md)). Keep fixes small.
2. **`cct doctor`**: check the Python version; that `claude` is on `PATH` and its version; that the statusline is
   installed in every distinct `settings.json`; link health; whether `ANTHROPIC_API_KEY` is set; the time of the
   last good statusline write; the last 5 lines of `error.log`.
3. **`CCT_DEBUG=1`**: save the key names and the `rate_limits` object of the last statusline payload to
   `~/.cct/last-statusline.json`, to help with Q1. Never store the full payload.

## Later

- `cct rename OLD NEW`: update the config and move `usage/OLD.json`.
- Handle `BrokenPipeError` when output is piped (`cct install-statusline | head` shows a traceback today).
- `cct status --json`.
- Windows: turn on console ANSI colors with `SetConsoleMode` instead of relying on `WT_SESSION`.
- Windows: `cct web` inherits `SO_REUSEADDR` from `http.server`, which on Windows lets two programs share a port.
  Consider `SO_EXCLUSIVEADDRUSE`. [inferred, not tested]
- An ISO `resets_at` without a time zone is read as local time. Claude Code has not been seen sending one.
  [inferred]

## Won't do

These break the hard rules, so they won't be accepted:

- Automatic account switching, or any code that picks and switches accounts without a human.
- Reading `.credentials.json` or the Keychain, or refreshing tokens.
- Calling `api/oauth/usage`, `api/oauth/profile` or any other OAuth endpoint.
- Binding the dashboard to anything but `127.0.0.1`, remote access, or write actions in the web API.
- Syncing credentials between computers.
