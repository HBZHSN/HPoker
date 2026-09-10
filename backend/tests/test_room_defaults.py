"""Administrator-managed defaults for new room creation."""

import httpx
import pytest
from fastapi import HTTPException

from backend.app.api.endpoints import (
    RoomDefaultsUpdateRequest,
    get_room_defaults_config,
    update_room_defaults_config,
)
from backend.app.models.room_defaults import RoomDefaultConfig
from backend.app.models.user import User
from backend.app.services.room_defaults_manager import (
    RoomDefaultsManager,
    room_defaults_manager,
)
from backend.app.services.user_manager import user_manager


def test_room_defaults_round_trip_and_derived_values(tmp_path):
    manager = RoomDefaultsManager(database_path=str(tmp_path / "room-defaults.sqlite3"))

    assert manager.get_config() == RoomDefaultConfig.default()

    saved = manager.update_config(
        buyin_chips=2500,
        cash_value=375.5,
        small_blind=25,
        action_timeout=30,
        max_seats=8,
        assistant_win_ratio=0.85,
        updated_by="admin-id",
    )
    assert saved.to_dict() == {
        "buyin_chips": 2500,
        "cash_value": 375.5,
        "small_blind": 25,
        "big_blind": 50,
        "action_timeout": 30,
        "max_seats": 8,
        "assistant_win_ratio": 0.85,
        "assistant_win_pct": 85,
    }
    assert RoomDefaultsManager(
        database_path=str(tmp_path / "room-defaults.sqlite3")
    ).get_config() == saved


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("buyin_chips", 9),
        ("buyin_chips", 10.5),
        ("cash_value", -1),
        ("small_blind", 0),
        ("action_timeout", 4),
        ("action_timeout", 61),
        ("max_seats", 1),
        ("max_seats", 10),
        ("assistant_win_ratio", 0.09),
        ("assistant_win_ratio", 1.01),
    ],
)
def test_room_defaults_reject_invalid_values(field, value):
    values = {
        "buyin_chips": 1000,
        "cash_value": 100,
        "small_blind": 10,
        "action_timeout": 15,
        "max_seats": 6,
        "assistant_win_ratio": 0.7,
    }
    values[field] = value

    with pytest.raises(ValueError):
        RoomDefaultConfig.from_values(**values)


def test_room_defaults_api_is_admin_only_for_updates():
    user_manager._users["admin-defaults"] = User(
        user_id="admin-defaults",
        username="admin-defaults",
        nickname="管理员",
        avatar="👑",
        is_admin=True,
    )
    user_manager._users["regular-defaults"] = User(
        user_id="regular-defaults",
        username="regular-defaults",
        nickname="普通用户",
        avatar="👤",
    )
    user_manager._tokens.update(
        {
            "admin-defaults-token": "admin-defaults",
            "regular-defaults-token": "regular-defaults",
        }
    )

    request = RoomDefaultsUpdateRequest(
        buyin_chips=1800,
        cash_value=216,
        small_blind=18,
        action_timeout=25,
        max_seats=7,
        assistant_win_ratio=0.9,
    )
    assert get_room_defaults_config() == RoomDefaultConfig.default().to_dict()

    with pytest.raises(HTTPException) as missing_auth:
        update_room_defaults_config(req=request, authorization=None, token=None)
    assert missing_auth.value.status_code == 401

    with pytest.raises(HTTPException) as regular_user:
        update_room_defaults_config(
            req=request,
            authorization="Bearer regular-defaults-token",
        )
    assert regular_user.value.status_code == 403

    expected = request.model_dump() | {
        "big_blind": 36,
        "assistant_win_pct": 90,
    }
    assert update_room_defaults_config(
        req=request,
        authorization="Bearer admin-defaults-token",
    ) == expected
    assert get_room_defaults_config() == expected


@pytest.mark.asyncio
async def test_create_room_uses_saved_defaults_only_when_fields_are_omitted():
    from backend.main import app

    room_defaults_manager.update_config(
        buyin_chips=2200,
        cash_value=330,
        small_blind=22,
        action_timeout=35,
        max_seats=8,
        assistant_win_ratio=0.8,
        updated_by="admin-defaults",
    )

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        default_response = await client.post(
            "/api/rooms",
            json={"host_player_id": "u_test1", "room_name": "使用管理员默认值"},
        )
        assert default_response.status_code == 200
        default_config = default_response.json()["config"]
        assert default_config["buyin_chips"] == 2200
        assert default_config["cash_value"] == 330
        assert default_config["small_blind"] == 22
        assert default_config["big_blind"] == 44
        assert default_config["action_timeout"] == 35
        assert default_config["max_seats"] == 8
        assert default_config["assistant_win_ratio"] == 0.8

        explicit_response = await client.post(
            "/api/rooms",
            json={
                "host_player_id": "u_test1",
                "room_name": "显式参数优先",
                "buyin_chips": 900,
                "cash_value": 0,
                "small_blind": 9,
                "action_timeout": 10,
                "max_seats": 3,
                "assistant_win_ratio": 0.6,
            },
        )
        assert explicit_response.status_code == 200
        explicit_config = explicit_response.json()["config"]
        assert explicit_config["buyin_chips"] == 900
        assert explicit_config["cash_value"] == 0
        assert explicit_config["small_blind"] == 9
        assert explicit_config["big_blind"] == 18
        assert explicit_config["action_timeout"] == 10
        assert explicit_config["max_seats"] == 3
        assert explicit_config["assistant_win_ratio"] == 0.6
