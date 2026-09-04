import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.app.services.user_manager import user_manager
from backend.app.websocket.protocol import EventType


def _auth_ws_url(path: str) -> str:
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


def test_spectate_mode_and_privacy_and_social():
    client = TestClient(app)

    # 1. Create a room with 2 seats
    resp = client.post("/api/rooms", json={
        "host_player_id": "u_test1",
        "room_name": "Spectator Test Room",
        "buyin_chips": 1000,
        "cash_value": 100,
        "small_blind": 10,
        "action_timeout": 15,
        "max_seats": 2,
    })
    assert resp.status_code == 200
    room_id = resp.json()["room_id"]

    # 2. Host (u_test1) connects and is seated
    with client.websocket_connect(f"/ws/{room_id}/u_test1") as ws_host:
        msg1 = ws_host.receive_json()
        assert msg1["payload"]["table"]["seats"][0]["player_id"] == "u_test1"

        # 3. User 2 (u_test2) connects with ?spectate=true
        # Even though seat 1 is empty, u_test2 should NOT be auto-seated!
        with client.websocket_connect(f"/ws/{room_id}/u_test2?spectate=true") as ws_spec:
            _ = ws_host.receive_json()  # host receives room state update
            spec_state = ws_spec.receive_json()

            # Verify spectator is not seated
            seats = spec_state["payload"]["table"]["seats"]
            assert seats[0]["player_id"] == "u_test1"
            assert seats[1] is None
            assert spec_state["payload"]["spectator_count"] == 1
            assert any(s["user_id"] == "u_test2" for s in spec_state["payload"]["spectators"])

            # 4. User 3 (u_test3) connects without spectate param -> sits at empty seat 1
            with client.websocket_connect(f"/ws/{room_id}/u_test3") as ws_p2:
                _ = ws_host.receive_json()
                _ = ws_spec.receive_json()
                msg3 = ws_p2.receive_json()
                assert msg3["payload"]["table"]["seats"][1]["player_id"] == "u_test3"

                # 5. Host starts game
                ws_host.send_json({"event": EventType.START_GAME.value, "payload": {}})
                sound_host = ws_host.receive_json()
                sound_spec = ws_spec.receive_json()
                sound_p2 = ws_p2.receive_json()
                assert sound_host["event"] == EventType.SOUND_EFFECT.value
                assert sound_spec["event"] == EventType.SOUND_EFFECT.value
                assert sound_p2["event"] == EventType.SOUND_EFFECT.value

                state_host = ws_host.receive_json()
                state_spec = ws_spec.receive_json()
                state_p2 = ws_p2.receive_json()

                # Host can see own cards
                host_cards = state_host["payload"]["table"]["seats"][0]["hole_cards"]
                assert len(host_cards) == 2

                # P2 can see own cards
                p2_cards = state_p2["payload"]["table"]["seats"][1]["hole_cards"]
                assert len(p2_cards) == 2

                # PRIVACY CHECK: Spectator must NOT see any player's private cards!
                spec_seats = state_spec["payload"]["table"]["seats"]
                assert spec_seats[0]["hole_cards"] == []
                assert spec_seats[1]["hole_cards"] == []
                assert spec_seats[0]["has_cards"] is True
                assert spec_seats[1]["has_cards"] is True

                # Spectator cannot perform player actions
                ws_spec.send_json({
                    "event": EventType.PLAYER_ACTION.value,
                    "payload": {"action": "CALL", "amount": 20},
                })
                err_msg = ws_spec.receive_json()
                assert err_msg["event"] == EventType.ERROR_MESSAGE.value

                # 6. SOCIAL: Spectator can send chat message
                ws_spec.send_json({
                    "event": EventType.CHAT_MESSAGE.value,
                    "payload": {"message": "加油各位！"},
                })
                chat_host = ws_host.receive_json()
                chat_spec = ws_spec.receive_json()
                chat_p2 = ws_p2.receive_json()

                assert chat_spec["event"] == EventType.CHAT_MESSAGE.value
                assert chat_spec["payload"]["message"] == "加油各位！"
                assert chat_spec["payload"]["player_id"] == "u_test2"
                assert chat_spec["payload"]["is_spectator"] is True
                assert chat_host["payload"]["is_spectator"] is True

                # 7. SOCIAL: Spectator can send emoji reaction
                ws_spec.send_json({
                    "event": EventType.EMOJI_REACTION.value,
                    "payload": {"emoji": "🔥"},
                })
                emoji_host = ws_host.receive_json()
                emoji_spec = ws_spec.receive_json()
                emoji_p2 = ws_p2.receive_json()

                assert emoji_spec["event"] == EventType.EMOJI_REACTION.value
                assert emoji_spec["payload"]["emoji"] == "🔥"
                assert emoji_spec["payload"]["player_id"] == "u_test2"
                assert emoji_spec["payload"]["is_spectator"] is True
                assert emoji_host["payload"]["is_spectator"] is True

                # In-seat player sends emoji -> is_spectator should be False
                ws_host.send_json({
                    "event": EventType.EMOJI_REACTION.value,
                    "payload": {"emoji": "😎"},
                })
                _ = ws_host.receive_json()
                emoji_from_host = ws_spec.receive_json()
                _ = ws_p2.receive_json()
                assert emoji_from_host["event"] == EventType.EMOJI_REACTION.value
                assert emoji_from_host["payload"]["emoji"] == "😎"
                assert emoji_from_host["payload"]["is_spectator"] is False


def test_spectator_stand_up_and_sit_down():
    client = TestClient(app)

    resp = client.post("/api/rooms", json={
        "host_player_id": "u_test1",
        "room_name": "Sit Stand Room",
        "buyin_chips": 1000,
        "cash_value": 100,
        "small_blind": 10,
        "action_timeout": 15,
        "max_seats": 2,
    })
    room_id = resp.json()["room_id"]

    with client.websocket_connect(f"/ws/{room_id}/u_test1") as ws1:
        _ = ws1.receive_json()

        with client.websocket_connect(f"/ws/{room_id}/u_test2") as ws2:
            _ = ws1.receive_json()
            msg2 = ws2.receive_json()
            assert msg2["payload"]["table"]["seats"][1]["player_id"] == "u_test2"

            # u_test2 stands up to become spectator
            ws2.send_json({"event": EventType.STAND_UP.value, "payload": {}})
            state1 = ws1.receive_json()
            state2 = ws2.receive_json()

            # Seat 1 is now empty, u_test2 is now a spectator
            assert state2["payload"]["table"]["seats"][1] is None
            assert state2["payload"]["spectator_count"] == 1
            assert any(s["user_id"] == "u_test2" for s in state2["payload"]["spectators"])

            # u_test2 can sit down again into seat 1
            ws2.send_json({"event": EventType.SIT_DOWN.value, "payload": {"seat_index": 1}})
            sound = ws1.receive_json()
            assert sound["event"] == EventType.SOUND_EFFECT.value
            _ = ws2.receive_json()  # sound on ws2

            new_state1 = ws1.receive_json()
            new_state2 = ws2.receive_json()
            assert new_state2["payload"]["table"]["seats"][1]["player_id"] == "u_test2"
            assert new_state2["payload"]["spectator_count"] == 0
