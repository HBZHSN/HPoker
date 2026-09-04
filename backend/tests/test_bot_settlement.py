import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.app.models.room import Room, RoomConfig
from backend.app.services.room_manager import room_manager
from backend.app.services.user_manager import user_manager
from backend.app.services.balance_manager import balance_manager
from backend.app.websocket.protocol import EventType


def _auth_ws_url(path: str) -> str:
    """Helper to append user's valid token to test websocket paths."""
    if "?token=" in path or "no_auth=1" in path:
        return path.replace("?no_auth=1", "").replace("&no_auth=1", "")
    parts = path.split("?")[0].strip("/").split("/")
    if len(parts) == 3 and parts[0] == "ws":
        user_id = parts[2]
        token = user_manager.get_or_create_token(user_id)
        if token:
            sep = "&" if "?" in path else "?"
            return f"{path}{sep}token={token}"
    return path


@pytest.fixture(autouse=True)
def auto_auth_ws(monkeypatch):
    orig_ws_connect = TestClient.websocket_connect

    def _ws_connect(self, url, *args, **kwargs):
        return orig_ws_connect(self, _auth_ws_url(url), *args, **kwargs)

    monkeypatch.setattr(TestClient, "websocket_connect", _ws_connect)


def test_room_has_bots_detection():
    room = Room(
        host_player_id="host_1",
        config=RoomConfig(buyin_chips=1000, cash_value=100.0, small_blind=10, max_seats=6),
    )
    assert room.has_bots is False
    assert room.to_dict()["has_bots"] is False

    room.sit_down_player("host_1", "Host", seat_index=0)
    assert room.has_bots is False

    bot = room.add_test_bot(seat_index=1)
    assert bot is not None
    assert room.has_bots is True
    assert room.to_dict()["has_bots"] is True

    # Stand up / kick bot
    room.kick_player(bot["player_id"])
    # Bot is no longer seated, but participated in the room history
    assert any(seat and seat.is_bot for seat in room.table.seats) is False
    assert room.has_bots is True
    assert room.to_dict()["has_bots"] is True


def test_bot_room_uses_play_money_and_closes_without_balance_pollution():
    room = Room(
        host_player_id="host_1",
        config=RoomConfig(buyin_chips=1000, cash_value=100.0, small_blind=10, max_seats=6),
    )
    room.sit_down_player("host_1", "Host", seat_index=0)
    room.add_test_bot(seat_index=1)

    assert room.money_mode == "play"
    assert balance_manager.get_user_balances() == []

    report = room.end_room(requester_id="host_1", settlement_type="balance")
    assert report is not None
    assert report.settlement_type == "balance"
    assert room.is_ended is True
    assert balance_manager.get_user_balances() == []


def test_bot_room_checkpoint_restoration_preserves_has_bots():
    room = Room(
        host_player_id="host_1",
        config=RoomConfig(buyin_chips=1000, cash_value=100.0, small_blind=10, max_seats=6),
    )
    room.sit_down_player("host_1", "Host", seat_index=0)
    room.add_test_bot(seat_index=1)

    checkpoint = room.to_checkpoint_dict()
    restored = Room.from_checkpoint_dict(checkpoint)

    assert restored.has_bots is True
    assert restored.money_mode == "play"
    report = restored.end_room(requester_id="host_1", settlement_type="balance")
    assert report.settlement_type == "balance"
    assert restored.is_ended is True


def test_api_end_room_with_bot_closes_play_money_room():
    client = TestClient(app)
    room = room_manager.create_room(
        host_player_id="u_test1",
        config=RoomConfig(buyin_chips=1000, cash_value=100.0, small_blind=10, max_seats=6),
    )
    room_id = room.room_id
    room.sit_down_player("u_test1", "Host", seat_index=0)
    room.add_test_bot(seat_index=1)

    # A bot room is play-money, so closing it never changes real balances.
    resp_balance = client.post(f"/api/rooms/{room_id}/end?requester_id=u_test1&settlement_type=balance")
    assert resp_balance.status_code == 200
    assert room_manager.get_room(room_id) is None
    assert balance_manager.get_user_balances() == []


