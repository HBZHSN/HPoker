"""Textual application shell for HPoker's interactive terminal client.

The controller remains the single owner of poker/network state.  This module
adapts its small ``TerminalTui`` contract to Textual widgets, so layout,
focus, resizing, and keyboard events are handled by a mature TUI framework.
"""

from __future__ import annotations

import asyncio
from typing import Iterable, Optional

from rich.text import Text
from textual import events, on
from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import Input, Static


class TextualTuiBridge:
    """Expose controller-friendly input/draw methods backed by Textual."""

    framework = "textual"

    def __init__(self, app: "PokerTextualApp") -> None:
        self.app = app
        self.active = False
        self._prompt = ""
        self._input_text = ""
        self._history: list[str] = []
        self._history_index: Optional[int] = None
        self._read_future: Optional[asyncio.Future[str]] = None
        self._eof_requested = False

    @property
    def supported(self) -> bool:
        return True

    @property
    def prompt(self) -> str:
        return self._prompt

    @property
    def input_text(self) -> str:
        try:
            return self.app.query_one("#command-input", Input).value
        except Exception:
            return self._input_text

    @property
    def eof_requested(self) -> bool:
        return self._eof_requested

    def enter(self) -> bool:
        self.active = True
        return True

    def exit(self) -> None:
        self.cancel_read("")
        self.active = False

    def cancel_read(self, value: str = "") -> None:
        if self._read_future and not self._read_future.done():
            self._read_future.set_result(value)

    def clear_input(self) -> None:
        self._input_text = ""
        try:
            self.app.query_one("#command-input", Input).value = ""
        except Exception:
            pass

    def draw(
        self,
        frame: str,
        *,
        prompt: str = "",
        input_text: str = "",
        footer: str = "",
    ) -> None:
        self._prompt = prompt
        self._input_text = input_text
        if self.active:
            self.app.update_dashboard(frame, prompt=prompt, notice=footer)

    async def read_line(self, prompt: str, history: Iterable[str] = ()) -> str:
        if not self.active:
            raise RuntimeError("Textual TUI is not active")
        loop = asyncio.get_running_loop()
        self._eof_requested = False
        self._prompt = prompt
        self._history = [item for item in history if item]
        self._history_index = None
        self.clear_input()
        future: asyncio.Future[str] = loop.create_future()
        self._read_future = future
        self.app.set_prompt(prompt)
        self.app.query_one("#command-input", Input).focus()
        try:
            return await future
        finally:
            if self._read_future is future:
                self._read_future = None

    def submit_line(self, value: str) -> None:
        if self._read_future and not self._read_future.done():
            self._input_text = value
            self._read_future.set_result(value)

    def request_eof(self) -> None:
        self._eof_requested = True
        self.cancel_read("")

    def move_history(self, *, up: bool) -> Optional[str]:
        if not self._history:
            return None
        if self._history_index is None:
            self._history_index = len(self._history)
        if up:
            self._history_index = max(0, self._history_index - 1)
        else:
            self._history_index = min(len(self._history), self._history_index + 1)
        return self._history[self._history_index] if self._history_index < len(self._history) else ""


