"""Authentication principal binding tests for REST and WebSocket transports."""

import asyncio

import pytest

from fastapi import HTTPException
from backend.app.api.endpoints import (
    CreateRoomRequest,
    UpdateProfileRequest,
    _verify_admin,
    _verify_user,
    create_room,
    delete_room,
    get_my_balance,
    update_profile,
)
from backend.app.services.authentication import AuthenticationError, authenticate_websocket
from backend.app.models.room import RoomConfig
from backend.app.services.room_manager import room_manager
from backend.app.services.user_manager import user_manager


def _login(username: str) -> str:
    user, token = user_manager.authenticate(username, "123")
    assert user is not None and token is not None
    return token


def test_rest_identity_never_falls_back_to_request_ids():
    test1_token = _login("test1")
    test2_token = _login("test2")

    with pytest.raises(HTTPException) as missing_auth:
        _verify_user()
    assert missing_auth.value.status_code == 401
    with pytest.raises(HTTPException) as malformed_auth:
        _verify_user(authorization="Basic forged", token=test1_token)
    assert malformed_auth.value.status_code == 401

    room = asyncio.run(
        create_room(
            CreateRoomRequest(room_name="身份绑定测试"),
            token=test1_token,
            authorization=None,
        )
    )
    room_id = room["room_id"]
    assert room["host_player_id"] == "u_test1"

    with pytest.raises(HTTPException) as forged_admin:
        _verify_admin(token=None)
    assert forged_admin.value.status_code == 401

    profile = update_profile(
        req=UpdateProfileRequest(nickname="只能改自己"),
        token=test1_token,
        authorization=None,
    )
    assert profile["user"]["user_id"] == "u_test1"
    assert user_manager.get_user("u_test2").nickname == "test2"

    my_balance = get_my_balance(token=test1_token, authorization=None)
    assert my_balance["user_id"] == "u_test1"

    with pytest.raises(HTTPException) as forbidden:
        asyncio.run(
            delete_room(
                room_id,
                token=test2_token,
                authorization=None,
            )
        )
    assert forbidden.value.status_code == 403
    assert room_manager.get_room(room_id) is not None


def test_websocket_path_id_cannot_claim_a_bot_or_registered_user():
    token = _login("test1")
    room = room_manager.create_room(
        host_player_id="u_test1",
        config=RoomConfig(max_seats=3),
    )
    bot = room.add_test_bot(seat_index=0)
    assert bot is not None

    spectator, spectator_id = authenticate_websocket(bot["player_id"])
    assert spectator is None
    assert spectator_id != bot["player_id"]

    with pytest.raises(AuthenticationError):
        authenticate_websocket("u_test1")
    with pytest.raises(AuthenticationError):
        authenticate_websocket("u_test2", token=token)
    user, effective_id = authenticate_websocket("u_test1", token=token)
    assert user.user_id == "u_test1"
    assert effective_id == "u_test1"


def test_production_bootstrap_is_explicit_and_tokens_rotate(tmp_path, monkeypatch):
    from backend.app.services.user_manager import UserManager

    monkeypatch.setenv("POKER_ENV", "production")
    monkeypatch.delenv("POKER_BOOTSTRAP_ADMIN_USERNAME", raising=False)
    monkeypatch.delenv("POKER_BOOTSTRAP_ADMIN_PASSWORD", raising=False)
    empty = UserManager(database_path=str(tmp_path / "empty.sqlite3"))
    assert empty.list_users() == []

    monkeypatch.setenv("POKER_BOOTSTRAP_ADMIN_USERNAME", "operator")
    monkeypatch.setenv("POKER_BOOTSTRAP_ADMIN_PASSWORD", "long-production-secret")
    bootstrapped = UserManager(database_path=str(tmp_path / "bootstrapped.sqlite3"))
    assert [user["username"] for user in bootstrapped.list_users()] == ["operator"]
    admin, first_token = bootstrapped.authenticate("operator", "long-production-secret")
    assert admin is not None and first_token is not None
    _, second_token = bootstrapped.authenticate("operator", "long-production-secret")
    assert second_token is not None and second_token != first_token
    assert bootstrapped.get_user_by_token(first_token) is None
    assert bootstrapped.get_user_by_token(second_token).user_id == admin.user_id
