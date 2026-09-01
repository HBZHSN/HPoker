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

    # 2. Auth login test
    resp = client.post("/api/auth/login", json={
        "username": "admin",
        "password": "admin"
    })
    assert resp.status_code == 200
    auth_data = resp.json()
    token = auth_data["token"]
    assert auth_data["user"]["username"] == "admin"

    # 3. Admin creates a user
    resp = client.post("/api/admin/users", json={
        "admin_user_id": "u_admin",
        "username": "new_pro",
        "nickname": "Poker Pro",
        "password": "secret_pass_123",
        "avatar": "🤠",
        "is_admin": False
    })
    assert resp.status_code == 200
    new_user = resp.json()
    assert new_user["username"] == "new_pro"

    # 4. User logs in and updates profile
    resp = client.post("/api/auth/login", json={
        "username": "new_pro",
        "password": "secret_pass_123"
    })
    assert resp.status_code == 200

    resp = client.post("/api/auth/profile", json={
        "user_id": new_user["user_id"],
        "nickname": "Super Poker Pro",
        "username": "super_pro"
    })
    assert resp.status_code == 200
    assert resp.json()["user"]["nickname"] == "Super Poker Pro"

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

    # Connect client 1 (Tom - Room Host) via WebSocket
    with client.websocket_connect(f"/ws/{room_id}/u_tom") as ws1:
        # Initial message is ROOM_STATE (with Tom automatically seated at seat 0!)
        msg = ws1.receive_json()
        assert msg["event"] == EventType.ROOM_STATE.value
        assert msg["payload"]["room_id"] == room_id
        assert msg["payload"]["table"]["seats"][0] is not None
        assert msg["payload"]["table"]["seats"][0]["player_id"] == "u_tom"

        # Ping / Pong test
        ws1.send_json({"event": EventType.PING.value})
        msg_pong = ws1.receive_json()
        assert msg_pong["event"] == EventType.PONG.value

        # Connect client 2 (Ivey - Non-host player) via WebSocket
        with client.websocket_connect(f"/ws/{room_id}/u_ivey") as ws2:
            # ws1 receives room state update with Ivey auto-seated at seat 1
            msg_ws1_sync = ws1.receive_json()
            assert msg_ws1_sync["event"] == EventType.ROOM_STATE.value
            assert msg_ws1_sync["payload"]["table"]["seats"][1]["player_id"] == "u_ivey"

            msg_ws2_sync = ws2.receive_json()
            assert msg_ws2_sync["event"] == EventType.ROOM_STATE.value
            assert msg_ws2_sync["payload"]["table"]["seats"][1]["player_id"] == "u_ivey"

            # Non-host (Ivey) tries to send START_GAME -> rejected / ignored
            ws2.send_json({"event": EventType.START_GAME.value})

            # Non-host (Ivey) sets ready -> updates ready list
            ws2.send_json({
                "event": EventType.PLAYER_READY.value,
                "payload": {"ready": True}
            })
            msg_ready_1 = ws1.receive_json()
            msg_ready_2 = ws2.receive_json()
            assert "u_ivey" in msg_ready_1["payload"]["table"]["ready_player_ids"]
            assert "u_ivey" in msg_ready_2["payload"]["table"]["ready_player_ids"]

            # Host (Tom) sends START_GAME -> Game starts!
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
        "username": "admin",
        "password": "wrong_password"
    })
    assert resp.status_code == 401

    # 2. Non-admin trying to list admin users
    resp = client.get("/api/admin/users?admin_id=u_tom")
    assert resp.status_code == 403

    # 3. Admin updates password of a user
    resp = client.put("/api/admin/users/u_tom", json={
        "admin_user_id": "u_admin",
        "password": "new_tom_password_456"
    })
    assert resp.status_code == 200

    # 4. Verify login with updated password
    resp = client.post("/api/auth/login", json={
        "username": "tom_dwan",
        "password": "new_tom_password_456"
    })
    assert resp.status_code == 200


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
    room = room_manager.create_room(host_player_id="u_tom", config=config)
    room.sit_down_player("u_tom", "Tom Dwan", 0)
    room.sit_down_player("u_ivey", "Phil Ivey", 1)

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
        "host_player_id": "u_tom",
        "room_name": "Rebuy WS Test",
        "buyin_chips": 1000,
        "cash_value": 100.0,
        "small_blind": 5,
        "big_blind": 10,
        "action_timeout": 15,
        "max_seats": 6
    })
    room_id = resp.json()["room_id"]

    with client.websocket_connect(f"/ws/{room_id}/u_tom") as ws:
        msg = ws.receive_json()
        assert msg["payload"]["table"]["seats"][0]["chips"] == 1000

        # Tom tries to rebuy with 1000 chips -> should fail / not rebuy
        ws.send_json({"event": EventType.REBUY.value})
        # Server does not broadcast rebuy sound or changes
        room = room_manager.get_room(room_id)
        assert room.table.seats[0].chips == 1000
        assert room.table.seats[0].rebuy_count == 1

        # Tom loses all chips
        room.table.seats[0].chips = 0

        # Tom rebuys now with 0 chips -> succeeds
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
        "host_player_id": "u_host",
        "room_name": "Max 2 Seats Room",
        "buyin_chips": 500,
        "cash_value": 50.0,
        "small_blind": 2,
        "big_blind": 5,
        "action_timeout": 15,
        "max_seats": 2
    })
    room_id = resp.json()["room_id"]

    with client.websocket_connect(f"/ws/{room_id}/u_host") as ws_host:
        msg1 = ws_host.receive_json()
        assert msg1["payload"]["table"]["seats"][0]["player_id"] == "u_host"

        with client.websocket_connect(f"/ws/{room_id}/u_p2") as ws_p2:
            _ = ws_host.receive_json()
            msg2 = ws_p2.receive_json()
            assert msg2["payload"]["table"]["seats"][1]["player_id"] == "u_p2"

            # 3rd player connects when max_seats = 2 -> room is full, remains spectator
            with client.websocket_connect(f"/ws/{room_id}/u_spectator") as ws_spec:
                _ = ws_host.receive_json()
                _ = ws_p2.receive_json()
                msg_spec = ws_spec.receive_json()
                seats = msg_spec["payload"]["table"]["seats"]
                assert seats[0]["player_id"] == "u_host"
                assert seats[1]["player_id"] == "u_p2"
                assert all(s["player_id"] != "u_spectator" for s in seats if s is not None)


