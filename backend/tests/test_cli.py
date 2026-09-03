"""Comprehensive Unit Tests for Poker CLI Client."""

import asyncio
import io
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from cli.api_client import PokerApiClient
from cli.main import parse_args
from cli.ws_client import PokerWsClient
from cli.ui_renderer import PokerUiRenderer, Colors
from cli.controller import PokerCliController
from cli.tui import TerminalTui
from cli.textual_app import PokerTextualApp
from cli.text_utils import display_width
from cli.commands import (
    BetSizingContext,
    CommandParseError,
    command_alias_conflicts,
    command_specs,
    normalize_command,
    parse_command,
    resolve_bet_amount,
)
from backend.app.services.user_manager import user_manager
from backend.app.services.room_manager import room_manager
from backend.app.models.room import RoomConfig


def test_cli_command_parser_and_bet_sizing():
    command = parse_command('create "Friday cash game" --buyin 2000')
    assert command is not None
    assert command.name == "create"
    assert command.args == ("Friday cash game", "--buyin", "2000")
    assert parse_command("r1").args == ("1",)
    assert parse_command("r0.5").args == ("0.5",)
    assert parse_command("r200").args == ("200",)

    with pytest.raises(CommandParseError):
        parse_command('create "unfinished')

    context = BetSizingContext(
        pot=200,
        minimum=40,
        maximum=1000,
        small_blind=10,
        current_round_bet=0,
        current_highest_bet=40,
    )
    assert resolve_bet_amount("1/3p", context) == 70
    assert resolve_bet_amount("2/3p", context) == 130
    assert resolve_bet_amount("3bb", context) == 60
    assert resolve_bet_amount("+1bb", context) == 60
    assert resolve_bet_amount("0.5", context) == 100
    assert resolve_bet_amount("1", context) == 200
    assert resolve_bet_amount("2", context) == 400
    assert resolve_bet_amount("5", context) == 40
    assert resolve_bet_amount("all-in", context) == 1000
    assert resolve_bet_amount(None, context) == 40
    assert resolve_bet_amount("not-an-amount", context) is None


def test_cli_commands_use_one_scope_aware_registry():
    lobby_create = normalize_command(parse_command("c"), "lobby")
    room_check = normalize_command(parse_command("c"), "room")
    lobby_refresh = normalize_command(parse_command("r"), "lobby")
    room_raise = normalize_command(parse_command("r 1/2p"), "room")
    compact_raise = normalize_command(parse_command("r0.5"), "room")

    assert lobby_create.name == "create"
    assert room_check.name == "check"
    assert lobby_refresh.name == "rooms"
    assert room_raise.name == "raise"
    assert room_raise.args == ("1/2p",)
    assert compact_raise.name == "raise"
    assert compact_raise.args == ("0.5",)
    assert normalize_command(parse_command("s1"), "room").args == ("1",)
    assert normalize_command(parse_command("muck"), "room").args == ("muck",)
    assert any(spec.name == "raise" and "r" in spec.aliases for spec in command_specs("room"))
    assert all(spec.name != "stand" for spec in command_specs("room"))

    for scope in ("lobby", "room"):
        assert command_alias_conflicts(scope) == {}
        for token in ("q", "quit", "exit"):
            assert normalize_command(parse_command(token), scope).name == "quit"
        for token in ("h", "help", "?"):
            assert normalize_command(parse_command(token), scope).name == "help"
        assert normalize_command(parse_command("view"), scope).name == "mode"
        assert normalize_command(parse_command("status"), scope).name == "info"
        assert normalize_command(parse_command("redraw"), scope).name == "refresh"
        assert normalize_command(parse_command("userlist"), scope).name == "users"

    for token in ("leave", "back", "lobby"):
        assert normalize_command(parse_command(token), "room").name == "leave"
    assert normalize_command(parse_command("exit"), "room").name != "leave"

    lobby_tokens = {token: spec.name for spec in command_specs("lobby") for token in spec.tokens}
    room_tokens = {token: spec.name for spec in command_specs("room") for token in spec.tokens}
    semantic_mismatches = {
        token: (lobby_tokens[token], room_tokens[token])
        for token in lobby_tokens.keys() & room_tokens.keys()
        if lobby_tokens[token] != room_tokens[token]
    }
    assert semantic_mismatches == {"c": ("create", "check"), "r": ("rooms", "raise")}
    assert normalize_command(parse_command("show"), "lobby").name == "show"
    assert normalize_command(parse_command("show"), "room").name == "show"


