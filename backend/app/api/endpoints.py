"""REST API Endpoints for Poker Users and Room Management."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional

from backend.app.services.user_manager import user_manager
from backend.app.services.room_manager import room_manager
from backend.app.models.room import RoomConfig

api_router = APIRouter()


class CreateUserRequest(BaseModel):
    username: str
    nickname: str
    avatar: str = "👤"
    is_admin: bool = False


class CreateRoomRequest(BaseModel):
    host_player_id: str
    room_name: str = "GGPoker 现金桌"
    buyin_chips: int = Field(default=1000, ge=10)
    cash_value: float = Field(default=100.0, ge=1.0)
    small_blind: int = Field(default=5, ge=1)
    big_blind: int = Field(default=10, ge=2)
    action_timeout: int = Field(default=15, ge=5, le=60)
    max_seats: int = Field(default=6, ge=2, le=9)


@api_router.get("/users")
def get_users():
    return user_manager.list_users()


@api_router.post("/users")
def create_user(req: CreateUserRequest):
    user = user_manager.create_user_by_admin(
        username=req.username,
        nickname=req.nickname,
        avatar=req.avatar,
        is_admin=req.is_admin
    )
    return user.to_dict()


@api_router.get("/rooms")
def get_rooms():
    return room_manager.list_rooms()


@api_router.post("/rooms")
def create_room(req: CreateRoomRequest):
    cfg = RoomConfig(
        room_name=req.room_name,
        buyin_chips=req.buyin_chips,
        cash_value=req.cash_value,
        small_blind=req.small_blind,
        big_blind=req.big_blind,
        action_timeout=req.action_timeout,
        max_seats=req.max_seats,
    )
    room = room_manager.create_room(host_player_id=req.host_player_id, config=cfg)
    return room.to_dict()


@api_router.get("/rooms/{room_id}")
def get_room_details(room_id: str, viewer_id: Optional[str] = None):
    room = room_manager.get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    return room.to_dict(viewer_player_id=viewer_id)


@api_router.post("/rooms/{room_id}/end")
def end_room(room_id: str, requester_id: str):
    room = room_manager.get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    report = room.end_room(requester_id=requester_id)
    if not report:
        raise HTTPException(status_code=403, detail="Only host can end room or room already ended")
    return report.to_dict()
