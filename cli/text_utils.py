"""Terminal display-width helpers shared by the renderer and TUI."""

from __future__ import annotations

import re
import unicodedata


ANSI_ESCAPE_RE = re.compile(r"\033\[[0-?]*[ -/]*[@-~]")
_ZERO_WIDTH_CHARS = {"\u200b", "\u200d", "\ufe0e", "\ufe0f"}


def char_display_width(char: str) -> int:
    """Return the number of terminal columns occupied by one character."""

    if char in _ZERO_WIDTH_CHARS or unicodedata.combining(char):
        return 0
    if unicodedata.category(char).startswith("C"):
        return 0
    return 2 if unicodedata.east_asian_width(char) in {"W", "F"} else 1


def display_width(text: str) -> int:
    """Measure visible terminal columns, ignoring ANSI color sequences."""

    visible = ANSI_ESCAPE_RE.sub("", str(text))
    return sum(char_display_width(char) for char in visible)


def clip_display(text: str, width: int) -> str:
    """Clip text to terminal columns while preserving useful ANSI styling."""

    if width <= 0:
        return ""

    pieces: list[str] = []
    used = 0
    clipped = False
    for token in re.split(r"(\033\[[0-?]*[ -/]*[@-~])", str(text)):
        if not token:
            continue
        if ANSI_ESCAPE_RE.fullmatch(token):
            pieces.append(token)
            continue
        for char in token:
            char_width = char_display_width(char)
            if used + char_width > width:
                clipped = True
                break
            pieces.append(char)
            used += char_width
        if clipped:
            break

    if clipped and ANSI_ESCAPE_RE.search(str(text)):
        pieces.append("\033[0m")
    return "".join(pieces)


def pad_display(text: str, width: int) -> str:
    """Left-align text to an exact visible terminal width."""

    clipped = clip_display(str(text), width)
    return clipped + " " * max(0, width - display_width(clipped))
