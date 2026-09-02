import pytest
import httpx
from fastapi.testclient import TestClient
from backend.main import app
from backend.app.services.user_manager import user_manager, DEFAULT_PRESET_USERS
from backend.app.services.room_manager import room_manager
from backend.app.websocket.protocol import EventType
from backend.app.models.room import RoomConfig


@pytest.fixture(autouse=True)
def isolate_user_manager(monkeypatch):
    """Ensure tests run in memory without writing dummy data to backend/data/users.json."""
    original_path = user_manager.storage_path
    user_manager.storage_path = ":memory:"
    user_manager.load_from_storage()
    yield
    user_manager.storage_path = original_path
    user_manager.load_from_storage()


def test_rest_api_users_and_rooms():
    client = TestClient(app)

    # 1. Get preset users (fwd, hx, yy)
    resp = client.get("/api/users")
    assert resp.status_code == 200
    users = resp.json()
    assert len(users) >= 3
    assert any(u["username"] == "fwd" for u in users)
    assert any(u["username"] == "hx" for u in users)
    assert any(u["username"] == "yy" for u in users)

    # 2. Auth login test with fwd
    resp = client.post("/api/auth/login", json={
        "username": "fwd",
        "password": "123"
    })
    assert resp.status_code == 200
    auth_data = resp.json()
    token = auth_data["token"]
    assert auth_data["user"]["username"] == "fwd"

    # Verify token
    resp_me = client.get(f"/api/auth/me?token={token}")
    assert resp_me.status_code == 200
    assert resp_me.json()["user"]["username"] == "fwd"

    # 3. Create a cash game room
    resp = client.post("/api/rooms", json={
        "host_player_id": "u_fwd",
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


@pytest.mark.asyncio
async def test_room_blind_defaults_and_derived_big_blind():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        default_resp = await client.post("/api/rooms", json={"host_player_id": "u_fwd"})
        assert default_resp.status_code == 200
        default_config = default_resp.json()["config"]
        assert default_config["buyin_chips"] == 1000
        assert default_config["cash_value"] == 100.0
        assert default_config["small_blind"] == 10
        assert default_config["big_blind"] == 20

        # A legacy/forged BB value must not override the room's derived BB.
        custom_resp = await client.post(
            "/api/rooms",
            json={"host_player_id": "u_fwd", "small_blind": 15, "big_blind": 999},
        )
        assert custom_resp.status_code == 200
        custom_config = custom_resp.json()["config"]
        assert custom_config["small_blind"] == 15
        assert custom_config["big_blind"] == 30

    config = RoomConfig()
    assert config.buyin_chips == 1000
    assert config.cash_value == 100.0
    assert config.small_blind == 10
    assert config.big_blind == 20


def test_websocket_room_interaction():
    client = TestClient(app)

    # Create room
    resp = client.post("/api/rooms", json={
        "host_player_id": "u_fwd",
        "room_name": "WS Test Room",
        "buyin_chips": 1000,
        "cash_value": 100.0,
        "small_blind": 5,
        "big_blind": 10,
        "action_timeout": 15,
        "max_seats": 6
    })
    room_id = resp.json()["room_id"]

    # Connect client 1 (fwd - Room Host) via WebSocket
    with client.websocket_connect(f"/ws/{room_id}/u_fwd") as ws1:
        # Initial message is ROOM_STATE (with fwd automatically seated at seat 0)
        msg = ws1.receive_json()
        assert msg["event"] == EventType.ROOM_STATE.value
        assert msg["payload"]["room_id"] == room_id
        assert msg["payload"]["table"]["seats"][0] is not None
        assert msg["payload"]["table"]["seats"][0]["player_id"] == "u_fwd"

        # Ping / Pong test
        ws1.send_json({"event": EventType.PING.value})
        msg_pong = ws1.receive_json()
        assert msg_pong["event"] == EventType.PONG.value

        # Connect client 2 (hx - Non-host player) via WebSocket
        with client.websocket_connect(f"/ws/{room_id}/u_hx") as ws2:
            # ws1 receives room state update with hx auto-seated at seat 1
            msg_ws1_sync = ws1.receive_json()
            assert msg_ws1_sync["event"] == EventType.ROOM_STATE.value
            assert msg_ws1_sync["payload"]["table"]["seats"][1]["player_id"] == "u_hx"

            msg_ws2_sync = ws2.receive_json()
            assert msg_ws2_sync["event"] == EventType.ROOM_STATE.value
            assert msg_ws2_sync["payload"]["table"]["seats"][1]["player_id"] == "u_hx"

            # Non-host (hx) tries to send START_GAME -> rejected / ignored
            ws2.send_json({"event": EventType.START_GAME.value})

            # Non-host (hx) sets ready -> updates ready list
            ws2.send_json({
                "event": EventType.PLAYER_READY.value,
                "payload": {"ready": True}
            })
            msg_ready_1 = ws1.receive_json()
            msg_ready_2 = ws2.receive_json()
            assert "u_hx" in msg_ready_1["payload"]["table"]["ready_player_ids"]
            assert "u_hx" in msg_ready_2["payload"]["table"]["ready_player_ids"]

            # Host (fwd) sends START_GAME -> Game starts!
            ws1.send_json({"event": EventType.START_GAME.value})

            # Sound effect 'deal' broadcast to both
            sound1 = ws1.receive_json()
            sound2 = ws2.receive_json()
            assert sound1["event"] == EventType.SOUND_EFFECT.value
            assert sound2["event"] == EventType.SOUND_EFFECT.value

            # Game state starts PREFLOP
            state1 = ws1.receive_json()
            state2 = ws2.receive_json()
            assert state1["payload"]["table"]["street"] == "PREFLOP"
            assert state2["payload"]["table"]["street"] == "PREFLOP"


def test_auth_and_admin_security():
    client = TestClient(app)

    # 1. Invalid login
    resp = client.post("/api/auth/login", json={
        "username": "fwd",
        "password": "wrong_password"
    })
    assert resp.status_code == 401

    # 2. Login with correct password for player fwd (non-admin)
    resp = client.post("/api/auth/login", json={
        "username": "fwd",
        "password": "123"
    })
    assert resp.status_code == 200
    auth_data = resp.json()
    assert auth_data["user"]["username"] == "fwd"
    assert auth_data["user"]["is_admin"] is False

    # 3. Login with admin user (is_admin == True)
    resp_admin = client.post("/api/auth/login", json={
        "username": "admin",
        "password": "admin"
    })
    assert resp_admin.status_code == 200
    admin_data = resp_admin.json()
    assert admin_data["user"]["username"] == "admin"
    assert admin_data["user"]["is_admin"] is True

    # 4. Non-admin (fwd) blocked from admin API
    resp_forbidden = client.get("/api/admin/users?admin_id=u_fwd")
    assert resp_forbidden.status_code == 403

    # 5. Admin can access admin API
    resp_allowed = client.get("/api/admin/users?admin_id=u_admin")
    assert resp_allowed.status_code == 200

    # 6. Profile update test on isolated in-memory user
    resp = client.post("/api/auth/profile", json={
        "user_id": "u_fwd",
        "nickname": "FWD Boss",
        "avatar": "🦈"
    })
    assert resp.status_code == 200
    assert resp.json()["user"]["nickname"] == "FWD Boss"


@pytest.mark.asyncio
async def test_turn_timeout_and_hand_end_auto_start():
    import asyncio
    from backend.app.websocket.router import trigger_room_turn_timer
    from backend.app.services.timeout_manager import timeout_manager
    from backend.app.services.room_manager import room_manager
    from backend.app.models.room import RoomConfig
    from backend.app.engine.state_machine import Street

    # Create room with 1 second action timeout
    config = RoomConfig(
        room_name="Quick Timeout Room",
        buyin_chips=1000,
        cash_value=100.0,
        small_blind=5,
        big_blind=10,
        action_timeout=1,
        max_seats=6
    )
    room = room_manager.create_room(host_player_id="u_fwd", config=config)
    room.sit_down_player("u_fwd", "fwd", 0)
    room.sit_down_player("u_hx", "hx", 1)

    # Start hand
    assert room.table.start_new_hand() is True
    assert room.table.street == Street.PREFLOP
    initial_turn_seat = room.table.current_turn_seat
    assert initial_turn_seat is not None
    current_player = room.table.seats[initial_turn_seat]
    assert current_player.time_bank_cards == 3

    # Trigger turn timer
    await trigger_room_turn_timer(room.room_id)

    # Sleep for 1.2s to allow initial timeout worker to fire
    await asyncio.sleep(1.2)

    # After initial timeout, player should have auto-consumed 1 time card (+30s)
    assert current_player.time_bank_cards == 2
    assert room.table.is_using_time_bank is True

    # Now set time_bank_cards to 0 and re-trigger 1s timer to test auto-fold/check
    current_player.time_bank_cards = 0
    room.table.current_turn_duration = 1
    await trigger_room_turn_timer(room.room_id)
    await asyncio.sleep(1.2)

    # After zero-card timeout, player at initial_turn_seat should have auto-folded/checked
    assert room.table.current_turn_seat != initial_turn_seat or room.table.street in (Street.FLOP, Street.HAND_END)

    # Clean up timers
    timeout_manager.cancel_all_timers(room.room_id)


def test_rebuy_only_allowed_when_chips_zero_ws():
    client = TestClient(app)

    resp = client.post("/api/rooms", json={
        "host_player_id": "u_fwd",
        "room_name": "Rebuy WS Test",
        "buyin_chips": 1000,
        "cash_value": 100.0,
        "small_blind": 5,
        "big_blind": 10,
        "action_timeout": 15,
        "max_seats": 6
    })
    room_id = resp.json()["room_id"]

    with client.websocket_connect(f"/ws/{room_id}/u_fwd") as ws:
        msg = ws.receive_json()
        assert msg["payload"]["table"]["seats"][0]["chips"] == 1000

        # fwd tries to rebuy with 1000 chips -> should fail / not rebuy
        ws.send_json({"event": EventType.REBUY.value})
        # Server does not broadcast rebuy sound or changes
        room = room_manager.get_room(room_id)
        assert room.table.seats[0].chips == 1000
        assert room.table.seats[0].rebuy_count == 1

        # fwd loses all chips
        room.table.seats[0].chips = 0

        # fwd rebuys now with 0 chips -> succeeds
        ws.send_json({"event": EventType.REBUY.value})
        sound_msg = ws.receive_json()
        assert sound_msg["event"] == EventType.SOUND_EFFECT.value
        assert sound_msg["payload"]["sound"] == "rebuy"

        state_msg = ws.receive_json()
        assert state_msg["payload"]["table"]["seats"][0]["chips"] == 1000
        assert state_msg["payload"]["table"]["seats"][0]["rebuy_count"] == 2


def test_auto_seating_when_room_full():
    client = TestClient(app)

    resp = client.post("/api/rooms", json={
        "host_player_id": "u_fwd",
        "room_name": "Max 2 Seats Room",
        "buyin_chips": 500,
        "cash_value": 50.0,
        "small_blind": 2,
        "big_blind": 5,
        "action_timeout": 15,
        "max_seats": 2
    })
    room_id = resp.json()["room_id"]

    with client.websocket_connect(f"/ws/{room_id}/u_fwd") as ws_host:
        msg1 = ws_host.receive_json()
        assert msg1["payload"]["table"]["seats"][0]["player_id"] == "u_fwd"

        with client.websocket_connect(f"/ws/{room_id}/u_hx") as ws_p2:
            _ = ws_host.receive_json()
            msg2 = ws_p2.receive_json()
            assert msg2["payload"]["table"]["seats"][1]["player_id"] == "u_hx"

            # 3rd player (yy) connects when max_seats = 2 -> room is full, remains spectator
            with client.websocket_connect(f"/ws/{room_id}/u_yy") as ws_spec:
                _ = ws_host.receive_json()
                _ = ws_p2.receive_json()
                msg_spec = ws_spec.receive_json()
                seats = msg_spec["payload"]["table"]["seats"]
                assert seats[0]["player_id"] == "u_fwd"
                assert seats[1]["player_id"] == "u_hx"
                assert all(s["player_id"] != "u_yy" for s in seats if s is not None)


def test_host_can_delete_room_via_api():
    client = TestClient(app)

    # 1. Create a room
    resp = client.post("/api/rooms", json={
        "host_player_id": "u_fwd",
        "room_name": "Host Deletion Test Room",
        "buyin_chips": 1000,
        "cash_value": 100.0,
        "small_blind": 5,
        "big_blind": 10,
        "action_timeout": 15,
        "max_seats": 6,
    })
    assert resp.status_code == 200
    room_id = resp.json()["room_id"]
    assert room_manager.get_room(room_id) is not None

    # 2. Non-host (u_hx) attempts to delete room -> 403 Forbidden
    resp_forbidden = client.delete(f"/api/rooms/{room_id}?requester_id=u_hx")
    assert resp_forbidden.status_code == 403
    assert room_manager.get_room(room_id) is not None

    # 3. Host (u_fwd) deletes room -> 200 OK and room deleted
    resp_delete = client.delete(f"/api/rooms/{room_id}?requester_id=u_fwd")
    assert resp_delete.status_code == 200
    assert resp_delete.json()["success"] is True
    assert room_manager.get_room(room_id) is None

    # 4. Deleting non-existent room -> 404 Not Found
    resp_404 = client.delete(f"/api/rooms/{room_id}?requester_id=u_fwd")
    assert resp_404.status_code == 404


def test_admin_can_delete_room_via_api():
    client = TestClient(app)

    # Create room by regular user
    resp = client.post("/api/rooms", json={
        "host_player_id": "u_fwd",
        "room_name": "Admin Deletion Room",
        "buyin_chips": 1000,
        "cash_value": 100.0,
        "small_blind": 5,
        "big_blind": 10,
        "action_timeout": 15,
        "max_seats": 6,
    })
    room_id = resp.json()["room_id"]

    # Admin deletes room
    resp_delete = client.delete(f"/api/rooms/{room_id}?requester_id=u_admin")
    assert resp_delete.status_code == 200
    assert room_manager.get_room(room_id) is None


def test_host_delete_room_ws_broadcast():
    client = TestClient(app)

    resp = client.post("/api/rooms", json={
        "host_player_id": "u_fwd",
        "room_name": "WS Disband Room",
        "buyin_chips": 1000,
        "cash_value": 100.0,
        "small_blind": 5,
        "big_blind": 10,
        "action_timeout": 15,
        "max_seats": 6,
    })
    room_id = resp.json()["room_id"]

    with client.websocket_connect(f"/ws/{room_id}/u_fwd") as ws_host:
        _ = ws_host.receive_json()

        with client.websocket_connect(f"/ws/{room_id}/u_hx") as ws_guest:
            _ = ws_host.receive_json()
            _ = ws_guest.receive_json()

            # Non-host attempts DELETE_ROOM -> ignored
            ws_guest.send_json({"event": EventType.DELETE_ROOM.value})
            assert room_manager.get_room(room_id) is not None

            # Host sends DELETE_ROOM -> broadcast ROOM_DELETED
            ws_host.send_json({"event": EventType.DELETE_ROOM.value})

            del_host = ws_host.receive_json()
            del_guest = ws_guest.receive_json()

            assert del_host["event"] == EventType.ROOM_DELETED.value
            assert del_guest["event"] == EventType.ROOM_DELETED.value
            assert room_manager.get_room(room_id) is None


@pytest.mark.asyncio
async def test_auto_delete_room_when_empty():
    import asyncio
    from backend.app.websocket.connection_manager import ws_manager
    from backend.app.websocket.router import schedule_room_empty_check

    client = TestClient(app)

    resp = client.post("/api/rooms", json={
        "host_player_id": "u_fwd",
        "room_name": "Auto Delete Empty Room",
        "buyin_chips": 1000,
        "cash_value": 100.0,
        "small_blind": 5,
        "big_blind": 10,
        "action_timeout": 15,
        "max_seats": 6,
    })
    room_id = resp.json()["room_id"]
    assert room_manager.get_room(room_id) is not None

    # Connect player
    with client.websocket_connect(f"/ws/{room_id}/u_fwd") as ws:
        _ = ws.receive_json()
        assert room_manager.get_room(room_id) is not None
        assert ws_manager.get_room_connection_count(room_id) >= 1

    # Disconnected now -> ws closed -> trigger fast empty check with 0.1s delay
    schedule_room_empty_check(room_id, delay_seconds=0.1)
    await asyncio.sleep(0.2)

    # Room must be automatically deleted
    assert room_manager.get_room(room_id) is None
