"""CLI Controller managing user session, game loop, and user commands."""

from __future__ import annotations
import asyncio
import re
import sys
from typing import Any, Dict, List, Optional

from cli.api_client import PokerApiClient
from cli.ws_client import PokerWsClient
from cli.ui_renderer import PokerUiRenderer, Colors


class PokerCliController:
    """Coordinates API interactions, WebSocket events, and terminal user commands."""

    def __init__(
        self,
        server_url: str = "http://127.0.0.1:8000",
        username: Optional[str] = None,
        password: str = "123",
        mode: str = "dashboard",
        enable_color: bool = True,
    ):
        self.server_url = server_url.rstrip("/")
        self.default_username = username
        self.default_password = password
        self.api = PokerApiClient(base_url=self.server_url)
        self.renderer = PokerUiRenderer(enable_color=enable_color, mode=mode)

        self.current_user: Optional[Dict[str, Any]] = None
        self.auth_token: Optional[str] = None

        self.active_room_id: Optional[str] = None
        self.active_room_data: Optional[Dict[str, Any]] = None
        self.ws_client: Optional[PokerWsClient] = None

        self._in_room = False
        self._need_render = False
        self._render_lock = asyncio.Lock()
        self._last_rendered_hand_state = None

    # ------------------ Authentication Flow ------------------

    async def login_flow(self) -> bool:
        """Manual username and password login."""
        # 1. If username was provided via CLI argument
        if self.default_username:
            pwd = self.default_password or "123"
            try:
                res = await self.api.login(self.default_username, pwd)
                self.auth_token = res["token"]
                self.current_user = res["user"]
                print(f"✓ 登录成功: {self.current_user['nickname']} ({self.current_user['username']})")
                return True
            except Exception as e:
                print(f"✗ 指定用户 {self.default_username} 登录失败: {e}")

        # 2. Interactive manual username and password input
        while True:
            print("\n" + self.renderer.c("=" * 60, Colors.CYAN))
            print(self.renderer.c("  HPoker 终端客户端 - 用户登录", Colors.BOLD + Colors.BRIGHT_WHITE))
            print(self.renderer.c("=" * 60, Colors.CYAN))

            uname = (await self._async_input("请输入用户名 (输入 q 退出): ")).strip()
            if not uname:
                continue

            if uname.lower() in ("q", "quit", "exit"):
                return False

            pwd = await self._async_password_input("请输入密码: ")

            try:
                res = await self.api.login(uname, pwd)
                self.auth_token = res["token"]
                self.current_user = res["user"]
                print(self.renderer.c(f"✓ 登录成功！欢迎回来，{self.current_user['nickname']}", Colors.BRIGHT_GREEN + Colors.BOLD))
                await asyncio.sleep(0.5)
                return True
            except Exception as err:
                print(self.renderer.c(f"✗ 登录失败: 用户名或密码错误 ({err})", Colors.BRIGHT_RED))
                print("请重新输入。")

    # ------------------ Lobby Loop ------------------

    async def run_lobby_loop(self):
        """Main lobby interactive loop."""
        while self.current_user:
            try:
                rooms = await self.api.list_rooms()
            except Exception as e:
                print(f"获取房间列表失败: {e}")
                rooms = []

            # Display lobby
            if self.renderer.mode == "dashboard":
                self.renderer.clear_screen()
            print(self.renderer.render_lobby(self.current_user, rooms, self.server_url))

            cmd = (await self._async_input("大厅命令 > ")).strip()
            if not cmd:
                continue

            parts = cmd.split()
            main_cmd = parts[0].lower()

            if main_cmd in ("q", "quit", "exit"):
                print("再见！祝游戏愉快！")
                break

            elif main_cmd in ("r", "refresh", "list"):
                continue

            elif main_cmd in ("user", "switch", "login"):
                await self.login_flow()
                continue

            elif main_cmd.isdigit():
                idx = int(main_cmd)
                if 1 <= idx <= len(rooms):
                    target_room_id = rooms[idx - 1]["room_id"]
                    await self.enter_room(target_room_id)
                else:
                    print("无效的房间序号！")
                    await asyncio.sleep(1)

            elif main_cmd in ("j", "join"):
                if len(parts) > 1:
                    r_id = parts[1]
                    await self.enter_room(r_id)
                else:
                    r_id = (await self._async_input("请输入房间ID: ")).strip()
                    if r_id:
                        await self.enter_room(r_id)

            elif main_cmd in ("c", "create", "new"):
                await self.create_room_flow()

            else:
                print(f"未知指令 '{cmd}'，输入 [help] 或直接输入房间序号。")
                await asyncio.sleep(1)

    async def create_room_flow(self):
        """Interactive room creation with sensible defaults."""
        print("\n" + self.renderer.c("--- 创建德州扑克现金桌 (直接按回车使用默认配置) ---", Colors.BOLD + Colors.CYAN))
        default_name = f"{self.current_user['nickname']}的局"
        name = (await self._async_input(f"房间名称 [{default_name}]: ")).strip() or default_name

        buyin_str = (await self._async_input("买入筹码 [1000]: ")).strip()
        buyin = int(buyin_str) if buyin_str.isdigit() else 1000

        cash_str = (await self._async_input("折合现金(元) [100.0]: ")).strip()
        try:
            cash = float(cash_str) if cash_str else 100.0
        except ValueError:
            cash = 100.0

        sb_str = (await self._async_input("小盲注(SB) [10]: ")).strip()
        sb = int(sb_str) if sb_str.isdigit() else 10

        timeout_str = (await self._async_input("操作思考超时(秒) [15]: ")).strip()
        timeout = int(timeout_str) if timeout_str.isdigit() else 15

        seats_str = (await self._async_input("座位数 (2~9) [6]: ")).strip()
        max_seats = int(seats_str) if seats_str.isdigit() and 2 <= int(seats_str) <= 9 else 6

        try:
            room_data = await self.api.create_room(
                host_player_id=self.current_user["user_id"],
                room_name=name,
                buyin_chips=buyin,
                cash_value=cash,
                small_blind=sb,
                action_timeout=timeout,
                max_seats=max_seats,
            )
            print(f"✓ 房间创建成功！ID: {room_data['room_id']}")
            await asyncio.sleep(0.5)
            await self.enter_room(room_data["room_id"])
        except Exception as e:
            print(f"✗ 创建房间失败: {e}")
            await asyncio.sleep(1.5)

    # ------------------ Room Gameplay Flow ------------------

    async def enter_room(self, room_id: str):
        """Connect to room and start in-game command loop."""
        self.active_room_id = room_id
        self._in_room = True

        ws_proto = "wss" if self.server_url.startswith("https") else "ws"
        host = self.server_url.split("://")[1]
        ws_url = f"{ws_proto}://{host}/ws/{room_id}/{self.current_user['user_id']}"

        self.ws_client = PokerWsClient(ws_url=ws_url)
        self.ws_client.on_room_state = self._on_ws_room_state
        self.ws_client.on_sound_effect = self._on_ws_sound_effect
        self.ws_client.on_error = self._on_ws_error
        self.ws_client.on_disconnect = self._on_ws_disconnect

        print(f"正在连接房间 {room_id} ...")
        try:
            await self.ws_client.connect()
        except Exception as e:
            print(f"✗ 无法连接到房间: {e}")
            self._in_room = False
            self.active_room_id = None
            await asyncio.sleep(1.5)
            return

        # Start game command input loop
        try:
            await self._in_room_input_loop()
        finally:
            self._in_room = False
            if self.ws_client:
                await self.ws_client.disconnect()
                self.ws_client = None
            self.active_room_id = None
            self.active_room_data = None

    async def _on_ws_room_state(self, data: Dict[str, Any]):
        """WebSocket ROOM_STATE handler."""
        self.active_room_data = data
        async with self._render_lock:
            if self.renderer.mode == "dashboard":
                self.renderer.clear_screen()
                out = self.renderer.render_table_dashboard(data, self.current_user["user_id"])
                print(out)
                sys.stdout.write("> ")
                sys.stdout.flush()
            else:
                stream_log = self.renderer.render_stream_event("ROOM_STATE", data, self.current_user["user_id"])
                if stream_log:
                    print("\n" + stream_log)
                    sys.stdout.write("> ")
                    sys.stdout.flush()

    async def _on_ws_sound_effect(self, sound: str, extra: Dict[str, Any]):
        """WebSocket SOUND_EFFECT handler."""
        if self.renderer.mode == "stream":
            sound_map = {
                "deal": "🃏 发牌",
                "check": "👌 过牌 (Check)",
                "call": "📞 跟注 (Call)",
                "raise": "🚀 加注 (Raise)",
                "fold": "❌ 弃牌 (Fold)",
                "allin": "🔥 全下 (All-in)!",
                "win_pot": "🏆 收池获胜",
                "time_card": "⏱️ 使用了时间卡 (+30s)",
                "rebuy": "💰 重新买入筹码",
            }
            s_name = sound_map.get(sound, sound)
            p_id = extra.get("player_id")
            p_note = f" (玩家: {p_id})" if p_id else ""
            print(f"[HPoker 音效] {s_name}{p_note}")
            sys.stdout.write("> ")
            sys.stdout.flush()

    async def _on_ws_error(self, msg: str):
        print(f"\n[提示] {msg}")
        sys.stdout.write("> ")
        sys.stdout.flush()

    async def _on_ws_disconnect(self):
        if self._in_room:
            print("\n[连接已断开] 正在退出房间...")
            self._in_room = False

    async def _in_room_input_loop(self):
        """In-room command dispatcher."""
        while self._in_room and self.ws_client and self.ws_client.is_connected:
            cmd = (await self._async_input("")).strip()
            if not cmd:
                continue

            parts = cmd.split()
            main_cmd = parts[0].lower()

            if main_cmd in ("leave", "back", "lobby", "exit"):
                print("正在离开房间...")
                break

            elif main_cmd in ("help", "h", "?"):
                self._print_in_game_help()
                continue

            elif main_cmd in ("clear", "cls", "r", "refresh"):
                if self.active_room_data:
                    await self._on_ws_room_state(self.active_room_data)
                continue

            elif main_cmd == "mode":
                # Toggle Dashboard / Stream
                self.renderer.mode = "stream" if self.renderer.mode == "dashboard" else "dashboard"
                print(f"已切换为: {'仪表盘 (Dashboard)' if self.renderer.mode == 'dashboard' else '极简日志流 (Stream)'} 模式")
                if self.active_room_data and self.renderer.mode == "dashboard":
                    await self._on_ws_room_state(self.active_room_data)
                continue

            elif main_cmd == "color":
                self.renderer.enable_color = not self.renderer.enable_color
                print(f"终端色彩已{'开启' if self.renderer.enable_color else '关闭'}")
                continue

            elif main_cmd in ("ready", "rd"):
                await self.ws_client.player_ready(True)

            elif main_cmd in ("unready", "unrd"):
                await self.ws_client.player_ready(False)

            elif main_cmd in ("start", "s"):
                await self.ws_client.start_game()

            elif main_cmd in ("rebuy", "rb", "buyin"):
                await self.ws_client.rebuy()

            elif main_cmd in ("sit", "seat"):
                if len(parts) > 1 and parts[1].isdigit():
                    s_idx = int(parts[1])
                    await self.ws_client.sit_down(s_idx)
                else:
                    print("用法: sit <座位号 0~5>")

            elif main_cmd in ("stand", "standup"):
                s_idx = self._get_my_seat_index()
                if s_idx is not None:
                    await self.ws_client.stand_up(s_idx)
                else:
                    print("你当前未入座。")

            # Game Actions
            elif main_cmd in ("c", "check", "call"):
                # Determine CHECK or CALL based on legal actions
                la = self._get_legal_actions()
                if la.get("can_check"):
                    await self.ws_client.player_action("CHECK", 0)
                elif la.get("can_call"):
                    amt = la.get("call_amount", 0)
                    await self.ws_client.player_action("CALL", amt)
                else:
                    print("当前不可过牌或跟注！")

            elif main_cmd in ("f", "fold"):
                await self.ws_client.player_action("FOLD", 0)

            elif main_cmd in ("a", "allin", "ai"):
                la = self._get_legal_actions()
                allin_amt = la.get("all_in_amount", 0)
                await self.ws_client.player_action("ALL_IN", allin_amt)

            elif main_cmd in ("r", "raise", "b", "bet"):
                await self._handle_raise_command(parts)

            elif main_cmd in ("tc", "time", "timecard"):
                await self.ws_client.use_time_card()

            elif main_cmd == "rit":
                if len(parts) > 1 and parts[1] in ("1", "2"):
                    choice = int(parts[1])
                    await self.ws_client.rit_choice(choice)
                else:
                    print("用法: rit 1 (发1次) 或 rit 2 (发2次)")

            # Show / Muck
            elif main_cmd in ("show", "s1", "s2", "sa", "muck", "hide"):
                await self._handle_show_command(main_cmd, parts)

            # End room & Settlements
            elif main_cmd in ("end", "endroom"):
                if not self.active_room_data or self.active_room_data.get("host_player_id") != self.current_user["user_id"]:
                    print("只有房主可以结束房间！")
                    continue
                confirm = (await self._async_input("确定要结束房间并生成结算清单吗？(y/n): ")).strip().lower()
                if confirm in ("y", "yes"):
                    await self.ws_client.end_room()

            elif main_cmd in ("bill", "report", "settlement"):
                if self.active_room_data and self.active_room_data.get("settlement_report"):
                    rep = self.active_room_data["settlement_report"]
                    print(self.renderer.render_settlement_report(rep))
                else:
                    print("当前房间尚未生成结算清单 (房主输入 [end] 即可结束并结算)。")

            else:
                print(f"未知指令 '{cmd}'，输入 [help] 查看帮助。")

    # ------------------ Action Parsing Helpers ------------------

    async def _handle_raise_command(self, parts: List[str]):
        """Parse raise amount with smart pot fraction calculations."""
        la = self._get_legal_actions()
        can_bet = la.get("can_bet", False)
        can_raise = la.get("can_raise", False)

        if not can_bet and not can_raise:
            print("当前不可下注或加注！")
            return

        act_type = "BET" if can_bet else "RAISE"
        min_amt = la.get("min_bet" if can_bet else "min_raise", 0)
        max_amt = la.get("max_bet" if can_bet else "max_raise", 0)
        total_pot = self.active_room_data.get("table", {}).get("total_pot", 0)

        if len(parts) == 1:
            print(f"用法: r <金额或比例>，例如: r {min_amt} / r 0.5p / r 2/3p / r 1p / r all")
            return

        arg = parts[1].lower()

        # Parse pot shortcut: e.g. "0.5p", "1/2p", "2/3p", "1p", "pot", "half", "all"
        target_amt = None
        if arg in ("all", "max"):
            target_amt = max_amt
        elif arg in ("pot", "1p"):
            target_amt = max(min_amt, total_pot)
        elif arg in ("half", "0.5p", "1/2p", "1/2"):
            target_amt = max(min_amt, int(total_pot * 0.5))
        elif arg in ("0.33p", "1/3p", "1/3"):
            target_amt = max(min_amt, int(total_pot * 0.333))
        elif arg in ("0.67p", "2/3p", "2/3"):
            target_amt = max(min_amt, int(total_pot * 0.667))
        elif arg.endswith("p"):
            try:
                frac = float(arg[:-1])
                target_amt = max(min_amt, int(total_pot * frac))
            except ValueError:
                pass
        elif arg.isdigit():
            target_amt = int(arg)

        if target_amt is None:
            print(f"无法识别的下注额度: {arg}")
            return

        # Bound check
        if target_amt < min_amt:
            print(f"下注金额小于最小下注额 {min_amt}，已自动调整为 {min_amt}")
            target_amt = min_amt
        elif target_amt > max_amt:
            print(f"下注金额大于最大筹码 {max_amt}，已自动调整为全下 {max_amt}")
            target_amt = max_amt

        await self.ws_client.player_action(act_type, target_amt)

    async def _handle_show_command(self, main_cmd: str, parts: List[str]):
        """Handle card showing / mucking options."""
        if main_cmd == "s1" or (len(parts) > 1 and parts[1] == "1"):
            await self.ws_client.show_card(card_index=0)
            print("✓ 已亮出左侧第 1 张手牌")
        elif main_cmd == "s2" or (len(parts) > 1 and parts[1] == "2"):
            await self.ws_client.show_card(card_index=1)
            print("✓ 已亮出右侧第 2 张手牌")
        elif main_cmd in ("sa", "showall") or (len(parts) > 1 and parts[1] in ("all", "a")):
            await self.ws_client.show_card(show_all=True)
            print("✓ 已亮出全部手牌")
        elif main_cmd in ("muck", "hide") or (len(parts) > 1 and parts[1] in ("hide", "none", "muck")):
            await self.ws_client.show_card(hide_all=True)
            print("✓ 已盖牌")
        else:
            print("亮牌指令: show 1 (亮左牌) | show 2 (亮右牌) | show all (全亮) | muck (盖牌)")

    def _get_legal_actions(self) -> Dict[str, Any]:
        """Fetch legal action dict for current user."""
        if not self.active_room_data:
            return {}
        table = self.active_room_data.get("table", {})
        return table.get("legal_actions") or {}

    def _get_my_seat_index(self) -> Optional[int]:
        """Find seat index of current player."""
        if not self.active_room_data or not self.current_user:
            return None
        seats = self.active_room_data.get("table", {}).get("seats", [])
        for idx, s in enumerate(seats):
            if s and s.get("player_id") == self.current_user["user_id"]:
                return idx
        return None

    def _print_in_game_help(self):
        """Print detailed help manual for terminal gameplay."""
        print("\n" + self.renderer.c("==================== HPoker 终端操作指南 ====================", Colors.BOLD + Colors.CYAN))
        print("  【牌局行动指令】 (在轮到你的回合时直接输入):")
        print("    • " + self.renderer.c("c", Colors.BRIGHT_GREEN) + " 或 " + self.renderer.c("check", Colors.BRIGHT_GREEN) + " / " + self.renderer.c("call", Colors.BRIGHT_GREEN) + "       : 智能 过牌 或 跟注")
        print("    • " + self.renderer.c("f", Colors.BRIGHT_RED) + " 或 " + self.renderer.c("fold", Colors.BRIGHT_RED) + "               : 弃牌 (Fold)")
        print("    • " + self.renderer.c("r <数值>", Colors.BRIGHT_YELLOW) + " / " + self.renderer.c("b <数值>", Colors.BRIGHT_YELLOW) + "        : 下注/加注指定筹码数 (如: r 40)")
        print("    • " + self.renderer.c("r 0.5p", Colors.BRIGHT_YELLOW) + " / " + self.renderer.c("r 2/3p", Colors.BRIGHT_YELLOW) + " / " + self.renderer.c("r 1p", Colors.BRIGHT_YELLOW) + " : 智能比例加注 (0.5池, 2/3池, 1满池)")
        print("    • " + self.renderer.c("a", Colors.BRIGHT_MAGENTA) + " 或 " + self.renderer.c("allin", Colors.BRIGHT_MAGENTA) + "             : 全下 (All-in)")
        print("    • " + self.renderer.c("tc", Colors.CYAN) + " 或 " + self.renderer.c("time", Colors.CYAN) + "               : 消耗 1 张时间卡 (+30s思考时间)")
        print("")
        print("  【局间与秀牌指令】:")
        print("    • " + self.renderer.c("ready", Colors.BRIGHT_GREEN) + " 或 " + self.renderer.c("rd", Colors.BRIGHT_GREEN) + "           : 准备 / 取消准备")
        print("    • " + self.renderer.c("start", Colors.BRIGHT_GREEN) + " 或 " + self.renderer.c("s", Colors.BRIGHT_GREEN) + "            : 开始新手牌 (仅房主)")
        print("    • " + self.renderer.c("rebuy", Colors.BRIGHT_YELLOW) + " 或 " + self.renderer.c("rb", Colors.BRIGHT_YELLOW) + "          : 重买补充初始买入筹码")
        print("    • " + self.renderer.c("show 1", Colors.WHITE) + " / " + self.renderer.c("show 2", Colors.WHITE) + " / " + self.renderer.c("show all", Colors.WHITE) + " : 亮出第1张/第2张/全部手牌")
        print("    • " + self.renderer.c("muck", Colors.DIM) + " 或 " + self.renderer.c("hide", Colors.DIM) + "            : 盖牌不秀")
        print("    • " + self.renderer.c("rit 1", Colors.BRIGHT_MAGENTA) + " / " + self.renderer.c("rit 2", Colors.BRIGHT_MAGENTA) + "         : 多次发牌投票 (发1次 / 发2次)")
        print("")
        print("  【房间管理与视图】:")
        print("    • " + self.renderer.c("end", Colors.BRIGHT_RED) + " 或 " + self.renderer.c("endroom", Colors.BRIGHT_RED) + "           : 结束房间并生成清算账单 (仅房主)")
        print("    • " + self.renderer.c("bill", Colors.BRIGHT_GREEN) + " 或 " + self.renderer.c("report", Colors.BRIGHT_GREEN) + "         : 查看终局结算转账清单")
        print("    • " + self.renderer.c("mode", Colors.CYAN) + "                    : 切换 仪表盘(Dashboard) / 极简日志流(Stream) 模式")
        print("    • " + self.renderer.c("leave", Colors.YELLOW) + " 或 " + self.renderer.c("back", Colors.YELLOW) + "           : 离开房间返回大厅")
        print("    • " + self.renderer.c("clear", Colors.WHITE) + " / " + self.renderer.c("r", Colors.WHITE) + "              : 清屏并重新绘制当前牌局")
        print(self.renderer.c("================================================================", Colors.BOLD + Colors.CYAN) + "\n")

    # ------------------ Async Helper ------------------

    async def _async_input(self, prompt: str = "") -> str:
        """Asynchronously read a line from standard input."""
        if prompt:
            sys.stdout.write(prompt)
            sys.stdout.flush()
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, sys.stdin.readline)

    async def _async_password_input(self, prompt: str = "请输入密码: ") -> str:
        """Asynchronously read password (hidden if tty available)."""
        loop = asyncio.get_running_loop()
        if sys.stdin.isatty():
            import getpass
            return await loop.run_in_executor(None, getpass.getpass, prompt)
        else:
            return (await self._async_input(prompt)).strip()
