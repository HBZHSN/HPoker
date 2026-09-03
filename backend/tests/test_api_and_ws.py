import asyncio
import pytest
import httpx
from fastapi.testclient import TestClient

from backend.main import app
from backend.app.services.room_manager import room_manager
from backend.app.websocket.protocol import EventType
from backend.app.models.room import RoomConfig
from backend.app.engine.state_machine import ActionType, Street


def test_rest_api_users_and_rooms():
    client = TestClient(app)

    # 1. Verify public /api/users is disabled to prevent leaking usernames and accounts
    resp = client.get("/api/users")
    assert resp.status_code in (404, 405)

    # Verify public registration is blocked (cannot self-register)
    reg_resp = client.post("/api/users", json={"username": "hacker", "nickname": "hacker"})
    assert reg_resp.status_code in (404, 405)

    # 2. Auth login test with dedicated test account test1
    resp = client.post("/api/auth/login", json={
        "username": "test1",
        "password": "123"
    })
    assert resp.status_code == 200
    auth_data = resp.json()
    token = auth_data["token"]
    assert auth_data["user"]["username"] == "test1"

    # Verify token
    resp_me = client.get(f"/api/auth/me?token={token}")
    assert resp_me.status_code == 200
    assert resp_me.json()["user"]["username"] == "test1"

    # 3. Create a cash game room using test account
    resp = client.post("/api/rooms", json={
        "host_player_id": "u_test1",
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
        default_resp = await client.post("/api/rooms", json={"host_player_id": "u_test1"})
        assert default_resp.status_code == 200
        default_config = default_resp.json()["config"]
        assert default_config["buyin_chips"] == 1000
        assert default_config["cash_value"] == 100.0
        assert default_config["small_blind"] == 10
        assert default_config["big_blind"] == 20

        # A legacy/forged BB value must not override the room's derived BB.
        custom_resp = await client.post(
            "/api/rooms",
            json={"host_player_id": "u_test1", "small_blind": 15, "big_blind": 999},
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
        "host_player_id": "u_test1",
        "room_name": "WS Test Room",
        "buyin_chips": 1000,
        "cash_value": 100.0,
        "small_blind": 5,
        "big_blind": 10,
        "action_timeout": 15,
        "max_seats": 6
    })
    room_id = resp.json()["room_id"]

    # Connect client 1 (test1 - Room Host) via WebSocket
    with client.websocket_connect(f"/ws/{room_id}/u_test1") as ws1:
        # Initial message is ROOM_STATE (with test1 automatically seated at seat 0)
        msg = ws1.receive_json()
        assert msg["event"] == EventType.ROOM_STATE.value
        assert msg["payload"]["room_id"] == room_id
        assert msg["payload"]["table"]["seats"][0] is not None
        assert msg["payload"]["table"]["seats"][0]["player_id"] == "u_test1"

        # Ping / Pong test
        ws1.send_json({"event": EventType.PING.value})
        msg_pong = ws1.receive_json()
        assert msg_pong["event"] == EventType.PONG.value

        # Connect client 2 (test2 - Non-host player) via WebSocket
        with client.websocket_connect(f"/ws/{room_id}/u_test2") as ws2:
            # ws1 receives room state update with test2 auto-seated at seat 1
            msg_ws1_sync = ws1.receive_json()
            assert msg_ws1_sync["event"] == EventType.ROOM_STATE.value
            assert msg_ws1_sync["payload"]["table"]["seats"][1]["player_id"] == "u_test2"

            msg_ws2_sync = ws2.receive_json()
            assert msg_ws2_sync["event"] == EventType.ROOM_STATE.value
            assert msg_ws2_sync["payload"]["table"]["seats"][1]["player_id"] == "u_test2"

            # Non-host (test2) tries to send START_GAME -> rejected / ignored
            ws2.send_json({"event": EventType.START_GAME.value})

            # Non-host (test2) sets ready -> updates ready list
            ws2.send_json({
                "event": EventType.PLAYER_READY.value,
                "payload": {"ready": True}
            })
            msg_ready_1 = ws1.receive_json()
            msg_ready_2 = ws2.receive_json()
            assert "u_test2" in msg_ready_1["payload"]["table"]["ready_player_ids"]
            assert "u_test2" in msg_ready_2["payload"]["table"]["ready_player_ids"]

            # Host (test1) sends START_GAME -> Game starts!
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


def test_websocket_chat_and_emoji_broadcast():
    client = TestClient(app)
    response = client.post("/api/rooms", json={
        "host_player_id": "u_test1",
        "room_name": "Social WS Test",
        "max_seats": 2,
    })
    room_id = response.json()["room_id"]

    with client.websocket_connect(f"/ws/{room_id}/u_test1") as ws_host:
        ws_host.receive_json()
        with client.websocket_connect(f"/ws/{room_id}/u_test2") as ws_guest:
            ws_host.receive_json()
            ws_guest.receive_json()

            ws_guest.send_json({
                "event": EventType.CHAT_MESSAGE.value,
                "payload": {"message": "  好牌！  "},
            })
            for message in (ws_host.receive_json(), ws_guest.receive_json()):
                assert message["event"] == EventType.CHAT_MESSAGE.value
                assert message["room_id"] == room_id
                assert message["payload"]["player_id"] == "u_test2"
                assert message["payload"]["name"] == "test2"
                assert message["payload"]["message"] == "好牌！"
                assert message["payload"]["message_id"]

            ws_host.send_json({
                "event": EventType.EMOJI_REACTION.value,
                "payload": {"emoji": "🔥"},
            })
            for message in (ws_host.receive_json(), ws_guest.receive_json()):
                assert message["event"] == EventType.EMOJI_REACTION.value
                assert message["payload"]["player_id"] == "u_test1"
                assert message["payload"]["name"] == "test1"
                assert message["payload"]["emoji"] == "🔥"
                assert message["payload"]["reaction_id"]


def test_websocket_leave_and_host_kick_stage_settlement():
    client = TestClient(app)
    response = client.post("/api/rooms", json={
        "host_player_id": "u_test1",
        "room_name": "Leave and Kick Room",
        "max_seats": 3,
    })
    room_id = response.json()["room_id"]

    with client.websocket_connect(f"/ws/{room_id}/u_test1") as ws_host:
        ws_host.receive_json()
        with client.websocket_connect(f"/ws/{room_id}/u_test2") as ws_guest:
            ws_host.receive_json()
            ws_guest.receive_json()

            ws_guest.send_json({"event": EventType.STAND_UP.value, "payload": {}})
            host_state = ws_host.receive_json()
            guest_state = ws_guest.receive_json()
            assert host_state["event"] == EventType.ROOM_STATE.value
            assert host_state["payload"]["table"]["seats"][1] is None
            assert host_state["payload"]["pending_settlements"][0]["reason"] == "leave"
            assert guest_state["payload"]["table"]["seats"][1] is None

        # Rejoin to verify the host can remove a currently seated player.
        with client.websocket_connect(f"/ws/{room_id}/u_test2") as ws_guest:
            host_rejoin_state = ws_host.receive_json()
            if host_rejoin_state["payload"]["table"]["seats"][1] is None:
                host_rejoin_state = ws_host.receive_json()
            assert host_rejoin_state["payload"]["table"]["seats"][1]["player_id"] == "u_test2"
            ws_guest.receive_json()

            ws_host.send_json({
                "event": EventType.KICK_PLAYER.value,
                "payload": {"target_player_id": "u_test2"},
            })
            kicked = ws_guest.receive_json()
            host_after_kick = ws_host.receive_json()

            assert kicked["event"] == EventType.PLAYER_KICKED.value
            assert host_after_kick["event"] == EventType.ROOM_STATE.value
            assert host_after_kick["payload"]["table"]["seats"][1] is None
            assert host_after_kick["payload"]["pending_settlements"][-1]["reason"] == "kick"

            with client.websocket_connect(f"/ws/{room_id}/u_test2") as rejected_guest:
                rejected = rejected_guest.receive_json()
                assert rejected["event"] == EventType.PLAYER_KICKED.value


def test_websocket_rejects_invalid_social_content():
    client = TestClient(app)
    response = client.post("/api/rooms", json={
        "host_player_id": "u_test1",
        "room_name": "Social Validation Test",
    })
    room_id = response.json()["room_id"]

    with client.websocket_connect(f"/ws/{room_id}/u_test1") as ws:
        ws.receive_json()

        ws.send_json({
            "event": EventType.CHAT_MESSAGE.value,
            "payload": {"message": "   "},
        })
        error = ws.receive_json()
        assert error["event"] == EventType.ERROR_MESSAGE.value
        assert "1-120" in error["payload"]["message"]

        ws.send_json({
            "event": EventType.EMOJI_REACTION.value,
            "payload": {"emoji": "not-an-emoji"},
        })
        error = ws.receive_json()
        assert error["event"] == EventType.ERROR_MESSAGE.value
        assert error["payload"]["message"] == "当前无法发送该表情"



@pytest.mark.asyncio
async def test_turn_timeout_and_hand_end_auto_start():
    import asyncio
    from backend.app.websocket.router import trigger_room_turn_timer
    from backend.app.services.timeout_manager import timeout_manager

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
    room = room_manager.create_room(host_player_id="u_test1", config=config)
    room.sit_down_player("u_test1", "test1", 0)
    room.sit_down_player("u_test2", "test2", 1)

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
        "host_player_id": "u_test1",
        "room_name": "Rebuy WS Test",
        "buyin_chips": 1000,
        "cash_value": 100.0,
        "small_blind": 5,
        "big_blind": 10,
        "action_timeout": 15,
        "max_seats": 6
    })
    room_id = resp.json()["room_id"]

    with client.websocket_connect(f"/ws/{room_id}/u_test1") as ws:
        msg = ws.receive_json()
        assert msg["payload"]["table"]["seats"][0]["chips"] == 1000

        # test1 tries to rebuy with 1000 chips -> should fail / not rebuy
        ws.send_json({"event": EventType.REBUY.value})
        room = room_manager.get_room(room_id)
        assert room.table.seats[0].chips == 1000
        assert room.table.seats[0].rebuy_count == 1

        # test1 loses all chips
        room.table.seats[0].chips = 0

        # test1 rebuys now with 0 chips -> succeeds
        ws.send_json({"event": EventType.REBUY.value})
        sound_msg = ws.receive_json()
        assert sound_msg["event"] == EventType.SOUND_EFFECT.value
        assert (sound_msg.get("sound") or sound_msg["payload"].get("sound")) == "rebuy"

        state_msg = ws.receive_json()
        assert state_msg["payload"]["table"]["seats"][0]["chips"] == 1000
        assert state_msg["payload"]["table"]["seats"][0]["rebuy_count"] == 2


