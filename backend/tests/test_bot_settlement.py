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


def test_bot_room_forbids_balance_settlement_and_allows_immediate():
    room = Room(
        host_player_id="host_1",
        config=RoomConfig(buyin_chips=1000, cash_value=100.0, small_blind=10, max_seats=6),
    )
    room.sit_down_player("host_1", "Host", seat_index=0)
    room.add_test_bot(seat_index=1)

    # 1. Attempting balance settlement must raise ValueError
    with pytest.raises(ValueError, match="房间内含有机器人，不允许结算到余额，只能实时结算"):
        room.end_room(requester_id="host_1", settlement_type="balance")

    # Room is not ended
    assert room.is_ended is False

    # 2. Immediate settlement succeeds
    report = room.end_room(requester_id="host_1", settlement_type="immediate")
    assert report is not None
    assert report.settlement_type == "immediate"
    assert room.is_ended is True
    assert room.settlement_type == "immediate"


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
    with pytest.raises(ValueError, match="房间内含有机器人，不允许结算到余额，只能实时结算"):
        restored.end_room(requester_id="host_1", settlement_type="balance")

    report = restored.end_room(requester_id="host_1", settlement_type="immediate")
    assert report.settlement_type == "immediate"
    assert restored.is_ended is True


def test_api_end_room_with_bot_rejects_balance_and_accepts_immediate():
    client = TestClient(app)
    room = room_manager.create_room(
        host_player_id="u_test1",
        config=RoomConfig(buyin_chips=1000, cash_value=100.0, small_blind=10, max_seats=6),
    )
    room_id = room.room_id
    room.sit_down_player("u_test1", "Host", seat_index=0)
    room.add_test_bot(seat_index=1)

    # REST: settlement_type=balance should return 400
    resp_balance = client.post(f"/api/rooms/{room_id}/end?requester_id=u_test1&settlement_type=balance")
    assert resp_balance.status_code == 400
    assert "机器人" in resp_balance.json()["detail"]

    # Room still active
    assert room_manager.get_room(room_id) is not None

    # REST: settlement_type=immediate should return 200
    resp_immediate = client.post(f"/api/rooms/{room_id}/end?requester_id=u_test1&settlement_type=immediate")
    assert resp_immediate.status_code == 200
    data = resp_immediate.json()
    assert data["settlement_type"] == "immediate"


def test_ws_end_room_with_bot_rejects_balance_and_accepts_immediate():
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

        # Host sends END_ROOM with balance
        ws_host.send_json({
            "event": EventType.END_ROOM.value,
            "payload": {"settlement_type": "balance"},
        })

        msg = ws_host.receive_json()
        assert msg["event"] == EventType.ERROR_MESSAGE.value
        assert "机器人" in msg["payload"]["message"]

        # Room should still exist
        assert room_manager.get_room(room_id) is not None

        # Host sends END_ROOM with immediate
        ws_host.send_json({
            "event": EventType.END_ROOM.value,
            "payload": {"settlement_type": "immediate"},
        })

        # Receive sound and final room state
        received_ended = False
        for _ in range(5):
            msg = ws_host.receive_json()
            if msg["event"] == EventType.ROOM_STATE.value and msg["payload"].get("is_ended"):
                received_ended = True
                assert msg["payload"].get("settlement_type") == "immediate"
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