@pytest.mark.asyncio
async def test_global_quit_has_same_semantics_in_lobby_and_room():
    lobby = PokerCliController(enable_color=False)
    lobby._output = MagicMock()
    room = PokerCliController(enable_color=False)
    room._output = MagicMock()
    room._in_room = True

    try:
        should_continue = await lobby._dispatch_lobby_command(parse_command("q"), [])
        await room._dispatch_room_command(parse_command("exit"))

        assert should_continue is False
        assert lobby._quit_requested is True
        assert room._quit_requested is True
        assert room._in_room is False

        room._quit_requested = False
        room._in_room = True
        await room._dispatch_room_command(parse_command("back"))
        assert room._quit_requested is False
        assert room._in_room is False
    finally:
        await lobby.api.close()
        await room.api.close()


@pytest.mark.asyncio
async def test_global_context_commands_work_in_lobby_and_room():
    controller = PokerCliController(enable_color=False)
    controller._show_users = AsyncMock()
    controller._show_room_info = AsyncMock()
    controller._redraw_room = AsyncMock()
    controller._output = MagicMock()
    controller.active_room_data = {"room_id": "r1", "table": {}}
    rooms = [{"room_id": "r1"}]

    try:
        await controller._dispatch_lobby_command(parse_command("status 1"), rooms)
        controller._show_room_info.assert_awaited_once_with("r1")

        await controller._dispatch_room_command(parse_command("users"))
        controller._show_users.assert_awaited_once()

        await controller._dispatch_room_command(parse_command("clear"))
        controller._redraw_room.assert_awaited_once()
    finally:
        await controller.api.close()


def test_cli_entrypoint_options():
    args = parse_args([
        "--server", "http://poker.test:9000",
        "--user", "fwd",
        "--password", "123",
        "--room", "rm_123",
        "--mode", "stream",
        "--no-color",
        "--http-timeout", "3.5",
        "--reconnect-attempts", "4",
    ])

    assert args.server == "http://poker.test:9000"
    assert args.user == "fwd"
    assert args.password == "123"
    assert args.room == "rm_123"
    assert args.mode == "stream"
    assert args.no_color is True
    assert args.http_timeout == 3.5
    assert args.reconnect_attempts == 4


def test_terminal_tui_replaces_frame_instead_of_appending_lines():
    output = io.StringIO()
    tui = TerminalTui(input_stream=io.StringIO(), output_stream=output)
    tui.active = True

    tui.draw("旧画面", prompt="牌桌> ", input_text="r 1/2p")
    tui.draw("新画面", prompt="牌桌> ", input_text="")

    rendered = output.getvalue()
    assert rendered.count("\033[H") == 2
    assert "\033[1;1H" in rendered
    assert "\033[2;1H" in rendered
    assert "新画面" in rendered
    assert "牌桌> " in rendered
    assert tui._fit_frame(["1", "2", "3", "4", "5"], 3) == ["1", "2", "3"]


@pytest.mark.asyncio
async def test_tui_empty_enter_is_not_eof_but_ctrl_d_is():
    tui = TerminalTui(input_stream=io.StringIO(), output_stream=io.StringIO())
    tui.active = True
    loop = asyncio.get_running_loop()

    tui._read_future = loop.create_future()
    tui._handle_character("\n")
    assert tui._read_future.result() == ""
    assert tui.eof_requested is False

    tui._input_text = ""
    tui._read_future = loop.create_future()
    tui._handle_character("\x04")
    assert tui._read_future.result() == ""
    assert tui.eof_requested is True