def test_auto_seating_when_room_full():
    client = TestClient(app)

    resp = client.post("/api/rooms", json={
        "host_player_id": "u_test1",
        "room_name": "Max 2 Seats Room",
        "buyin_chips": 500,
        "cash_value": 50.0,
        "small_blind": 2,
        "big_blind": 5,
        "action_timeout": 15,
        "max_seats": 2
    })
    room_id = resp.json()["room_id"]

    with client.websocket_connect(f"/ws/{room_id}/u_test1") as ws_host:
        msg1 = ws_host.receive_json()
        assert msg1["payload"]["table"]["seats"][0]["player_id"] == "u_test1"

        with client.websocket_connect(f"/ws/{room_id}/u_test2") as ws_p2:
            _ = ws_host.receive_json()
            msg2 = ws_p2.receive_json()
            assert msg2["payload"]["table"]["seats"][1]["player_id"] == "u_test2"

            # 3rd player (test3) connects when max_seats = 2 -> room is full, remains spectator
            with client.websocket_connect(f"/ws/{room_id}/u_test3") as ws_spec:
                _ = ws_host.receive_json()
                _ = ws_p2.receive_json()
                msg_spec = ws_spec.receive_json()
                seats = msg_spec["payload"]["table"]["seats"]
                assert seats[0]["player_id"] == "u_test1"
                assert seats[1]["player_id"] == "u_test2"
                assert all(s["player_id"] != "u_test3" for s in seats if s is not None)


