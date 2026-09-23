import httpx
import pytest
from fastapi import HTTPException

from backend.main import app
from backend.app.api.endpoints import JevSettingsRequest, get_jev_settings, update_jev_settings
from backend.app.models.room import RoomConfig
from backend.app.models.user import User
from backend.app.services.balance_manager import balance_manager
from backend.app.services.hand_history_manager import hand_history_manager
from backend.app.services.jev_assistant import jev_assistant
from backend.app.services.room_manager import room_manager
from backend.app.services.user_manager import user_manager


def test_admin_jev_settings_keep_key_private():
    assert jev_assistant.public_settings()["fee"] == "0.01"
    admin = User("jev_admin", "jev_admin", "Admin", "👑", is_admin=True)
    user_manager._users[admin.user_id] = admin
    user_manager._tokens.update({"jev_admin_token": admin.user_id, "jev_player_token": "u_test1"})
    with pytest.raises(HTTPException) as denied:
        get_jev_settings(authorization="Bearer jev_player_token", token=None)
    assert denied.value.status_code == 403
    saved = update_jev_settings(JevSettingsRequest(api_key="private-test-key", fee="0.01"),
                                authorization="Bearer jev_admin_token", token=None)
    assert saved["has_key"] is True
    assert "private-test-key" not in str(saved)


@pytest.mark.asyncio
async def test_jev_decision_is_private_cached_and_transfers_fee_once(monkeypatch):
    admin = User("jev_admin", "jev_admin", "Admin", "👑", is_admin=True)
    user_manager._users[admin.user_id] = admin
    user_manager._tokens.update({"jev_admin_token": admin.user_id, "jev_player_token": "u_test1"})
    room = room_manager.create_room("u_test1", RoomConfig(cash_value=0))
    room.table.sit_down("u_test1", "Player", seat_index=0, chips=1000)
    room.table.sit_down("u_test2", "Opponent", seat_index=1, chips=1000)
    room.table.start_new_hand()
    room_manager.checkpoint_room(room)
    actor = room.table.seats[room.table.current_turn_seat]
    assert actor.player_id == "u_test1"

    calls = []
    monkeypatch.setattr(hand_history_manager, "get_table_statistics", lambda room_id, ids: {
        "u_test2": {"hands": 42, "vpip": 30.0, "pfr": 18.0, "three_bet": 6.0,
                    "three_bet_opportunities": 16, "win_rate": 12.0,
                    "collect_rate": 24.0, "showdown_rate": 28.0,
                    "luck": 53, "luck_samples": 42, "updating": False}
    })

    async def fake_recommend(*, api_key, state, legal):
        calls.append((api_key, state, legal))
        assert len(state["hero_cards"]) == 2
        assert all("hole_cards" not in opponent for opponent in state["opponents"])
        assert state["opponents"][0]["public_stats"] == {
            "hands": 42, "vpip": 30.0, "pfr": 18.0, "three_bet": 6.0,
            "three_bet_opportunities": 16, "win_rate": 12.0,
            "collect_rate": 24.0, "showdown_rate": 28.0,
            "luck": 53, "luck_samples": 42, "updating": False,
        }
        return {"recommendation": "call", "probabilities": {"fold": 0.1, "call": 0.7, "raise": 0.2}, "model": "jev-test"}

    monkeypatch.setattr(jev_assistant, "recommend", fake_recommend)
    jev_assistant.update_settings(api_key="private-test-key", fee="1.25", admin_id=admin.user_id)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        url = f"/api/rooms/{room.room_id}/jev-decision"
        assert (await client.post(url)).status_code == 401
        first = await client.post(url, headers={"Authorization": "Bearer jev_player_token"})
        assert first.status_code == 200
        assert first.json()["probabilities"] == {"fold": 0.1, "call": 0.7, "raise": 0.2}
        second = await client.post(url, headers={"Authorization": "Bearer jev_player_token"})
        assert second.json() == first.json()
        assert len(calls) == 1
        assert balance_manager.available_cents("u_test1") == -125
        assert balance_manager.available_cents(admin.user_id) == 125
        assert room.table.seats[0].using_assistant
        assert len(balance_manager.get_user_records("u_test1")) == 1
        room.table.current_turn_seat = 1
        assert (await client.post(url, headers={"Authorization": "Bearer jev_player_token"})).status_code == 409
        assert balance_manager.available_cents("u_test1") == -125