@pytest.mark.asyncio
async def test_controller_empty_command_returns_to_prompt():
    controller = PokerCliController(enable_color=False)
    controller._async_input = AsyncMock(return_value="")

    command = await controller._read_command("牌桌> ")

    assert command is not None
    assert command.raw == ""


def test_controller_routes_tui_feedback_to_fixed_footer():
    controller = PokerCliController(enable_color=False)
    controller.tui.active = True
    controller._refresh_tui = MagicMock()

    controller._output("操作已发送")
    assert controller._tui_notice == "操作已发送"
    assert controller._tui_panel is None

    controller._output("帮助第一行\n帮助第二行", panel=True)
    assert controller._tui_panel == "帮助第一行\n帮助第二行"


@pytest.mark.asyncio
async def test_controller_tui_timer_refreshes_room_dashboard_locally():
    controller = PokerCliController(enable_color=False)
    controller.tui.active = True
    controller._in_room = True
    controller._tui_view = "room"
    controller.active_room_data = {"table": {"street": "FLOP", "current_turn_seat": 0}}
    controller._refresh_tui = MagicMock()

    timer_task = asyncio.create_task(controller._tui_timer_loop())
    await asyncio.sleep(0.25)
    controller._in_room = False
    await asyncio.wait_for(timer_task, timeout=1)

    assert controller._refresh_tui.call_count >= 1
    assert all(call.kwargs.get("now") is not None for call in controller._refresh_tui.call_args_list)


@pytest.mark.asyncio
async def test_textual_tui_handles_input_and_responsive_layout():
    controller = PokerCliController(enable_color=False)
    controller.current_user = {"user_id": "u_me", "nickname": "Hero"}
    controller.rooms = []
    controller._tui_view = "lobby"
    app = PokerTextualApp(controller, autostart=False)

    try:
        async with app.run_test(size=(120, 36)) as pilot:
            controller._refresh_tui()
            await pilot.pause()
            assert app.bridge.active is True
            assert app.screen.has_class("narrow") is False
            assert app.screen.has_class("compact") is False

            read_task = asyncio.create_task(app.bridge.read_line("大厅> ", ["rooms"]))
            await pilot.pause()
            await pilot.press("h", "e", "l", "p", "enter")
            assert await asyncio.wait_for(read_task, timeout=1) == "help"

            await pilot.resize_terminal(80, 30)
            await pilot.pause()
            assert app.screen.has_class("narrow") is True
            assert app.screen.has_class("compact") is True
    finally:
        await controller.api.close()


