"""Interactive controller for the HPoker terminal client.

The controller intentionally owns the user-facing state machine while the
REST and WebSocket classes stay transport-only.  That keeps command handling
testable and, more importantly, prevents an incoming room update from being
mistaken for a user command.
"""

from __future__ import annotations

import asyncio
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence
from urllib.parse import quote, urlsplit

from cli.api_client import PokerApiClient, PokerApiError
from cli.commands import (
    BetSizingContext,
    CommandParseError,
    CliCommand,
    is_global_command,
    normalize_command,
    parse_command,
    resolve_bet_amount,
)
from cli.ui_renderer import Colors, PokerUiRenderer
from cli.tui import TerminalTui
from cli.ws_client import PokerWsClient


class PokerCliController:
    """Coordinate authentication, lobby navigation, and room gameplay."""

    def __init__(
        self,
        server_url: str = "http://127.0.0.1:8000",
        username: Optional[str] = None,
        password: Optional[str] = "123",
        mode: str = "dashboard",
        enable_color: bool = True,
        http_timeout: float = 10.0,
        reconnect_attempts: int = 2,
    ):
        self.server_url = server_url.rstrip("/")
        self.default_username = username
        self.default_password = password
        self.reconnect_attempts = max(0, int(reconnect_attempts))
        self.api = PokerApiClient(base_url=self.server_url, timeout=http_timeout)
        self.renderer = PokerUiRenderer(enable_color=enable_color, mode=mode)

        self.current_user: Optional[Dict[str, Any]] = None
        self.auth_token: Optional[str] = None
        self.rooms: List[Dict[str, Any]] = []

        self.active_room_id: Optional[str] = None
        self.active_room_data: Optional[Dict[str, Any]] = None
        self.ws_client: Optional[PokerWsClient] = None

        self._in_room = False
        self._closing_room = False
        self._connection_lost = False
        self._room_deleted = False
        self._quit_requested = False
        self._stdin_closed = False
        self._prompt_displayed = False
        self._render_lock = asyncio.Lock()
        self.command_history: List[str] = []

        # Dashboard mode uses a single alternate-screen frame when a real
        # terminal is available.  Stream mode and redirected output keep the
        # traditional line-oriented behavior.
        self.tui = TerminalTui()
        self._tui_view: Optional[str] = None
        self._tui_notice = ""
        self._tui_panel: Optional[str] = None
        self._tui_panel_title = ""
        self._tui_panel_kind: Optional[str] = None
        self._tui_prompt = ""
        self._tui_timer_task: Optional[asyncio.Task] = None

    # ------------------ Fixed-screen TUI ------------------

    def _begin_tui(self, view: str) -> bool:
        """Start the fixed dashboard screen when stdout/stdin are terminals."""

        if self.renderer.mode != "dashboard":
            return False
        if not self.tui.active and not self.tui.enter():
            return False
        if self._tui_view != view:
            self._tui_prompt = ""
            self._tui_panel = None
            self._tui_panel_title = ""
            self._tui_panel_kind = None
            self.tui.clear_input()
        self._tui_view = view
        if view == "room":
            self._start_tui_timer()
        elif self._tui_timer_task:
            self._tui_timer_task.cancel()
            self._tui_timer_task = None
        self._refresh_tui()
        return self.tui.active

    def _end_tui(self) -> None:
        if self._tui_timer_task:
            self._tui_timer_task.cancel()
            self._tui_timer_task = None
        self.tui.exit()
        self._tui_view = None
        self._tui_notice = ""
        self._tui_panel = None
        self._tui_panel_title = ""
        self._tui_panel_kind = None
        self._tui_prompt = ""

    def _start_tui_timer(self) -> None:
        """Start local redraws so the countdown moves between WS updates."""

        if not self.tui.active:
            return
        if self._tui_timer_task and not self._tui_timer_task.done():
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        self._tui_timer_task = loop.create_task(self._tui_timer_loop())

    async def _tui_timer_loop(self) -> None:
        """Refresh the room dashboard at a steady cadence from local time."""

        current_task = asyncio.current_task()
        try:
            while (
                self.tui.active
                and self._in_room
                and self._tui_view == "room"
                and self.renderer.mode == "dashboard"
            ):
                if self.active_room_data:
                    async with self._render_lock:
                        if self.tui.active and self._tui_view == "room":
                            self._refresh_tui(now=time.time())
                await asyncio.sleep(0.2)
        except asyncio.CancelledError:
            raise
        finally:
            if self._tui_timer_task is current_task:
                self._tui_timer_task = None

    def _refresh_tui(self, now: Optional[float] = None) -> None:
        """Draw the current lobby/table frame and its fixed footer."""

        if not self.tui.active:
            return

        if self._tui_panel is not None:
            frame = self._tui_panel
        elif self._tui_view == "lobby" and self.current_user:
            frame = self.renderer.render_lobby(self.current_user, self.rooms, self.server_url)
        elif self._tui_view == "room" and self.active_room_data:
            frame = self.renderer.render_table_dashboard(
                self.active_room_data,
                self._current_user_id(),
                now=now,
            )
        elif self._tui_view == "room":
            frame = "HPoker 牌桌\n\n正在等待服务器发送房间状态……"
        else:
            frame = "HPoker\n\n正在加载……"

        if self._tui_panel_kind == "settlement":
            prompt = "结算> "
        elif self._tui_view == "room":
            prompt = "断线> " if not self.ws_client or not self.ws_client.is_connected else "牌桌> "
        else:
            prompt = "大厅> "
        if self._tui_prompt:
            prompt = self._tui_prompt
        footer = self._tui_notice
        if self._tui_panel:
            panel_hint = "输入 q 返回上一页；方向键 ↑/↓ 可浏览历史命令"
            footer = f"{footer}\n{panel_hint}" if footer else panel_hint
        self.tui.draw(
            frame,
            prompt=prompt,
            input_text=self.tui.input_text,
            footer=footer,
        )

    def _output(
        self,
        message: Any = "",
        *,
        panel: bool = False,
        panel_title: str = "详情",
        panel_kind: str = "details",
    ) -> None:
        """Send user feedback to the footer instead of scrolling the TUI."""

        if not self.tui.active:
            print(message)
            return
        text = str(message)
        if panel or "\n" in text.strip("\n"):
            self._tui_panel = text.strip("\n")
            self._tui_panel_title = panel_title
            self._tui_panel_kind = panel_kind
        else:
            self._tui_notice = text
        self._refresh_tui()

    async def _dispatch_global_command(
        self,
        command: CliCommand,
        scope: str,
        rooms: Sequence[Dict[str, Any]] = (),
    ) -> Optional[bool]:
        """Handle commands whose aliases and meaning are identical everywhere."""

        name = command.name
        args = command.args
        if name == "quit":
            self._quit_requested = True
            self._in_room = False
            self._output("再见！祝游戏愉快！")
            return False
        if name == "help":
            self._output(self.renderer.render_help(scope), panel=True)
            return True
        if name == "users":
            await self._show_users()
            return True
        if name == "info":
            if scope == "lobby":
                if not args:
                    self._output("用法: info <房间序号或 room_id>")
                else:
                    await self._show_room_info(self._resolve_room_ref(args[0], rooms))
            elif self.active_room_data:
                self._output(self.renderer.render_room_details(self.active_room_data), panel=True)
            else:
                self._output("尚未收到房间状态。")
            return True
        if name == "refresh":
            if scope == "room":
                await self._redraw_room()
            return True
        if name == "mode":
            self._set_mode(args[0] if args else None)
            if scope == "room" and self.active_room_data:
                await self._redraw_room()
            return True
        if name == "color":
            self._set_color(args[0] if args else None)
            return True
        return None

    # ------------------ Authentication Flow ------------------

    async def _try_login(self, username: str, password: str) -> bool:
        try:
            result = await self.api.login(username.strip(), password)
            user = result.get("user") if isinstance(result, dict) else None
            token = result.get("token") if isinstance(result, dict) else None
            if not user or not token:
                raise PokerApiError("服务器返回的登录信息不完整")
            self.auth_token = token
            self.current_user = user
            self._output(
                self.renderer.c(
                    f"✓ 登录成功！欢迎回来，{user.get('nickname', user.get('username', username))}",
                    Colors.BRIGHT_GREEN + Colors.BOLD,
                )
            )
            return True
        except Exception as exc:
            self._output(self.renderer.c(f"✗ 登录失败: {self._friendly_error(exc)}", Colors.BRIGHT_RED))
            return False

    async def login_flow(self) -> bool:
        """Login via command-line credentials or a resilient interactive flow."""

        if self.default_username:
            username = self.default_username
            password = self.default_password if self.default_password is not None else "123"
            if await self._try_login(username, password):
                return True
            # Do not keep retrying the same failed command-line credentials
            # when the user later invokes ``user``/``logout``.
            self.default_username = None

        while True:
            self._output("\n" + self.renderer.c("=" * 60, Colors.CYAN))
            self._output(self.renderer.c("  HPoker 终端客户端 - 用户登录", Colors.BOLD + Colors.BRIGHT_WHITE))
            self._output(self.renderer.c("=" * 60, Colors.CYAN))

            username = (await self._async_input("用户名（输入 users 查看账号，q 退出）: ")).strip()
            if self._stdin_closed:
                return False
            if not username:
                continue
            if is_global_command(username, "quit"):
                return False
            if username.lower() in {"users", "list"}:
                await self._show_users()
                continue

            password = await self._async_password_input("密码: ")
            if self._stdin_closed:
                return False
            if await self._try_login(username, password):
                return True
            self._output("请重新输入；输入 users 可查看可用账号。")

    async def _show_users(self) -> None:
        try:
            users = await self.api.list_users()
            self._output(self.renderer.render_users(users), panel=True)
        except Exception as exc:
            self._output(self.renderer.c(f"获取用户列表失败: {self._friendly_error(exc)}", Colors.BRIGHT_RED))

    # ------------------ Lobby Loop ------------------

    async def _fetch_rooms(self) -> List[Dict[str, Any]]:
        try:
            rooms = await self.api.list_rooms()
            self.rooms = rooms
            return rooms
        except Exception as exc:
            self._output(self.renderer.c(f"获取房间列表失败: {self._friendly_error(exc)}", Colors.BRIGHT_RED))
            return self.rooms

    async def run_lobby_loop(self) -> None:
        """Run the lobby until logout or EOF/quit."""

        self._begin_tui("lobby")
        try:
            while self.current_user and not self._quit_requested:
                self._begin_tui("lobby")
                rooms = await self._fetch_rooms()
                if self.tui.active:
                    self._tui_view = "lobby"
                    self._refresh_tui()
                else:
                    if self.renderer.mode == "dashboard":
                        self.renderer.clear_screen()
                    self._output(self.renderer.render_lobby(self.current_user, rooms, self.server_url))

                command = await self._read_command("大厅> ")
                if command is None:
                    break
                if not command.raw:
                    continue
                self.command_history.append(command.raw)

                try:
                    should_continue = await self._dispatch_lobby_command(command, rooms)
                except Exception as exc:
                    self._output(self.renderer.c(f"命令执行失败: {self._friendly_error(exc)}", Colors.BRIGHT_RED))
                    should_continue = True
                if not should_continue:
                    break
        finally:
            self._end_tui()

    async def _dispatch_lobby_command(
        self,
        command: CliCommand,
        rooms: Sequence[Dict[str, Any]],
    ) -> bool:
        command = normalize_command(command, "lobby")
        name = command.name
        args = command.args

        global_result = await self._dispatch_global_command(command, "lobby", rooms)
        if global_result is not None:
            return global_result
        if name == "rooms":
            return True
        if name == "user":
            self._end_tui()
            self.current_user = None
            self.auth_token = None
            self.default_username = None
            return await self.login_flow()
        if name == "create":
            if args and args[0].lower() in {"help", "?"}:
                self._output(self._render_create_help(), panel=True)
            else:
                await self.create_room_flow(args)
            return True
        if name == "join":
            room_ref = args[0] if args else await self._async_input("房间序号或 ID: ")
            if self._stdin_closed:
                return False
            if room_ref.strip():
                await self.enter_room(self._resolve_room_ref(room_ref.strip(), rooms))
            return True
        if name.isdigit():
            index = int(name)
            if 1 <= index <= len(rooms):
                await self.enter_room(str(rooms[index - 1].get("room_id", "")))
            else:
                self._output("无效的房间序号。")
            return True

        self._output(f"未知大厅命令: {command.raw}；输入 help 查看可用命令。")
        return True

    def _resolve_room_ref(self, value: str, rooms: Sequence[Dict[str, Any]]) -> str:
        if value.isdigit():
            index = int(value)
            if 1 <= index <= len(rooms):
                return str(rooms[index - 1].get("room_id", ""))
        return value

    async def _show_room_info(self, room_id: str) -> None:
        try:
            room = await self.api.get_room(room_id, self._current_user_id())
            self._output(self.renderer.render_room_details(room), panel=True)
        except Exception as exc:
            self._output(self.renderer.c(f"获取房间详情失败: {self._friendly_error(exc)}", Colors.BRIGHT_RED))

    async def create_room_flow(self, args: Optional[Sequence[str]] = None) -> None:
        """Create a room interactively or from ``create --option value``."""

        if not self.current_user:
            return
        options = list(args or [])
        defaults: Dict[str, Any] = {
            "name": f"{self.current_user.get('nickname', '玩家')}的局",
            "buyin": 1000,
            "cash": 100.0,
            "sb": 10,
            "timeout": 15,
            "seats": 6,
        }

        if options:
            try:
                supplied = self._parse_create_options(options)
                defaults.update(supplied)
            except ValueError as exc:
                self._output(self.renderer.c(f"创建参数错误: {exc}", Colors.BRIGHT_RED))
                self._output(self._render_create_help(), panel=True)
                return
        else:
            self._output("\n" + self.renderer.c("--- 创建德州扑克现金桌（回车使用默认值）---", Colors.BOLD + Colors.CYAN))
            name = await self._prompt_text(f"房间名称 [{defaults['name']}]: ", str(defaults["name"]))
            if name is None:
                return
            defaults["name"] = name
            for key, label, parser, minimum, maximum in (
                ("buyin", "买入筹码", int, 10, None),
                ("cash", "买入现金(元)", float, 0.01, None),
                ("sb", "小盲注 SB", int, 1, None),
                ("timeout", "行动时限(秒)", int, 5, 60),
                ("seats", "座位数", int, 2, 9),
            ):
                value = await self._prompt_number(
                    f"{label} [{defaults[key]}]: ",
                    defaults[key],
                    parser,
                    minimum,
                    maximum,
                )
                if value is None:
                    return
                defaults[key] = value

        try:
            self._validate_create_options(defaults)
            room_data = await self.api.create_room(
                host_player_id=self._current_user_id(),
                room_name=str(defaults["name"]),
                buyin_chips=int(defaults["buyin"]),
                cash_value=float(defaults["cash"]),
                small_blind=int(defaults["sb"]),
                action_timeout=int(defaults["timeout"]),
                max_seats=int(defaults["seats"]),
            )
            room_id = room_data.get("room_id", "")
            self._output(self.renderer.c(f"✓ 房间创建成功！ID: {room_id}", Colors.BRIGHT_GREEN + Colors.BOLD))
            if room_id:
                await self.enter_room(room_id)
        except Exception as exc:
            self._output(self.renderer.c(f"✗ 创建房间失败: {self._friendly_error(exc)}", Colors.BRIGHT_RED))

    @staticmethod
    def _parse_create_options(args: Sequence[str]) -> Dict[str, Any]:
        aliases = {
            "--name": "name",
            "-n": "name",
            "--buyin": "buyin",
            "--chips": "buyin",
            "--cash": "cash",
            "--sb": "sb",
            "--small-blind": "sb",
            "--timeout": "timeout",
            "--seats": "seats",
        }
        parsers = {"buyin": int, "cash": float, "sb": int, "timeout": int, "seats": int}
        result: Dict[str, Any] = {}
        positional_name: Optional[str] = None
        index = 0
        while index < len(args):
            token = args[index]
            if "=" in token and token.startswith("-"):
                option, raw_value = token.split("=", 1)
            elif token.startswith("-"):
                option = token
                index += 1
                if index >= len(args):
                    raise ValueError(f"{option} 缺少值")
                raw_value = args[index]
            else:
                if positional_name is not None:
                    raise ValueError("只能提供一个房间名称")
                positional_name = token
                index += 1
                continue

            key = aliases.get(option.lower())
            if key is None:
                raise ValueError(f"不支持的选项 {option}")
            if not raw_value.strip():
                raise ValueError(f"{option} 的值不能为空")
            try:
                result[key] = parsers.get(key, str)(raw_value) if key != "name" else raw_value
            except ValueError as exc:
                raise ValueError(f"{option} 的值无效: {raw_value}") from exc
            index += 1
        if positional_name is not None and "name" not in result:
            result["name"] = positional_name
        return result

    @staticmethod
    def _validate_create_options(options: Dict[str, Any]) -> None:
        if not str(options.get("name", "")).strip():
            raise ValueError("房间名称不能为空")
        if int(options["buyin"]) < 10:
            raise ValueError("买入筹码不能少于 10")
        if float(options["cash"]) <= 0:
            raise ValueError("现金金额必须大于 0")
        if int(options["sb"]) < 1:
            raise ValueError("小盲注必须至少为 1")
        if not 5 <= int(options["timeout"]) <= 60:
            raise ValueError("行动时限必须在 5~60 秒之间")
        if not 2 <= int(options["seats"]) <= 9:
            raise ValueError("座位数必须在 2~9 之间")

    def _render_create_help(self) -> str:
        return (
            "创建方式: create [房间名] [--buyin 筹码] [--cash 元] "
            "[--sb 小盲] [--timeout 秒] [--seats 2~9]\n"
            "示例: create \"周五现金局\" --buyin 2000 --cash 200 --sb 10 --timeout 20 --seats 6"
        )

    # ------------------ Room Gameplay Flow ------------------

    async def enter_room(self, room_id: str) -> None:
        """Connect to a room and keep the command loop alive across reconnects."""

        room_id = room_id.strip()
        if not room_id or not self.current_user:
            self._output("房间 ID 不能为空。")
            return

        had_tui = self.tui.active
        self.active_room_id = room_id
        self.active_room_data = None
        self._in_room = True
        self._closing_room = False
        self._connection_lost = False
        self._room_deleted = False
        self.ws_client = self._new_ws_client(room_id)
        if self.renderer.mode == "dashboard":
            self._begin_tui("room")

        tui_owner = not had_tui and self.tui.active
        self._output(f"正在连接房间 {room_id} ...")
        try:
            await self.ws_client.connect(retries=self.reconnect_attempts, retry_delay=0.8)
            self._output(self.renderer.c("✓ 已连接。输入 help 查看牌桌命令。", Colors.BRIGHT_GREEN))
            await self._in_room_input_loop()
        except Exception as exc:
            self._output(self.renderer.c(f"✗ 无法连接到房间: {self._friendly_error(exc)}", Colors.BRIGHT_RED))
        finally:
            self._in_room = False
            self._closing_room = True
            if self.ws_client:
                await self.ws_client.disconnect()
            self.ws_client = None
            self.active_room_id = None
            self.active_room_data = None
            self._closing_room = False
            if tui_owner:
                self._end_tui()
            elif self.tui.active:
                self._begin_tui("lobby")

    def _new_ws_client(self, room_id: str) -> PokerWsClient:
        parsed = urlsplit(self.server_url if "://" in self.server_url else f"http://{self.server_url}")
        scheme = "wss" if parsed.scheme == "https" else "ws"
        netloc = parsed.netloc or parsed.path
        ws_url = f"{scheme}://{netloc}/ws/{quote(room_id, safe='')}/{quote(self._current_user_id(), safe='')}"
        client = PokerWsClient(ws_url=ws_url)
        client.on_room_state = self._on_ws_room_state
        client.on_action_event = self._on_ws_action_event
        client.on_sound_effect = self._on_ws_sound_effect
        client.on_settlement_report = self._on_ws_settlement_report
        client.on_room_deleted = self._on_ws_room_deleted
        client.on_error = self._on_ws_error
        client.on_disconnect = self._on_ws_disconnect
        return client

    async def _in_room_input_loop(self) -> None:
        """Dispatch room commands; offline mode keeps only recovery commands."""

        while self._in_room:
            prompt = "断线> " if not self.ws_client or not self.ws_client.is_connected else "牌桌> "
            command = await self._read_command(prompt)
            if command is None:
                break
            if not command.raw:
                continue
            self.command_history.append(command.raw)
            try:
                await self._dispatch_room_command(command)
            except Exception as exc:
                self._output(self.renderer.c(f"命令执行失败: {self._friendly_error(exc)}", Colors.BRIGHT_RED))

    async def _dispatch_room_command(self, command: CliCommand) -> None:
        command = normalize_command(command, "room")
        name = command.name
        args = command.args

        global_result = await self._dispatch_global_command(command, "room")
        if global_result is not None:
            return
        if name == "leave":
            self._output("正在离开房间...")
            self._in_room = False
            return
        if name == "history":
            limit = self._parse_positive_int(args[0], 10) if args else 10
            if self.active_room_data:
                self._output(self.renderer.render_action_history(self.active_room_data, limit), panel=True)
            return
        if name == "reconnect":
            await self._reconnect_room()
            return
        if name == "ready":
            await self._send_ws("player_ready", True)
            return
        if name == "unready":
            await self._send_ws("player_ready", False)
            return
        if name == "start":
            await self._send_ws("start_game")
            return
        if name == "rebuy":
            await self._send_ws("rebuy")
            return
        if name == "sit":
            if not args:
                self._output("用法: sit <座位号>（从 0 开始）")
                return
            seat = self._parse_nonnegative_int(args[0])
            if seat is None:
                self._output("座位号必须是非负整数。")
                return
            await self._send_ws("sit_down", seat)
            return
        if name == "bot":
            seat = self._parse_nonnegative_int(args[0]) if args else None
            await self._handle_add_bot(seat)
            return

        # Action aliases are intentionally checked before the generic utility
        # commands so ``r`` always means raise in a room; redraw is explicit.
        if name == "check":
            await self._handle_check_or_call()
            return
        if name == "fold":
            await self._send_action("FOLD", 0)
            return
        if name == "allin":
            await self._handle_all_in()
            return
        if name == "raise":
            await self._handle_raise_command([name, *args])
            return
        if name == "timecard":
            await self._send_ws("use_time_card")
            return
        if name == "rit":
            choice = self._parse_positive_int(args[0], 0) if args else 0
            if choice not in (1, 2):
                self._output("用法: rit 1（发一次）或 rit 2（发两次）")
            else:
                await self._send_ws("rit_choice", choice)
            return
        if name == "show":
            await self._handle_show_command(name, list(args))
            return
        if name == "bill":
            await self._show_settlement()
            return
        if name == "end":
            await self._end_room()
            return
        if name == "delete":
            await self._delete_room()
            return
        if name == "export":
            await self._export_settlement(args[0] if args else None)
            return

        self._output(f"未知牌桌命令: {command.raw}；输入 help 查看可用命令。")

    async def _reconnect_room(self) -> None:
        if not self.ws_client:
            self._output("当前没有房间连接。")
            return
        try:
            self._output("正在重连...")
            await self.ws_client.reconnect(retries=self.reconnect_attempts, retry_delay=0.8)
            self._connection_lost = False
            self._output(self.renderer.c("✓ 重连成功，服务器会发送最新状态。", Colors.BRIGHT_GREEN))
        except Exception as exc:
            self._connection_lost = True
            self._output(self.renderer.c(f"重连失败: {self._friendly_error(exc)}", Colors.BRIGHT_RED))

    async def _send_ws(self, method: str, *args: Any, **kwargs: Any) -> bool:
        if not self.ws_client or not self.ws_client.is_connected:
            self._output("当前已断线，请输入 reconnect 重连。")
            return False
        try:
            await getattr(self.ws_client, method)(*args, **kwargs)
            return True
        except Exception as exc:
            self._output(self.renderer.c(f"发送操作失败: {self._friendly_error(exc)}", Colors.BRIGHT_RED))
            return False

    async def _send_action(self, action: str, amount: int) -> bool:
        legal = self._get_legal_actions()
        if action == "FOLD" and not legal.get("can_fold", False):
            self._output("当前不能弃牌。")
            return False
        if action == "CHECK" and not legal.get("can_check", False):
            self._output("当前不能过牌。")
            return False
        if action == "CALL" and not legal.get("can_call", False):
            self._output("当前不能跟注。")
            return False
        if action == "ALL_IN" and not legal.get("can_all_in", False):
            self._output("当前不能全下。")
            return False
        if action in {"BET", "RAISE"} and not (
            legal.get("can_bet", False) or legal.get("can_raise", False)
        ):
            self._output("当前不能下注或加注。")
            return False
        return await self._send_ws("player_action", action, int(amount))

    async def _handle_check_or_call(self) -> None:
        legal = self._get_legal_actions()
        if legal.get("can_check"):
            await self._send_action("CHECK", 0)
        elif legal.get("can_call"):
            await self._send_action("CALL", self._as_int(legal.get("call_amount")))
        else:
            self._output("当前不可过牌或跟注（可能还没轮到你）。")

    async def _handle_all_in(self) -> None:
        legal = self._get_legal_actions()
        await self._send_action("ALL_IN", self._as_int(legal.get("all_in_amount")))

    # ------------------ Action Parsing Helpers ------------------

    async def _handle_raise_command(self, parts: List[str]) -> None:
        """Resolve a total round-bet amount and send BET/RAISE."""

        legal = self._get_legal_actions()
        can_bet = bool(legal.get("can_bet", False))
        can_raise = bool(legal.get("can_raise", False))
        if not can_bet and not can_raise:
            self._output("当前不可下注或加注（可能还没轮到你）。")
            return

        action = "BET" if can_bet else "RAISE"
        minimum = self._as_int(legal.get("min_bet" if can_bet else "min_raise_to"))
        if not minimum:
            minimum = self._as_int(legal.get("min_raise" if can_raise else "min_bet"))
        maximum = self._as_int(legal.get("max_bet" if can_bet else "max_raise_to"))
        if not maximum:
            maximum = self._as_int(legal.get("max_raise" if can_raise else "max_bet"))

        table = self.active_room_data.get("table", {}) if self.active_room_data else {}
        config = self.active_room_data.get("config", {}) if self.active_room_data else {}
        my_seat = self._get_my_seat()
        context = BetSizingContext(
            pot=self._as_int(table.get("total_pot")),
            minimum=minimum,
            maximum=maximum,
            small_blind=self._as_int(table.get("small_blind"), self._as_int(config.get("small_blind"), 1)),
            current_round_bet=self._as_int(my_seat.get("current_round_bet")) if my_seat else 0,
            current_highest_bet=self._as_int(table.get("current_round_highest_bet")),
            big_blind=self._as_int(table.get("big_blind"), self._as_int(config.get("big_blind"), 0)) or None,
        )
        token = parts[1] if len(parts) > 1 else None
        target = resolve_bet_amount(token, context)
        if target is None:
            self._output("无法识别下注额度；示例: r 100、r 1/2p、r 2.5bb、r +1bb、r allin")
            return

        raw_numeric = self._parse_raw_number(token)
        if raw_numeric is not None and raw_numeric < minimum:
            self._output(f"下注金额小于最小值 {minimum}，已调整为 {target}。")
        if raw_numeric is not None and raw_numeric > maximum:
            self._output(f"下注金额超过最大值 {maximum}，已调整为全下额度 {target}。")
        await self._send_action(action, target)

    async def _handle_show_command(self, name: str, args: List[str]) -> None:
        if not self.active_room_data or self.active_room_data.get("table", {}).get("street") != "HAND_END":
            self._output("只有本手结束后才能亮牌。")
            return

        choice = name.lower()
        value = args[0].lower() if args else ""
        if choice == "s1" or value == "1":
            await self._send_ws("show_card", card_index=0)
            self._output("✓ 已亮出第 1 张手牌。")
        elif choice == "s2" or value == "2":
            await self._send_ws("show_card", card_index=1)
            self._output("✓ 已亮出第 2 张手牌。")
        elif choice in {"sa", "showall"} or value in {"all", "a"}:
            await self._send_ws("show_card", show_all=True)
            self._output("✓ 已亮出全部手牌。")
        elif choice in {"muck", "hide"} or value in {"hide", "none", "muck"}:
            await self._send_ws("show_card", hide_all=True)
            self._output("✓ 已盖牌。")
        elif value == "toggle" and len(args) > 1 and args[1] in {"1", "2"}:
            await self._send_ws("show_card", toggle_index=int(args[1]) - 1)
        else:
            self._output("用法: show 1 | show 2 | show all | show toggle 1 | muck")

    # ------------------ Room Lifecycle / Settlement ------------------

    async def _handle_add_bot(self, seat_index: Optional[int] = None) -> None:
        if not self._is_host():
            self._output("只有房主可以添加测试机器人。")
            return
        if self.active_room_data:
            table = self.active_room_data.get("table", {})
            street = table.get("street")
            if street not in ("IDLE", "HAND_END"):
                self._output("只能在手牌间隙（未开局或手牌结束时）添加机器人。")
                return
            seats = table.get("seats", [])
            if seat_index is not None:
                if seat_index < 0 or seat_index >= len(seats):
                    self._output(f"座位号超出范围（0 - {len(seats) - 1}）。")
                    return
                if seats[seat_index] is not None:
                    self._output(f"座位 {seat_index} 已有玩家。")
                    return
            else:
                if all(s is not None for s in seats):
                    self._output("牌桌已满，无法添加机器人。")
                    return

        if self.ws_client and self.ws_client.is_connected:
            ok = await self._send_ws("add_bot", seat_index=seat_index)
            if ok:
                seat_str = f" 到座位 {seat_index}" if seat_index is not None else ""
                self._output(f"已请求添加测试机器人{seat_str}。")
            return

        try:
            room = await self.api.add_test_bot(
                self.active_room_id or "",
                requester_id=self._current_user_id(),
                seat_index=seat_index,
            )
            self.active_room_data = room
            self._output("✓ 已成功添加测试机器人。")
            if self.renderer.mode == "dashboard":
                await self._redraw_room()
        except Exception as exc:
            self._output(self.renderer.c(f"添加机器人失败: {self._friendly_error(exc)}", Colors.BRIGHT_RED))

    async def _end_room(self) -> None:
        if not self._is_host():
            self._output("只有房主可以结束房间。")
            return
        confirmed = (await self._async_input("确定结束房间并生成结算清单吗？(y/n): ")).strip().lower()
        if self._stdin_closed or confirmed not in {"y", "yes"}:
            self._output("已取消。")
            return
        if self.ws_client and self.ws_client.is_connected:
            await self._send_ws("end_room")
            return
        try:
            report = await self.api.end_room(self.active_room_id or "", self._current_user_id())
            self._merge_settlement_report(report)
            self._output(self.renderer.render_settlement_report(report), panel=True)
        except Exception as exc:
            self._output(self.renderer.c(f"结束房间失败: {self._friendly_error(exc)}", Colors.BRIGHT_RED))

    async def _delete_room(self) -> None:
        if not self._is_host() and not bool(self.current_user and self.current_user.get("is_admin")):
            self._output("只有房主或管理员可以解散房间。")
            return
        confirmed = (await self._async_input("确定解散房间并让所有玩家退出吗？(y/n): ")).strip().lower()
        if self._stdin_closed or confirmed not in {"y", "yes"}:
            self._output("已取消。")
            return
        if self.ws_client and self.ws_client.is_connected:
            await self._send_ws("delete_room")
            return
        try:
            await self.api.delete_room(self.active_room_id or "", self._current_user_id())
            self._output("房间已解散。")
            self._in_room = False
        except Exception as exc:
            self._output(self.renderer.c(f"解散房间失败: {self._friendly_error(exc)}", Colors.BRIGHT_RED))

    async def _show_settlement(self) -> None:
        report = self.active_room_data.get("settlement_report") if self.active_room_data else None
        if report:
            self._open_settlement_page(report)
            return
        if not self.active_room_id:
            self._output("当前没有房间结算清单。")
            return
        try:
            room = await self.api.get_room(self.active_room_id, self._current_user_id())
            report = room.get("settlement_report")
            if report:
                self.active_room_data = room
                self._open_settlement_page(report)
            else:
                self._output("当前房间尚未结束；房主输入 end 后才会生成结算清单。")
        except Exception as exc:
            self._output(self.renderer.c(f"获取结算清单失败: {self._friendly_error(exc)}", Colors.BRIGHT_RED))

    async def _export_settlement(self, requested_path: Optional[str]) -> None:
        report = self.active_room_data.get("settlement_report") if self.active_room_data else None
        if not report:
            self._output("当前没有可导出的结算清单。")
            return
        target = Path(requested_path or f"settlement-{self.active_room_id or 'room'}.txt")
        try:
            target.write_text(self.renderer.render_settlement_report(report) + "\n", encoding="utf-8")
            self._output(f"✓ 结算清单已保存到: {target}")
        except OSError as exc:
            self._output(self.renderer.c(f"保存失败: {exc}", Colors.BRIGHT_RED))

    def _merge_settlement_report(self, report: Dict[str, Any]) -> None:
        if self.active_room_data is None:
            self.active_room_data = {"room_id": self.active_room_id, "settlement_report": report}
        else:
            self.active_room_data["settlement_report"] = report
            self.active_room_data["is_ended"] = True

    def _open_settlement_page(self, report: Dict[str, Any]) -> None:
        """Open the final bill as a first-class CLI page."""

        self._output(
            self.renderer.render_settlement_report(report),
            panel=True,
            panel_title="终局结算",
            panel_kind="settlement",
        )

    # ------------------ WebSocket Event Handlers ------------------

    async def _on_ws_room_state(self, data: Dict[str, Any]) -> None:
        self.active_room_data = data
        report = data.get("settlement_report") if data.get("is_ended") else None
        async with self._render_lock:
            if self.tui.active:
                if isinstance(report, dict):
                    self._open_settlement_page(report)
                else:
                    self._tui_panel = None
                    self._tui_panel_title = ""
                    self._tui_panel_kind = None
                    self._refresh_tui()
            elif self.renderer.mode == "dashboard":
                self.renderer.clear_screen()
                if isinstance(report, dict):
                    self._output(self.renderer.render_settlement_report(report), panel=True)
                else:
                    self._output(self.renderer.render_table_dashboard(data, self._current_user_id()))
            else:
                stream_log = self.renderer.render_stream_event("ROOM_STATE", data, self._current_user_id())
                if stream_log:
                    self._output("\n" + stream_log)
                if isinstance(report, dict):
                    self._output("\n" + self.renderer.render_settlement_report(report), panel=True)
            if self._in_room and not self._closing_room and not self.tui.active:
                self._write_prompt("牌桌> ")

    async def _on_ws_action_event(self, data: Dict[str, Any]) -> None:
        if self.renderer.mode == "stream":
            line = self.renderer.render_stream_event("ACTION_EVENT", data, self._current_user_id())
            if line:
                self._output("\n" + line)
                self._write_prompt("牌桌> ")

    async def _on_ws_sound_effect(self, sound: str, extra: Dict[str, Any]) -> None:
        sound_map = {
            "deal": "🃏 发牌",
            "check": "👌 过牌",
            "call": "📞 跟注",
            "bet": "🪙 下注",
            "raise": "🚀 加注",
            "fold": "❌ 弃牌",
            "allin": "🔥 全下",
            "win_pot": "🏆 收池",
            "time_card": "⏱️ 使用时间卡",
            "time_card_gain": "⏱️ 获得时间卡",
            "rebuy": "💰 重买",
        }
        player_id = extra.get("player_id") if isinstance(extra, dict) else None
        note = f" · {player_id}" if player_id else ""
        line = f"[HPoker] {sound_map.get(sound, sound)}{note}"
        if self.renderer.mode == "stream":
            self._output("\n" + line)
            self._write_prompt("牌桌> ")
        elif self.tui.active:
            self._output(line)

    async def _on_ws_settlement_report(self, data: Dict[str, Any]) -> None:
        report = data.get("report") if isinstance(data, dict) and isinstance(data.get("report"), dict) else data
        if isinstance(report, dict):
            self._merge_settlement_report(report)
            if self.renderer.mode == "stream":
                self._output("\n" + self.renderer.render_settlement_report(report), panel=True)
                self._write_prompt("牌桌> ")
            elif self.tui.active:
                self._open_settlement_page(report)

    async def _on_ws_room_deleted(self, data: Dict[str, Any]) -> None:
        message = data.get("message", "房间已被解散") if isinstance(data, dict) else "房间已被解散"
        self._output(self.renderer.c(f"[房间已关闭] {message}", Colors.BRIGHT_YELLOW))
        self._room_deleted = True
        self._in_room = False
        self.tui.cancel_read("")

    async def _on_ws_error(self, msg: str) -> None:
        self._output(self.renderer.c(f"[服务器提示] {msg}", Colors.BRIGHT_RED))
        if self._in_room:
            self._write_prompt("牌桌> ")

    async def _on_ws_disconnect(self) -> None:
        if self._closing_room or self._room_deleted:
            return
        self._connection_lost = True
        self._output(self.renderer.c("[连接已断开] 输入 reconnect 重连，或 leave 返回大厅。", Colors.BRIGHT_YELLOW))
        self._write_prompt("断线> ")

    # ------------------ State / Input Helpers ------------------

    async def _redraw_room(self) -> None:
        if not self.active_room_data:
            self._output("尚未收到房间状态。")
            return
        if self.tui.active:
            self._tui_panel = None
            self._refresh_tui()
            return
        if self.renderer.mode == "dashboard":
            self.renderer.clear_screen()
        self._output(self.renderer.render_table_dashboard(self.active_room_data, self._current_user_id()))

    async def _read_command(self, prompt: str) -> Optional[CliCommand]:
        line = await self._async_input(prompt)
        if self._stdin_closed:
            return None
        # ``None`` is reserved for EOF.  An empty Enter is a valid no-op and
        # must return to the command prompt instead of closing the loop.
        if not line.strip():
            return CliCommand(name="", raw="")
        try:
            return parse_command(line) or CliCommand(name="", raw="")
        except CommandParseError as exc:
            self._output(self.renderer.c(str(exc), Colors.BRIGHT_RED))
            return CliCommand(name="", raw="")

    async def _prompt_text(self, prompt: str, default: str) -> Optional[str]:
        value = await self._async_input(prompt)
        if self._stdin_closed:
            return None
        return value.strip() or default

    async def _prompt_number(
        self,
        prompt: str,
        default: Any,
        parser: Any,
        minimum: float,
        maximum: Optional[float],
    ) -> Optional[Any]:
        while True:
            value = await self._async_input(prompt)
            if self._stdin_closed:
                return None
            raw = value.strip()
            if not raw:
                return default
            try:
                parsed = parser(raw)
                if parsed < minimum or (maximum is not None and parsed > maximum):
                    raise ValueError
                return parsed
            except ValueError:
                range_text = f"{minimum}~{maximum}" if maximum is not None else f">={minimum}"
                self._output(f"请输入有效数字（{range_text}）。")

    def _write_prompt(self, prompt: str) -> None:
        if self._closing_room or self._stdin_closed:
            return
        if self.tui.active:
            self._tui_prompt = prompt
            self._refresh_tui()
            self._prompt_displayed = True
            return
        sys.stdout.write(prompt)
        sys.stdout.flush()
        self._prompt_displayed = True

    async def _async_input(self, prompt: str = "") -> str:
        """Read stdin without blocking the event loop, with EOF detection."""

        if self.tui.active:
            self._tui_prompt = prompt
            try:
                line = await self.tui.read_line(prompt, self.command_history)
            finally:
                self.tui.clear_input()
            if getattr(self.tui, "eof_requested", False):
                self._stdin_closed = True
            self._tui_panel = None
            self._refresh_tui()
            return line

        if prompt and not self._prompt_displayed:
            sys.stdout.write(prompt)
            sys.stdout.flush()
        self._prompt_displayed = False
        loop = asyncio.get_running_loop()
        line = await loop.run_in_executor(None, sys.stdin.readline)
        if line == "":
            self._stdin_closed = True
            return ""
        return line.rstrip("\n")

    async def _async_password_input(self, prompt: str = "密码: ") -> str:
        loop = asyncio.get_running_loop()
        if sys.stdin.isatty():
            import getpass

            return await loop.run_in_executor(None, getpass.getpass, prompt)
        return (await self._async_input(prompt)).strip()

    def _set_mode(self, mode: Optional[str]) -> None:
        if not mode:
            mode = "stream" if self.renderer.mode == "dashboard" else "dashboard"
        mode = mode.lower()
        if mode not in {"dashboard", "stream"}:
            self._output("模式只能是 dashboard 或 stream。")
            return
        self.renderer.mode = mode
        if mode == "dashboard":
            self._begin_tui("room" if self._in_room else "lobby")
        elif self.tui.active:
            self._end_tui()
        self._output(f"已切换为 {mode} 模式。")

    def _set_color(self, value: Optional[str]) -> None:
        if value:
            value = value.lower()
            if value in {"on", "yes", "true", "1"}:
                self.renderer.enable_color = True
            elif value in {"off", "no", "false", "0"}:
                self.renderer.enable_color = False
            else:
                self._output("color 用法: color on 或 color off")
                return
        else:
            self.renderer.enable_color = not self.renderer.enable_color
        self._output(f"终端颜色已{'开启' if self.renderer.enable_color else '关闭'}。")

    def _get_legal_actions(self) -> Dict[str, Any]:
        if not self.active_room_data:
            return {}
        raw = self.active_room_data.get("table", {}).get("legal_actions") or {}
        actions = dict(raw)
        if "min_raise_to" not in actions:
            actions["min_raise_to"] = actions.get("min_raise", 0)
        if "max_raise_to" not in actions:
            actions["max_raise_to"] = actions.get("max_raise", 0)
        if "min_raise" not in actions:
            actions["min_raise"] = actions.get("min_raise_to", 0)
        if "max_raise" not in actions:
            actions["max_raise"] = actions.get("max_raise_to", 0)
        return actions

    def _get_my_seat_index(self) -> Optional[int]:
        if not self.active_room_data:
            return None
        seats = self.active_room_data.get("table", {}).get("seats", [])
        user_id = self._current_user_id()
        for index, seat in enumerate(seats):
            if seat and seat.get("player_id") == user_id:
                return index
        return None

    def _get_my_seat(self) -> Optional[Dict[str, Any]]:
        index = self._get_my_seat_index()
        if index is None or not self.active_room_data:
            return None
        seats = self.active_room_data.get("table", {}).get("seats", [])
        return seats[index] if index < len(seats) else None

    def _is_host(self) -> bool:
        return bool(self.active_room_data and self.active_room_data.get("host_player_id") == self._current_user_id())

    def _current_user_id(self) -> str:
        return str(self.current_user.get("user_id", "")) if self.current_user else ""

    @staticmethod
    def _as_int(value: Any, default: int = 0) -> int:
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _parse_positive_int(value: str, default: int) -> int:
        try:
            parsed = int(value)
            return parsed if parsed > 0 else default
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _parse_nonnegative_int(value: str) -> Optional[int]:
        try:
            parsed = int(value)
            return parsed if parsed >= 0 else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _parse_raw_number(value: Optional[str]) -> Optional[float]:
        if not value:
            return None
        cleaned = value.strip().replace(",", "")
        if cleaned.startswith(("¥", "$")):
            cleaned = cleaned[1:]
        if not re.fullmatch(r"\d+(?:\.\d+)?", cleaned):
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None

    @staticmethod
    def _friendly_error(exc: Exception) -> str:
        if isinstance(exc, PokerApiError):
            return str(exc)
        if isinstance(exc, (ConnectionError, OSError, TimeoutError)):
            return "网络连接失败，请检查服务地址或输入 reconnect 重试"
        return str(exc) or exc.__class__.__name__
