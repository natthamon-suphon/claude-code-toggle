"""cct: switch Claude Code accounts, resume a session on another account, see usage.

Each extra account gets its own CLAUDE_CONFIG_DIR. Sessions, settings,
CLAUDE.md, skills, commands and agents are shared by linking them to ~/.claude.
Usage numbers come from the statusline data that Claude Code itself passes to
statusline scripts. This tool never reads, copies or sends OAuth tokens.
"""

__version__ = "0.1.1"