class TestPokerUiRenderer:
    """Tests for terminal UI rendering."""

    def test_card_formatting(self):
        renderer = PokerUiRenderer(enable_color=False, mode="dashboard")
        
        card1 = {"rank": 14, "rank_symbol": "A", "suit": "s", "suit_symbol": "♠", "color": "black"}
        card2 = {"rank": 13, "rank_symbol": "K", "suit": "h", "suit_symbol": "♥", "color": "red"}
        
        assert renderer.format_card(card1) == "[A♠]"
        assert renderer.format_card(card2) == "[K♥]"
        assert renderer.format_cards([card1, card2]) == "[A♠] [K♥]"
        assert renderer.format_cards([]) == "(无)"

    def test_color_card_formatting(self):
        renderer = PokerUiRenderer(enable_color=True, mode="dashboard")
        card = {"rank": 14, "rank_symbol": "A", "suit": "h", "suit_symbol": "♥", "color": "red"}
        formatted = renderer.format_card(card)
        assert "A♥" in formatted
        assert "\033[" in formatted  # ANSI escape code present

    def test_large_cards_and_split_dashboard_sections(self):
        renderer = PokerUiRenderer(enable_color=False, mode="dashboard")
        room_data = {
            "room_id": "r_split",
            "host_player_id": "u_me",
            "config": {"room_name": "深夜牌局", "small_blind": 5, "big_blind": 10},
            "table": {
                "hand_number": 8,
                "street": "FLOP",
                "total_pot": 180,
                "board_cards": [
                    {"rank_symbol": "A", "suit_symbol": "♠"},
                    {"rank_symbol": "10", "suit_symbol": "♥"},
                    {"rank_symbol": "2", "suit_symbol": "♦"},
                ],
                "current_turn_seat": 0,
                "current_turn_duration": 20,
                "turn_started_at": 100.0,
                "seats": [{
                    "player_id": "u_me",
                    "name": "Hero",
                    "chips": 900,
                    "current_round_bet": 20,
                    "hole_cards": [
                        {"rank_symbol": "K", "suit_symbol": "♣"},
                        {"rank_symbol": "K", "suit_symbol": "♦"},
                    ],
                }],
                "legal_actions": {
                    "can_check": True,
                    "can_fold": True,
                    "can_bet": True,
                    "min_bet": 20,
                    "max_bet": 900,
                    "can_all_in": True,
                    "all_in_amount": 900,
                },
                "action_history": [{"player_name": "Hero", "action": "BET", "amount": 20}],
            },
        }

        cards = renderer.format_large_cards(room_data["table"]["board_cards"], slots=5)
        main = renderer.render_table_main(room_data, "u_me")
        sidebar = renderer.render_table_sidebar(room_data, "u_me")
        compact_main = renderer.render_table_main(room_data, "u_me", compact=True)
        compact_sidebar = renderer.render_table_sidebar(room_data, "u_me", compact=True)

        assert len(cards.splitlines()) == 5
        assert all(display_width(line) == 39 for line in cards.splitlines())
        assert "公共牌" in main and "你的手牌" in main
        assert "A" in main and "K" in main
        assert "下注 20~900" in sidebar
        assert "raise 90" in sidebar
        assert "raise 180" in sidebar
        assert "r0.5 / r1" in sidebar
        assert "最近动态" in sidebar
        assert "公共牌  [A♠] [10♥] [2♦]" in compact_main
        assert "手牌    [K♣] [K♦]" in compact_main
        assert "┌─────┐" not in compact_main
        assert len(compact_main.splitlines()) < len(main.splitlines())
        assert "[" not in compact_sidebar  # compact timer omits the progress bar
        assert "快捷  raise 60  raise 90  raise 180" in compact_sidebar
        assert "比例缩写  r0.5 / r1" in compact_sidebar
        assert "快捷命令" not in compact_sidebar

    def test_render_lobby(self):
        renderer = PokerUiRenderer(enable_color=False, mode="dashboard")
        current_user = {"user_id": "u_fwd", "nickname": "fwd", "username": "fwd"}
        rooms = [
            {
                "room_id": "rm123",
                "room_name": "测试房间",
                "config": {"small_blind": 5, "big_blind": 10, "buyin_chips": 1000, "max_seats": 6},
                "seated_players_count": 2,
                "is_ended": False,
            }
        ]
        output = renderer.render_lobby(current_user, rooms)
        assert "HPoker 游戏大厅" in output
        assert "fwd" in output
        assert "rm123" in output
        assert "测试房间" in output
        assert "5/10" in output

    def test_render_table_dashboard(self):
        renderer = PokerUiRenderer(enable_color=False, mode="dashboard")
        room_data = {
            "room_id": "r_test",
            "host_player_id": "u_admin",
            "config": {"room_name": "经典德州现金桌", "small_blind": 5, "big_blind": 10, "action_timeout": 15},
            "is_ended": False,
            "table": {
                "hand_number": 1,
                "street": "FLOP",
                "total_pot": 150,
                "pots": [{"amount": 150}],
                "board_cards": [
                    {"rank_symbol": "A", "suit_symbol": "♠"},
                    {"rank_symbol": "K", "suit_symbol": "♥"},
                    {"rank_symbol": "Q", "suit_symbol": "♦"},
                ],
                "current_turn_seat": 0,
                "current_turn_duration": 20,
                "turn_started_at": 100.0,
                "dealer_seat": 1,
                "sb_seat": 0,
                "bb_seat": 1,
                "seats": [
                    {
                        "player_id": "u_admin",
                        "name": "Admin",
                        "chips": 980,
                        "rebuy_count": 1,
                        "current_round_bet": 10,
                        "is_folded": False,
                        "is_all_in": False,
                        "hole_cards": [{"rank_symbol": "A", "suit_symbol": "♣"}, {"rank_symbol": "A", "suit_symbol": "♦"}],
                        "shown_cards": [],
                        "last_action": "Bet 10",
                        "time_bank_cards": 3,
                    },
                    {
                        "player_id": "u_fwd",
                        "name": "fwd",
                        "chips": 990,
                        "rebuy_count": 1,
                        "current_round_bet": 0,
                        "is_folded": False,
                        "is_all_in": False,
                        "hole_cards": [],
                        "shown_cards": [],
                        "last_action": "Check",
                        "time_bank_cards": 3,
                    },
                ],
                "legal_actions": {
                    "can_check": True,
                    "can_call": False,
                    "can_fold": True,
                    "can_bet": True,
                    "min_bet": 10,
                    "max_bet": 980,
                    "can_all_in": True,
                    "all_in_amount": 980,
                },
                "action_history": [
                    {"player_name": "Admin", "action": "Bet", "amount": 10, "street": "FLOP"}
                ],
            }
        }
        output = renderer.render_table_dashboard(room_data, "u_admin", now=105.0)
        assert "HPoker 现金桌: 经典德州现金桌" in output
        assert "翻牌圈 (Flop)" in output
        assert "[A♠] [K♥] [Q♦]" in output
        assert "Admin (你)👑" in output
        assert "[A♣] [A♦]" in output
        assert "[c]过牌 (Check)" in output
        assert "[r/b <额度>]下注(10~980)" in output
        assert "⏱ 玩家倒计时" in output
        assert "15s" in output
        assert "轮到你" in output
        assert "[████" in output
        assert all(display_width(line) == 98 for line in output.splitlines())

    def test_render_table_dashboard_shows_bot_icon(self):
        renderer = PokerUiRenderer(enable_color=False, mode="dashboard")
        room_data = {
            "room_id": "r_test",
            "host_player_id": "u_admin",
            "config": {"room_name": "测试桌", "small_blind": 5, "big_blind": 10, "action_timeout": 15},
            "is_ended": False,
            "table": {
                "street": "IDLE",
                "seats": [
                    {
                        "player_id": "bot_1",
                        "name": "测试机器人 1",
                        "is_bot": True,
                        "chips": 1000,
                        "rebuy_count": 0,
                        "current_round_bet": 0,
                        "is_folded": False,
                        "is_all_in": False,
                        "hole_cards": [],
                        "shown_cards": [],
                        "last_action": "",
                    },
                ],
                "legal_actions": {},
            },
        }
        output = renderer.render_table_dashboard(room_data, "u_admin")
        assert "🤖测试机器人 1" in output

    def test_render_help_contains_bot(self):
        renderer = PokerUiRenderer(enable_color=False)
        output = renderer.render_help("room")
        assert "bot" in output
        assert "测试机器人" in output

    def test_render_settlement_report(self):
        renderer = PokerUiRenderer(enable_color=False, mode="dashboard")
        report = {
            "room_id": "r_123",
            "room_name": "德州扑克结算局",
            "chip_to_cash_ratio": 0.1,
            "player_settlements": [
                {
                    "player_id": "u_winner",
                    "player_name": "赢家小王",
                    "rebuy_count": 1,
                    "total_buyin_cash": 100.0,
                    "final_chips": 2000,
                    "net_profit_cash": 100.0,
                },
                {
                    "player_id": "u_loser",
                    "player_name": "输家小李",
                    "rebuy_count": 1,
                    "total_buyin_cash": 100.0,
                    "final_chips": 0,
                    "net_profit_cash": -100.0,
                },
            ],
            "transfers": [
                {
                    "from_player_name": "输家小李",
                    "to_player_name": "赢家小王",
                    "amount_cash": 100.0,
                    "amount_chips": 1000,
                }
            ],
        }
        output = renderer.render_settlement_report(report)
        assert "战局终局结算报表: 德州扑克结算局" in output
        assert "赢家小王" in output
        assert "+100.00" in output
        assert "输家小李" in output
        assert "-100.00" in output
        assert "输家小李  ── 应转账 ──▶  ¥ 100.00 (折合1000筹码) ──▶  赢家小王" in output


