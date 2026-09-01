import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.app.services.user_manager import user_manager
from backend.app.services.room_manager import room_manager
from backend.app.websocket.protocol import EventType


def test_rest_api_users_and_rooms():
    client = TestClient(app)

    # 1. Get preset users
    resp = client.get("/api/users")
    assert resp.status_code == 200
    users = resp.json()
    assert len(users) >= 8
    assert any(u["username"] == "tom_dwan" for u in users)

    # 2. Admin creates a user
    resp = client.post("/api/users", json={
        "username": "new_pro",
        "nickname": "Poker Pro",
        "avatar": "🤠",
        "is_admin": False
    })
    assert resp.status_code == 200
    new_user = resp.json()
    assert new_user["username"] == "new_pro"

    # 3. Create a cash game room
    resp = client.post("/api/rooms", json={
        "host_player_id": "u_admin",
        "room_name": "High Stakes Table",
        "buyin_chips": 2000,
        "cash_value": 200.0,
        "small_blind": 10,
        "big_blind": 20,
        "action_timeout": 20,
        "max_seats": 6
    })
    assert resp.status_code == 200
    room_data = resp.json()
    room_id = room_data["room_id"]
    assert room_data["config"]["room_name"] == "High Stakes Table"

    # 4. Get room details
    resp = client.get(f"/api/rooms/{room_id}")
    assert resp.status_code == 200
    assert resp.json()["room_id"] == room_id


def test_websocket_room_interaction():
    client = TestClient(app)

    # Create room
    resp = client.post("/api/rooms", json={
        "host_player_id": "u_tom",
        "room_name": "WS Test Room",
        "buyin_chips": 1000,
        "cash_value": 100.0,
        "small_blind": 5,
        "big_blind": 10,
        "action_timeout": 15,
        "max_seats": 6
    })
    room_id = resp.json()["room_id"]

    # Connect client 1 (Tom) via WebSocket
    with client.websocket_connect(f"/ws/{room_id}/u_tom") as ws1:
        # Initial message is ROOM_STATE
        msg = ws1.receive_json()
        assert msg["event"] == EventType.ROOM_STATE.value
        assert msg["payload"]["room_id"] == room_id

        # Ping / Pong test
        ws1.send_json({"event": EventType.PING.value})
        msg_pong = ws1.receive_json()
        assert msg_pong["event"] == EventType.PONG.value

        # Tom sits down at seat 0
        ws1.send_json({
            "event": EventType.SIT_DOWN.value,
            "payload": {"seat_index": 0}
        })
        # Server broadcasts sound and state
        msg_sound = ws1.receive_json()
        assert msg_sound["event"] == EventType.SOUND_EFFECT.value
        msg_state = ws1.receive_json()
        assert msg_state["event"] == EventType.ROOM_STATE.value
        assert msg_state["payload"]["table"]["seats"][0]["player_id"] == "u_tom"
