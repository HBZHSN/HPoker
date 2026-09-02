"""Comprehensive Unit Tests for Poker CLI Client."""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from cli.api_client import PokerApiClient
from cli.ws_client import PokerWsClient
from cli.ui_renderer import PokerUiRenderer, Colors
from cli.controller import PokerCliController
from backend.app.services.user_manager import user_manager
from backend.app.services.room_manager import room_manager
from backend.app.models.room import RoomConfig


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
        output = renderer.render_table_dashboard(room_data, "u_admin")
        assert "HPoker 现金桌: 经典德州现金桌" in output
        assert "翻牌圈 (Flop)" in output
        assert "[A♠] [K♥] [Q♦]" in output
        assert "Admin (你)👑" in output
        assert "[A♣] [A♦]" in output
        assert "[c]过牌 (Check)" in output
        assert "[r/b <额度>]下注(10~980)" in output

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

