"""Sound correlation survives the authenticated WebSocket action path."""
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.app.models.room import RoomConfig
from backend.app.services.room_manager import room_manager
from backend.app.services.user_manager import user_manager


@pytest.mark.parametrize("request_id", ["local-click-1", None, "x" * 129, {"invalid": True}])
def test_sit_sound_echo_uses_authenticated_identity(request_id):
    user, token = user_manager.authenticate("test1", "123")
    room = room_manager.create_room(
        host_player_id=user.user_id,
        config=RoomConfig(max_seats=3),
    )
    with TestClient(app) as client:
        with client.websocket_connect(f"/ws/{room.room_id}/{user.user_id}?token={token}&spectate=true") as ws:
            ws.send_json({
                "event": "SIT_DOWN",
                "payload": {"seat_index": 0, "player_id": "forged"},
                "sound_request_id": request_id,
            })
            for _ in range(10):
                message = ws.receive_json()
                if message["event"] == "SOUND_EFFECT":
                    payload = message["payload"]
                    assert payload["sound"] == "sit"
                    assert payload["player_id"] == user.user_id
                    if request_id == "local-click-1":
                        assert payload["sound_request_id"] == request_id
                    else:
                        assert "sound_request_id" not in payload
                    break
            else:
                pytest.fail("No sound broadcast for successful sit action")