class PokerTextualApp(App[int]):
    """Responsive two-column HPoker interface."""

    TITLE = "HPoker"
    SUB_TITLE = "Texas Hold'em"
    BINDINGS = [
        ("ctrl+c", "shutdown", "退出"),
        ("ctrl+d", "eof", "返回/退出"),
    ]

    CSS = """
    Screen {
        background: #090c12;
        color: #d7dce5;
        layout: vertical;
    }
    #topbar {
        height: 3;
        padding: 0 2;
        content-align: left middle;
        color: #e7c873;
        background: #111722;
        text-style: bold;
        border-bottom: solid #364154;
    }
    #workspace {
        height: 1fr;
        padding: 1;
    }
    #main-panel, #side-panel {
        height: 100%;
        padding: 0 1;
        background: #0d121b;
        border: round #364154;
        overflow-y: auto;
    }
    #main-panel {
        width: 3fr;
        margin-right: 1;
        border-title-color: #e7c873;
    }
    #side-panel {
        width: 1fr;
        min-width: 31;
        border-title-color: #73c7e7;
    }
    #notice {
        height: auto;
        max-height: 3;
        padding: 0 2;
        color: #8fd6a4;
        background: #111722;
    }
    #command-bar {
        height: 3;
        background: #111722;
        border-top: solid #364154;
    }
    #prompt-label {
        width: 10;
        padding-left: 2;
        content-align: left middle;
        color: #e7c873;
        text-style: bold;
    }
    #command-input {
        width: 1fr;
        height: 3;
        border: none;
        background: #111722;
    }
    Screen.narrow #workspace {
        layout: vertical;
    }
    Screen.narrow #main-panel {
        width: 100%;
        height: 2fr;
        margin-right: 0;
        margin-bottom: 1;
    }
    Screen.narrow #side-panel {
        width: 100%;
        min-width: 0;
        height: 1fr;
    }
    Screen.compact #topbar {
        height: 1;
        padding: 0 1;
        border: none;
    }
    Screen.compact #workspace {
        padding: 0;
    }
    Screen.compact #main-panel, Screen.compact #side-panel {
        padding: 0 1;
        border: none;
    }
    Screen.compact #main-panel {
        margin-bottom: 0;
    }
    Screen.compact #side-panel {
        border-top: solid #273142;
    }
    Screen.compact #notice {
        max-height: 1;
        padding: 0 1;
    }
    Screen.compact #command-bar, Screen.compact #command-input {
        height: 1;
    }
    Screen.compact #command-bar {
        border: none;
    }
    Screen.compact #prompt-label {
        width: 8;
        padding-left: 1;
    }
    """

    def __init__(self, controller, room_id: Optional[str] = None, *, autostart: bool = True) -> None:
        super().__init__()
        self.controller = controller
        self.room_id = room_id
        self.autostart = autostart
        self.bridge = TextualTuiBridge(self)
        self.controller.tui = self.bridge

    def compose(self) -> ComposeResult:
        yield Static("HPoker  ·  正在载入", id="topbar", markup=False)
        with Horizontal(id="workspace"):
            yield Static("正在载入…", id="main-panel", markup=False)
            yield Static("输入 help 查看命令", id="side-panel", markup=False)
        yield Static("", id="notice", markup=False)
        with Horizontal(id="command-bar"):
            yield Static("大厅 ›", id="prompt-label", markup=False)
            yield Input(placeholder="输入命令，Enter 执行", id="command-input")

    async def on_mount(self) -> None:
        self.bridge.enter()
        self._apply_responsive_class(self.size.width, self.size.height)
        self.query_one("#main-panel", Static).border_title = "牌桌"
        self.query_one("#side-panel", Static).border_title = "操作"
        self.query_one("#command-input", Input).focus()
        if self.autostart:
            self.run_worker(self._run_controller(), group="controller", exclusive=True)

    async def _run_controller(self) -> None:
        try:
            if self.room_id:
                await self.controller.enter_room(self.room_id)
            else:
                await self.controller.run_lobby_loop()
        finally:
            self.exit(0)

    @on(Input.Submitted, "#command-input")
    def _on_command(self, event: Input.Submitted) -> None:
        value = event.value
        event.input.value = ""
        self.bridge.submit_line(value)

    @on(events.Resize)
    def _on_resize(self, event: events.Resize) -> None:
        self._apply_responsive_class(event.size.width, event.size.height)
        if self.bridge.active:
            self.controller._refresh_tui()

    @on(events.Key)
    def _on_key(self, event: events.Key) -> None:
        if event.key not in {"up", "down"}:
            return
        command_input = self.query_one("#command-input", Input)
        if not command_input.has_focus:
            return
        value = self.bridge.move_history(up=event.key == "up")
        if value is not None:
            command_input.value = value
            command_input.cursor_position = len(value)
            event.stop()

    def _apply_responsive_class(self, width: int, height: int) -> None:
        self.screen.set_class(width < 100, "narrow")
        self.screen.set_class(width < 100 or height < 30, "compact")

    @staticmethod
    def _rich_text(value: str) -> Text:
        return Text.from_ansi(value or "")

    def set_prompt(self, prompt: str) -> None:
        label = prompt.rstrip().rstrip(">").strip() or "命令"
        self.query_one("#prompt-label", Static).update(f"{label} ›")

    def update_dashboard(self, fallback_frame: str, *, prompt: str, notice: str) -> None:
        controller = self.controller
        renderer = controller.renderer
        view = controller._tui_view
        panel_open = controller._tui_panel is not None
        compact = self.screen.has_class("compact")

        if panel_open:
            main = fallback_frame
            main_title = "详情"
        elif view == "room" and controller.active_room_data:
            main = renderer.render_table_main(
                controller.active_room_data,
                controller._current_user_id(),
                compact=compact,
            )
            main_title = "牌桌"
        elif view == "lobby" and controller.current_user:
            main = renderer.render_lobby_main(controller.current_user, controller.rooms)
            main_title = "房间"
        else:
            main = fallback_frame
            main_title = "HPoker"

        if view == "room":
            sidebar = renderer.render_table_sidebar(
                controller.active_room_data or {},
                controller._current_user_id(),
                compact=compact,
            )
            room = controller.active_room_data or {}
            cfg = room.get("config", {})
            title = cfg.get("room_name") or room.get("room_name") or "HPoker 牌桌"
        else:
            sidebar = renderer.render_lobby_sidebar(bool((controller.current_user or {}).get("is_admin")))
            title = "HPoker  ·  游戏大厅"

        main_widget = self.query_one("#main-panel", Static)
        side_widget = self.query_one("#side-panel", Static)
        main_widget.border_title = main_title
        main_widget.update(self._rich_text(main))
        side_widget.update(self._rich_text(sidebar))
        self.query_one("#topbar", Static).update(title)
        self.query_one("#notice", Static).update(self._rich_text(notice))
        self.set_prompt(prompt)

    def action_eof(self) -> None:
        self.bridge.request_eof()

    def action_shutdown(self) -> None:
        self.bridge.request_eof()


async def run_textual_ui(controller, room_id: Optional[str] = None) -> int:
    """Run the dashboard frontend in the caller's asyncio loop."""

    app = PokerTextualApp(controller, room_id)
    result = await app.run_async(mouse=False)
    return int(result or 0)