@pytest.mark.asyncio
class TestPokerApiClient:
    """Tests for REST API client."""

    async def test_api_client_operations(self):
        from fastapi.testclient import TestClient
        from backend.main import app

        # Test through TestClient or direct mocked responses
        with patch("httpx.AsyncClient.get") as mock_get, patch("httpx.AsyncClient.post") as mock_post:
            client = PokerApiClient("http://localhost:8000")

            # Mock users
            mock_get.return_value.status_code = 200
            mock_get.return_value.json = MagicMock(return_value=[{"user_id": "u_fwd", "username": "fwd"}])
            mock_get.return_value.raise_for_status = MagicMock()

            users = await client.list_users()
            assert len(users) == 1
            assert users[0]["username"] == "fwd"

            # Mock login
            mock_post.return_value.status_code = 200
            mock_post.return_value.json = MagicMock(return_value={"token": "tk_123", "user": {"user_id": "u_fwd"}})
            mock_post.return_value.raise_for_status = MagicMock()

            login_res = await client.login("fwd", "123")
            assert login_res["token"] == "tk_123"

            # Mock create room
            mock_post.return_value.json = MagicMock(return_value={"room_id": "rm_999"})
            room = await client.create_room("u_fwd", "新房间")
            assert room["room_id"] == "rm_999"

            # Mock add test bot
            mock_post.return_value.json = MagicMock(return_value={"room_id": "rm_999", "bot_added": True})
            bot_res = await client.add_test_bot("rm_999", "u_fwd", seat_index=2)
            assert bot_res["bot_added"] is True
            assert mock_post.call_args[1]["params"] == {"requester_id": "u_fwd", "seat_index": 2}

            await client.close()



