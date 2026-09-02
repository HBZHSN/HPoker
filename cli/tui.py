"""Small dependency-free terminal UI primitives for the HPoker CLI.

The project deliberately does not require a third-party TUI framework.  This
module provides the few terminal features the controller needs: an alternate
screen, a redrawable frame, and a tiny line editor that can coexist with the
WebSocket listener.
"""

from __future__ import annotations

import asyncio
import codecs
import os
import shutil
import sys
from typing import Iterable, Optional, TextIO

from cli.text_utils import clip_display

try:  # termios is unavailable on Windows; text mode remains the fallback.
    import termios
    import tty
except ImportError:  # pragma: no cover - exercised only on Windows.
    termios = None  # type: ignore[assignment]
    tty = None  # type: ignore[assignment]


class TerminalTui:
    """Render one stable screen and read one command without scrolling output."""

    def __init__(self, input_stream: Optional[TextIO] = None, output_stream: Optional[TextIO] = None):
        self.input_stream = input_stream or sys.stdin
        self.output_stream = output_stream or sys.stdout
        self.active = False

        self._saved_terminal: Optional[list] = None
        self._input_fd: Optional[int] = None
        self._read_future: Optional[asyncio.Future[str]] = None
        self._prompt = ""
        self._input_text = ""
        self._history: list[str] = []
        self._history_index: Optional[int] = None
        self._escape_buffer = ""
        self._decoder = codecs.getincrementaldecoder("utf-8")("replace")
        self._frame = ""
        self._footer = ""

    @property
    def supported(self) -> bool:
        """Whether this process has the terminal capabilities needed by TUI."""

        try:
            return bool(self.input_stream.isatty() and self.output_stream.isatty())
        except (AttributeError, OSError):
            return False

    def enter(self) -> bool:
        """Switch to the alternate screen and enable raw input."""

        if self.active:
            return True
        if not self.supported or termios is None or tty is None:
            return False

        try:
            self._input_fd = self.input_stream.fileno()
            self._saved_terminal = termios.tcgetattr(self._input_fd)
            tty.setraw(self._input_fd)
            self.output_stream.write("\033[?1049h\033[?25l\033[2J\033[H")
            self.output_stream.flush()
        except (AttributeError, OSError, termios.error):
            self._restore_terminal()
            self._input_fd = None
            self._saved_terminal = None
            return False

        self.active = True
        return True

    def exit(self) -> None:
        """Restore the normal screen and terminal settings."""

        if self._read_future and not self._read_future.done():
            self._read_future.set_result("")
        self._read_future = None

        if self.active:
            try:
                self.output_stream.write("\033[0m\033[?25h\033[?1049l")
                self.output_stream.flush()
            except (AttributeError, OSError):
                pass
        self._restore_terminal()
        self.active = False
        self._input_fd = None
        self._saved_terminal = None
        self._escape_buffer = ""
        self._decoder = codecs.getincrementaldecoder("utf-8")("replace")

    def cancel_read(self, value: str = "") -> None:
        """Finish a pending read, useful when the room is deleted remotely."""

        if self._read_future and not self._read_future.done():
            self._read_future.set_result(value)

    @property
    def prompt(self) -> str:
        return self._prompt

    @property
    def input_text(self) -> str:
        return self._input_text

    def clear_input(self) -> None:
        self._input_text = ""

    def draw(
        self,
        frame: str,
        *,
        prompt: str = "",
        input_text: str = "",
        footer: str = "",
    ) -> None:
        """Replace the current frame while keeping input in a fixed footer."""

        self._frame = frame or ""
        self._prompt = prompt
        self._input_text = input_text
        self._footer = footer or ""
        if not self.active:
            return

        width, height = shutil.get_terminal_size((100, 30))
        width = max(40, width)
        height = max(8, height)

        footer_lines = self._footer_lines(width)
        reserved = len(footer_lines) + 2  # separator + input line
        frame_lines = self._fit_frame(self._frame.splitlines(), max(1, height - reserved))
        lines = frame_lines + ["─" * min(width, 120)] + footer_lines
        prompt_line = f"{self._prompt}{self._input_text}"
        lines.append(prompt_line)

        output_lines = []
        for row, line in enumerate(lines[:height], start=1):
            # A bare LF moves down but may keep the current column.  That is
            # why the old implementation rendered every row diagonally in
            # terminals whose ONLCR behavior differed.  Address each row by
            # absolute position so every redraw starts at column one.
            output_lines.append(f"\033[{row};1H\033[2K{self._clip(line, width)}")
        clear_from = min(len(lines), height) + 1
        output = "\033[H" + "".join(output_lines) + f"\033[{clear_from};1H\033[J"
        try:
            self.output_stream.write(output)
            self.output_stream.flush()
        except (AttributeError, OSError):
            self.exit()

    async def read_line(self, prompt: str, history: Iterable[str] = ()) -> str:
        """Read a command through the raw-mode line editor."""

        if not self.active or self._input_fd is None:
            raise RuntimeError("TUI is not active")

        loop = asyncio.get_running_loop()
        future: asyncio.Future[str] = loop.create_future()
        self._read_future = future
        self._prompt = prompt
        self._input_text = ""
        self._history = [item for item in history if item]
        self._history_index = None
        self._escape_buffer = ""
        self._draw_current()
        loop.add_reader(self._input_fd, self._on_input_ready)
        try:
            return await future
        finally:
            loop.remove_reader(self._input_fd)
            if self._read_future is future:
                self._read_future = None

    def _on_input_ready(self) -> None:
        if self._input_fd is None or not self._read_future or self._read_future.done():
            return
        try:
            raw = os.read(self._input_fd, 128)
        except OSError as exc:
            self._read_future.set_exception(exc)
            return
        if not raw:
            self._read_future.set_result("")
            return

        text = self._decoder.decode(raw)
        for char in text:
            if self._read_future is None or self._read_future.done():
                return
            self._handle_character(char)

    def _handle_character(self, char: str) -> None:
        if self._escape_buffer:
            self._escape_buffer += char
            if self._escape_buffer == "\033[":
                return
            if self._escape_buffer in {"\033[A", "\033[B"}:
                self._move_history(up=self._escape_buffer.endswith("A"))
                self._escape_buffer = ""
                return
            if len(self._escape_buffer) >= 3:
                self._escape_buffer = ""
            return

        if char == "\033":
            self._escape_buffer = char
        elif char in {"\r", "\n"}:
            self._complete_line()
        elif char in {"\x03"}:
            if self._read_future and not self._read_future.done():
                self._read_future.set_exception(KeyboardInterrupt())
        elif char in {"\x04"}:
            if self._input_text:
                self._input_text = self._input_text[:-1]
                self._draw_current()
            elif self._read_future and not self._read_future.done():
                self._read_future.set_result("")
        elif char in {"\x08", "\x7f"}:
            if self._input_text:
                self._input_text = self._input_text[:-1]
                self._draw_current()
        elif char.isprintable() or char == "\t":
            self._input_text += char
            self._history_index = None
            self._draw_current()

    def _complete_line(self) -> None:
        value = self._input_text
        if value:
            self._history.append(value)
        if self._read_future and not self._read_future.done():
            self._read_future.set_result(value)

    def _move_history(self, *, up: bool) -> None:
        if not self._history:
            return
        if self._history_index is None:
            self._history_index = len(self._history)
        if up:
            self._history_index = max(0, self._history_index - 1)
        else:
            self._history_index = min(len(self._history), self._history_index + 1)
        self._input_text = self._history[self._history_index] if self._history_index < len(self._history) else ""
        self._draw_current()

    def _draw_current(self) -> None:
        self.draw(self._frame, prompt=self._prompt, input_text=self._input_text, footer=self._footer)

    def _footer_lines(self, width: int) -> list[str]:
        lines: list[str] = []
        for raw_line in self._footer.splitlines():
            if raw_line:
                lines.append(self._clip(raw_line, width))
        return lines[-3:]

    @staticmethod
    def _fit_frame(lines: list[str], available: int) -> list[str]:
        if len(lines) <= available:
            return lines
        if available <= 1:
            return ["…"]
        if available <= 4:
            return lines[:available]
        return lines[: available - 2] + ["…（终端窗口较小，部分内容已折叠）"] + lines[-1:]

    @staticmethod
    def _clip(value: str, width: int) -> str:
        return clip_display(value, max(1, width))

    def _restore_terminal(self) -> None:
        if self._input_fd is not None and self._saved_terminal is not None:
            try:
                termios.tcsetattr(self._input_fd, termios.TCSADRAIN, self._saved_terminal)
            except (OSError, termios.error if termios is not None else OSError):
                pass
