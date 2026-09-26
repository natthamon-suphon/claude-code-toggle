# Security policy

## Reporting a vulnerability

Please report security problems privately, not in a public issue. Use the **Report a vulnerability** button
on this repository's **Security** tab (GitHub private vulnerability reporting).

Include what you found, how to reproduce it, and which version (`cct --version`) and OS you used.

## Supported versions

Only the latest release gets security fixes.

## Security model

What cct promises, and what counts as a vulnerability if it is broken:

| cct never... | How it is kept |
|---|---|
| reads, copies, stores, refreshes or sends OAuth tokens, `.credentials.json` or Keychain items | No code touches these files or the Keychain. Accounts are separated only by `CLAUDE_CONFIG_DIR`. |
| makes network requests | No HTTP client code. Usage comes from the JSON Claude Code sends to the statusline on stdin. |
| exposes data to other devices | `cct web` binds to `127.0.0.1` only. |
| lets other websites read the dashboard | The `Host` header must be `127.0.0.1:PORT` or `localhost:PORT` (blocks DNS rebinding). Responses use `Cache-Control: no-store`, `X-Content-Type-Options: nosniff` and a strict Content Security Policy with a per-start script nonce. |
| lets the dashboard change anything | Only `GET` is handled. There are no write endpoints. |
| overwrites your files | `cct add` and `cct link` skip anything that already exists. `cct install-statusline` backs up each `settings.json` before it changes it. |

What cct stores in `~/.cct`: account names, config folder paths, usage percentages, reset times, project folder
paths and session IDs. No passwords, tokens or keys.

## Out of scope

- Anyone who can already run code as your user, or read your home folder.
- Claude Code itself. Report those issues to Anthropic.
- Whether a particular way of using several accounts fits Anthropic's terms (see the README's
  "Terms of service" section).