def test_ws_end_room_with_bot_closes_play_money_room():
    client = TestClient(app)
    room = room_manager.create_room(
        host_player_id="u_test1",
        config=RoomConfig(buyin_chips=1000, cash_value=100.0, small_blind=10, max_seats=6),
    )
    room_id = room.room_id
    room.sit_down_player("u_test1", "Host", seat_index=0)
    room.add_test_bot(seat_index=1)

    with client.websocket_connect(f"/ws/{room_id}/u_test1") as ws_host:
        # Drain initial state
        _ = ws_host.receive_json()

        ws_host.send_json({
            "event": EventType.END_ROOM.value,
            "payload": {"settlement_type": "balance"},
        })

        received_ended = False
        for _ in range(5):
            msg = ws_host.receive_json()
            if msg["event"] == EventType.ROOM_STATE.value and msg["payload"].get("is_ended"):
                received_ended = True
                assert msg["payload"].get("settlement_type") == "balance"
                break

        assert received_ended is True
        # Room is dissolved
        assert room_manager.get_room(room_id) is None


def test_bot_room_immediate_settlement_does_not_pollute_balances():
    room = Room(
        host_player_id="u_test1",
        config=RoomConfig(buyin_chips=1000, cash_value=100.0, small_blind=10, max_seats=6),
    )
    room.sit_down_player("u_test1", "Host", seat_index=0)
    room.add_test_bot(seat_index=1)

    # Settle immediately
    report = room.end_room(requester_id="u_test1", settlement_type="immediate")
    assert report.settlement_type == "immediate"

    # Verify that in balance_manager, user balances for consolidated debt are NOT affected
    unsettled = balance_manager.get_user_balances(include_test=False)
    # The immediate settlement is already settled (status="settled"), not unsettled
    assert len(unsettled) == 0


def test_bot_presence_switches_future_buyins_to_play_money_then_back_to_cash():
    room = Room(
        host_player_id="real_host",
        config=RoomConfig(buyin_chips=100, cash_value=10, small_blind=5),
        room_id="mode-switch",
    )
    assert room.sit_down_player("real_host", "Alice", 0, is_test=False)
    assert room.sit_down_player("real_guest", "Bob", 1, is_test=False)
    assert {b.user_id: b.net_cash for b in balance_manager.get_user_balances()} == {
        "real_host": -10,
        "real_guest": -10,
    }

    bot = room.add_test_bot(2)
    assert bot is not None
    assert room.money_mode == "play"
    assert balance_manager.get_user_balances() == []

    room.table.seats[1].chips = 0
    entry_count = len(balance_manager._entries)
    assert room.rebuy_player("real_guest")
    assert len(balance_manager._entries) == entry_count

    room.table.seats[0].chips = 150
    room.table.seats[1].chips = 50
    assert room.kick_player(bot["player_id"])
    assert room.money_mode == "real"
    assert {b.user_id: b.net_cash for b in balance_manager.get_user_balances()} == {
        "real_host": -15,
        "real_guest": -5,
    }

    room.table.seats[0].chips = 180
    room.table.seats[1].chips = 20
    assert room.leave_player("real_host")
    assert room.leave_player("real_guest")
    assert {b.user_id: b.net_cash for b in balance_manager.get_user_balances()} == {
        "real_host": 3,
        "real_guest": -3,
    }


def test_test_user_join_during_hand_defers_play_money_switch_to_hand_boundary():
    room = Room(
        host_player_id="boundary_host",
        config=RoomConfig(buyin_chips=100, cash_value=10, small_blind=5),
        room_id="mode-boundary",
    )
    assert room.sit_down_player("boundary_host", "Alice", 0, is_test=False)
    assert room.sit_down_player("boundary_guest", "Bob", 1, is_test=False)
    assert room.table.start_new_hand()

    assert room.sit_down_player("test_joiner", "Tester", 2, is_test=True)
    assert room.money_mode == "real"
    assert room.has_active_test_players is True

    room.table.refund_unsettled_hand()
    assert room.prepare_next_hand()
    assert room.money_mode == "play"
    assert balance_manager.get_user_balances() == []