def test_host_can_delete_room_via_api():
    client = TestClient(app)

    # 1. Create a room
    resp = client.post("/api/rooms", json={
        "host_player_id": "u_test1",
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

    # 2. Non-host (u_test2) attempts to delete room -> 403 Forbidden
    resp_forbidden = client.delete(f"/api/rooms/{room_id}?requester_id=u_test2")
    assert resp_forbidden.status_code == 403
    assert room_manager.get_room(room_id) is not None

    # 3. Host (u_test1) deletes room -> 200 OK and room deleted
    resp_delete = client.delete(f"/api/rooms/{room_id}?requester_id=u_test1")
    assert resp_delete.status_code == 200
    assert resp_delete.json()["success"] is True
    assert room_manager.get_room(room_id) is None

    # 4. Deleting non-existent room -> 404 Not Found
    resp_404 = client.delete(f"/api/rooms/{room_id}?requester_id=u_test1")
    assert resp_404.status_code == 404


def test_host_delete_room_ws_broadcast():
    client = TestClient(app)

    resp = client.post("/api/rooms", json={
        "host_player_id": "u_test1",
        "room_name": "WS Disband Room",
        "buyin_chips": 1000,
        "cash_value": 100.0,
        "small_blind": 5,
        "big_blind": 10,
        "action_timeout": 15,
        "max_seats": 6,
    })
    room_id = resp.json()["room_id"]

    with client.websocket_connect(f"/ws/{room_id}/u_test1") as ws_host:
        _ = ws_host.receive_json()

        with client.websocket_connect(f"/ws/{room_id}/u_test2") as ws_guest:
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


def test_unsettled_room_is_retained_when_empty():
    from backend.app.websocket.router import schedule_room_empty_check

    room = room_manager.create_room(
        host_player_id="u_test1",
        config=RoomConfig(room_name="Reconnectable Empty Room"),
    )
    room_id = room.room_id
    assert room_manager.get_room(room_id) is not None

    # A legacy empty-check request must no longer delete an un-settled room.
    schedule_room_empty_check(room_id, delay_seconds=0.1)

    assert room_manager.get_room(room_id) is not None


def test_room_automatically_deleted_after_settlement():
    client = TestClient(app)

    # 1. Test WebSocket END_ROOM auto dissolution
    resp = client.post("/api/rooms", json={
        "host_player_id": "u_test1",
        "room_name": "Auto Disband WS Table",
        "buyin_chips": 1000,
        "cash_value": 100.0,
        "small_blind": 10,
        "big_blind": 20,
    })
    room_id = resp.json()["room_id"]
    assert room_manager.get_room(room_id) is not None
    assert any(r["room_id"] == room_id for r in client.get("/api/rooms").json())

    with client.websocket_connect(f"/ws/{room_id}/u_test1") as ws_host:
        _ = ws_host.receive_json()  # INITIAL ROOM_STATE

        # Host sends END_ROOM
        ws_host.send_json({"event": EventType.END_ROOM.value, "payload": {"settlement_type": "balance"}})

        # Receive messages until final ROOM_STATE with report
        final_state = None
        for _ in range(5):
            msg = ws_host.receive_json()
            if msg.get("event") == EventType.ROOM_STATE.value:
                final_state = msg
                if msg.get("payload", {}).get("is_ended"):
                    break

        assert final_state is not None
        assert final_state["payload"]["is_ended"] is True
        assert final_state["payload"]["settlement_report"] is not None

        # Room must be automatically deleted from room_manager and not visible in lobby
        assert room_manager.get_room(room_id) is None
        assert not any(r["room_id"] == room_id for r in client.get("/api/rooms").json())

    # 2. Test REST POST /api/rooms/{id}/end auto dissolution
    resp2 = client.post("/api/rooms", json={
        "host_player_id": "u_test1",
        "room_name": "Auto Disband REST Table",
        "buyin_chips": 1000,
        "cash_value": 100.0,
        "small_blind": 10,
        "big_blind": 20,
    })
    room_id2 = resp2.json()["room_id"]
    assert room_manager.get_room(room_id2) is not None

    end_resp = client.post(f"/api/rooms/{room_id2}/end?requester_id=u_test1&settlement_type=balance")
    assert end_resp.status_code == 200
    assert end_resp.json()["room_id"] == room_id2
    assert room_manager.get_room(room_id2) is None
    assert not any(r["room_id"] == room_id2 for r in client.get("/api/rooms").json())


def test_user_privacy_and_balance_endpoints():
    client = TestClient(app)

    # 1. No public user listing or registration
    assert client.get("/api/users").status_code in (404, 405)
    assert client.post("/api/users", json={"username": "hacker"}).status_code in (404, 405)

    # 2. Balance endpoints do not leak username
    overview = client.get("/api/balance/overview").json()
    for u in overview.get("user_balances", []):
        assert "username" not in u

    my_bal = client.get("/api/balance/my?user_id=u_test1").json()
    assert "username" not in my_bal


def test_lobby_online_users_and_websocket_lifecycle():
    client = TestClient(app)

    # 1. Initially without websocket connections, u_test1 is offline
    resp = client.get("/api/lobby/users")
    assert resp.status_code == 200
    users = resp.json()
    assert len(users) > 0
    test1_user = next((u for u in users if u["user_id"] == "u_test1"), None)
    assert test1_user is not None
    assert test1_user["is_online"] is False

    # 2. Connect u_test1 via lobby websocket
    with client.websocket_connect("/ws/lobby/u_test1") as ws:
        msg = ws.receive_json()
        assert msg["event"] == EventType.ONLINE_USERS_UPDATE
        assert "u_test1" in msg["payload"]["online_user_ids"]

        # REST endpoint reflects u_test1 is online
        resp_online = client.get("/api/lobby/users")
        u1_state = next(u for u in resp_online.json() if u["user_id"] == "u_test1")
        assert u1_state["is_online"] is True
        assert u1_state["current_room_id"] is None

        # Ping/Pong test on lobby WS
        ws.send_json({"event": EventType.PING, "payload": {}})
        pong = ws.receive_json()
        assert pong["event"] == EventType.PONG

    # 3. After websocket disconnection, u_test1 becomes offline
    resp_offline = client.get("/api/lobby/users")
    u1_offline = next(u for u in resp_offline.json() if u["user_id"] == "u_test1")
    assert u1_offline["is_online"] is False

    # 4. Multi-user test: u_test1 in lobby, u_test2 in a game room
    create_room_resp = client.post("/api/rooms", json={
        "host_player_id": "u_test2",
        "room_name": "Online Test Table",
        "buyin_chips": 1000,
        "cash_value": 100.0,
        "small_blind": 10,
        "big_blind": 20,
        "action_timeout": 15,
        "max_seats": 6,
    })
    assert create_room_resp.status_code == 200
    r_id = create_room_resp.json()["room_id"]

    with client.websocket_connect("/ws/lobby/u_test1") as lobby_ws:
        init_lobby_msg = lobby_ws.receive_json()
        assert init_lobby_msg["event"] == EventType.ONLINE_USERS_UPDATE

        with client.websocket_connect(f"/ws/{r_id}/u_test2") as room_ws:
            # u_test1 in lobby receives broadcast that u_test2 is online in room
            update_msg = lobby_ws.receive_json()
            assert update_msg["event"] == EventType.ONLINE_USERS_UPDATE
            assert "u_test1" in update_msg["payload"]["online_user_ids"]
            assert "u_test2" in update_msg["payload"]["online_user_ids"]
            assert update_msg["payload"]["user_locations"]["u_test2"] == r_id

            # Verify REST API reflects both online and locations
            resp_both = client.get("/api/lobby/users")
            users_map = {u["user_id"]: u for u in resp_both.json()}
            assert users_map["u_test1"]["is_online"] is True
            assert users_map["u_test1"]["current_room_id"] is None
            assert users_map["u_test2"]["is_online"] is True
            assert users_map["u_test2"]["current_room_id"] == r_id
            assert users_map["u_test2"]["current_room_name"] == "Online Test Table"

    # Both disconnected -> both offline
    resp_all_offline = client.get("/api/lobby/users")
    final_map = {u["user_id"]: u for u in resp_all_offline.json()}
    assert final_map["u_test1"]["is_online"] is False
    assert final_map["u_test2"]["is_online"] is False
