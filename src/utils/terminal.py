"""What the terminal can draw."""

from __future__ import annotations

import os

from cct.utils import system


def supports_utf8(stream) -> bool:
    return (getattr(stream, "encoding", None) or "").lower().startswith("utf")


def supports_color(stream) -> bool:
    """ANSI color only on a TTY, when NO_COLOR is unset, and not in the old Windows console."""
    return bool(
        stream.isatty()
        and not os.environ.get("NO_COLOR")
        and (not system.IS_WINDOWS or os.environ.get("WT_SESSION"))  # Windows Terminal speaks ANSI
    )