@pytest.mark.asyncio
class TestPokerWsClient:
    """Tests for WebSocket Client."""

    async def test_ws_client_event_dispatch(self):
        ws_client = PokerWsClient("ws://localhost:8000/ws/test/u1")
        mock_ws = AsyncMock()
        mock_ws.closed = False
        ws_client.websocket = mock_ws

        # Test sending actions
        await ws_client.sit_down(2)
        mock_ws.send.assert_called_once()
        assert '"event": "SIT_DOWN"' in mock_ws.send.call_args[0][0]
        assert '"seat_index": 2' in mock_ws.send.call_args[0][0]

        mock_ws.reset_mock()
        await ws_client.player_action("RAISE", 150)
        assert '"event": "PLAYER_ACTION"' in mock_ws.send.call_args[0][0]
        assert '"amount": 150' in mock_ws.send.call_args[0][0]

        mock_ws.reset_mock()
        await ws_client.show_card(card_index=0)
        assert '"event": "SHOW_CARD"' in mock_ws.send.call_args[0][0]

        mock_ws.reset_mock()
        await ws_client.rit_choice(2)
        assert '"event": "RIT_CHOICE"' in mock_ws.send.call_args[0][0]
        assert '"choice": 2' in mock_ws.send.call_args[0][0]

        mock_ws.reset_mock()
        await ws_client.add_bot(3)
        assert '"event": "ADD_TEST_BOT"' in mock_ws.send.call_args[0][0]
        assert '"seat_index": 3' in mock_ws.send.call_args[0][0]


    async def test_ws_client_dispatches_room_events_and_sound_metadata(self):
        ws_client = PokerWsClient("ws://localhost:8000/ws/test/u1")
        ws_client.on_action_event = AsyncMock()
        ws_client.on_sound_effect = AsyncMock()
        ws_client.on_settlement_report = AsyncMock()
        ws_client.on_room_deleted = AsyncMock()

        await ws_client._dispatch({
            "event": "ACTION_EVENT",
            "payload": {"action": "CALL", "amount": 20},
        })
        await ws_client._dispatch({
            "event": "SOUND_EFFECT",
            "payload": {"sound": "raise", "player_id": "u1"},
        })
        await ws_client._dispatch({
            "event": "SETTLEMENT_REPORT",
            "payload": {"room_id": "r1"},
        })
        await ws_client._dispatch({
            "event": "ROOM_DELETED",
            "payload": {"room_id": "r1", "message": "closed"},
        })

        ws_client.on_action_event.assert_awaited_once_with({"action": "CALL", "amount": 20})
        ws_client.on_sound_effect.assert_awaited_once_with("raise", {"player_id": "u1"})
        ws_client.on_settlement_report.assert_awaited_once_with({"room_id": "r1"})
        ws_client.on_room_deleted.assert_awaited_once_with({"room_id": "r1", "message": "closed"})


@pytest.mark.asyncio
class TestPokerCliController:
    """Tests for CLI Controller logic and raise parsing."""

    async def test_raise_calculation_and_bounds(self):
        controller = PokerCliController(enable_color=False)
        controller.active_room_data = {
            "table": {
                "total_pot": 200,
                "legal_actions": {
                    "can_bet": False,
                    "can_raise": True,
                    "min_raise": 40,
                    "max_raise": 1000,
                },
            }
        }
        mock_ws = AsyncMock()
        controller.ws_client = mock_ws

        # Test fraction raise: 0.5p -> 100
        await controller._handle_raise_command(["r", "0.5p"])
        mock_ws.player_action.assert_called_with("RAISE", 100)

        # Test 1p -> 200
        mock_ws.reset_mock()
        await controller._handle_raise_command(["r", "1p"])
        mock_ws.player_action.assert_called_with("RAISE", 200)

        # Compact command syntax: r0.5 -> half pot, r200 -> 200 chips.
        mock_ws.reset_mock()
        await controller._dispatch_room_command(parse_command("r0.5"))
        mock_ws.player_action.assert_called_with("RAISE", 100)

        mock_ws.reset_mock()
        await controller._dispatch_room_command(parse_command("r200"))
        mock_ws.player_action.assert_called_with("RAISE", 200)

        # Test 2/3p -> 133
        mock_ws.reset_mock()
        await controller._handle_raise_command(["r", "2/3p"])
        mock_ws.player_action.assert_called_with("RAISE", 133)

        # Test allin -> 1000
        mock_ws.reset_mock()
        await controller._handle_raise_command(["r", "all"])
        mock_ws.player_action.assert_called_with("RAISE", 1000)

        # Test below min_raise adjustment
        mock_ws.reset_mock()
        await controller._handle_raise_command(["r", "10"])
        mock_ws.player_action.assert_called_with("RAISE", 40)

    async def test_login_flow_manual_input(self):
        """Test manual username and password login flow in CLI controller."""
        controller = PokerCliController(enable_color=False)
        controller.api = MagicMock()
        controller.api.login = AsyncMock(return_value={
            "token": "test_token_123",
            "user": {"user_id": "u_fwd", "nickname": "fwd", "username": "fwd"},
        })

        # Mock user typing username "fwd" then password "123"
        with patch.object(controller, "_async_input", AsyncMock(side_effect=["fwd"])), \
             patch.object(controller, "_async_password_input", AsyncMock(return_value="123")):
            success = await controller.login_flow()
            assert success is True
            assert controller.current_user["username"] == "fwd"
            assert controller.auth_token == "test_token_123"
            controller.api.login.assert_called_once_with("fwd", "123")

    async def test_add_bot_command_host_and_non_host(self):
        """Test host can add test bot via CLI and non-host cannot."""
        controller = PokerCliController(enable_color=False)
        controller.current_user = {"user_id": "u_host", "username": "host"}
        controller.active_room_id = "r_test"
        controller.active_room_data = {
            "host_player_id": "u_host",
            "table": {
                "street": "IDLE",
                "seats": [None, None, None, None, None, None],
            },
        }
        mock_ws = AsyncMock()
        mock_ws.is_connected = True
        controller.ws_client = mock_ws

        # Host can add bot (no seat specified)
        cmd = parse_command("bot")
        assert cmd is not None
        await controller._dispatch_room_command(cmd)
        mock_ws.add_bot.assert_called_with(seat_index=None)

        # Host can add bot specifying seat
        mock_ws.reset_mock()
        cmd = parse_command("bot 2")
        assert cmd is not None
        await controller._dispatch_room_command(cmd)
        mock_ws.add_bot.assert_called_with(seat_index=2)

        # Non-host cannot add bot
        mock_ws.reset_mock()
        controller.current_user = {"user_id": "u_guest", "username": "guest"}
        cmd = parse_command("bot")
        assert cmd is not None
        await controller._dispatch_room_command(cmd)
        mock_ws.add_bot.assert_not_called()

        # Cannot add bot during active hand
        controller.current_user = {"user_id": "u_host", "username": "host"}
        controller.active_room_data["table"]["street"] = "FLOP"
        mock_ws.reset_mock()
        cmd = parse_command("addbot")
        assert cmd is not None
        await controller._dispatch_room_command(cmd)
        mock_ws.add_bot.assert_not_called()

    async def test_full_cli_game_flow(self):
        """End-to-end integration test of room creation, playing hand, and settlement."""
        from fastapi.testclient import TestClient
        from backend.main import app

        with TestClient(app) as client:
            # 1. Login Admin
            login_resp = client.post("/api/auth/login", json={"username": "admin", "password": "admin"})
            assert login_resp.status_code == 200
            admin_data = login_resp.json()

            # 2. Login Player fwd
            login_fwd = client.post("/api/auth/login", json={"username": "fwd", "password": "123"})
            assert login_fwd.status_code == 200
            fwd_data = login_fwd.json()

            # 3. Create room
            create_resp = client.post("/api/rooms", json={
                "host_player_id": admin_data["user"]["user_id"],
                "room_name": "CLI集成测试房间",
                "buyin_chips": 1000,
                "cash_value": 100.0,
                "small_blind": 5,
                "big_blind": 10,
                "action_timeout": 15,
                "max_seats": 6,
            })
            assert create_resp.status_code == 200
            room = create_resp.json()
            r_id = room["room_id"]

            # 4. Connect WebSockets for both players
            with client.websocket_connect(f"/ws/{r_id}/{admin_data['user']['user_id']}") as ws_admin, \
                 client.websocket_connect(f"/ws/{r_id}/{fwd_data['user']['user_id']}") as ws_fwd:

                # Drain initial state messages
                msg_admin = ws_admin.receive_json()
                assert msg_admin["event"] == "ROOM_STATE"

                msg_fwd = ws_fwd.receive_json()
                assert msg_fwd["event"] == "ROOM_STATE"

                # Both players ready
                ws_admin.send_json({"event": "PLAYER_READY", "payload": {"ready": True}})
                ws_fwd.send_json({"event": "PLAYER_READY", "payload": {"ready": True}})

                # Admin starts game
                ws_admin.send_json({"event": "START_GAME", "payload": {}})

                # Receive updated state with dealing
                # In game: PREFLOP
                state = None
                for _ in range(10):
                    data = ws_admin.receive_json()
                    if data.get("event") == "ROOM_STATE":
                        state = data.get("payload")
                        if state.get("table", {}).get("street") == "PREFLOP":
                            break

                assert state is not None
                assert state["table"]["street"] == "PREFLOP"
                assert state["table"]["hand_number"] == 1

                # End room as host
                ws_admin.send_json({"event": "END_ROOM", "payload": {}})

                # Receive state with settlement report
                final_state = None
                for _ in range(5):
                    data = ws_admin.receive_json()
                    if data.get("event") == "ROOM_STATE":
                        final_state = data.get("payload")
                        if final_state.get("is_ended"):
                            break

                assert final_state is not None
                assert final_state["is_ended"] is True
                assert "settlement_report" in final_state
                rep = final_state["settlement_report"]
                assert rep is not None
                assert "player_records" in rep
                assert len(rep["player_records"]) == 2
