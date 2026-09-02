"""REST API Endpoints for Poker Users, Authentication, and Room Management."""

import json
from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional

from backend.app.services.user_manager import user_manager
from backend.app.services.room_manager import room_manager
from backend.app.services.timeout_manager import timeout_manager
from backend.app.websocket.connection_manager import ws_manager
from backend.app.websocket.protocol import EventType, make_message
from backend.app.models.room import RoomConfig

api_router = APIRouter()


# ----------------- Auth Models & Endpoints -----------------

class LoginRequest(BaseModel):
    username: str
    password: str


class UpdateProfileRequest(BaseModel):
    user_id: str
    nickname: Optional[str] = None
    username: Optional[str] = None
    new_password: Optional[str] = None
    avatar: Optional[str] = None


class AdminCreateUserRequest(BaseModel):
    admin_user_id: str
    username: str
    nickname: str
    password: str = "123"
    avatar: str = "👤"
    is_admin: bool = False


class AdminUpdateUserRequest(BaseModel):
    admin_user_id: str
    username: Optional[str] = None
    nickname: Optional[str] = None
    password: Optional[str] = None
    avatar: Optional[str] = None
    is_admin: Optional[bool] = None


@api_router.post("/auth/login")
def login(req: LoginRequest):
    user, token = user_manager.authenticate(req.username, req.password)
    if not user or not token:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    return {
        "token": token,
        "user": user.to_dict(),
    }


@api_router.get("/auth/me")
def get_current_user(token: Optional[str] = Query(None), authorization: Optional[str] = Header(None)):
    auth_token = token
    if not auth_token and authorization and authorization.startswith("Bearer "):
        auth_token = authorization.split("Bearer ")[1].strip()

    if not auth_token:
        raise HTTPException(status_code=401, detail="未提供认证 Token")

    user = user_manager.get_user_by_token(auth_token)
    if not user:
        raise HTTPException(status_code=401, detail="无效或已过期的 Token")
    return {"user": user.to_dict()}


@api_router.post("/auth/profile")
def update_profile(req: UpdateProfileRequest):
    try:
        user = user_manager.update_profile(
            user_id=req.user_id,
            nickname=req.nickname,
            username=req.username,
            new_password=req.new_password,
            avatar=req.avatar,
        )
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")
        return {"user": user.to_dict(), "message": "资料更新成功"}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


# ----------------- Admin User Management Endpoints -----------------

@api_router.get("/admin/users")
def admin_list_users(admin_id: str = Query(...)):
    admin = user_manager.get_user(admin_id)
    if not admin or not admin.is_admin:
        raise HTTPException(status_code=403, detail="仅管理员有权限访问")
    return user_manager.list_users()


@api_router.post("/admin/users")
def admin_create_user(req: AdminCreateUserRequest):
    try:
        user = user_manager.admin_create_user(
            admin_user_id=req.admin_user_id,
            username=req.username,
            nickname=req.nickname,
            password=req.password,
            avatar=req.avatar,
            is_admin=req.is_admin,
        )
        return user.to_dict()
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


@api_router.put("/admin/users/{user_id}")
def admin_update_user(user_id: str, req: AdminUpdateUserRequest):
    try:
        user = user_manager.admin_update_user(
            admin_user_id=req.admin_user_id,
            target_user_id=user_id,
            username=req.username,
            nickname=req.nickname,
            password=req.password,
            avatar=req.avatar,
            is_admin=req.is_admin,
        )
        return user.to_dict()
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


@api_router.delete("/admin/users/{user_id}")
def admin_delete_user(user_id: str, admin_id: str = Query(...)):
    try:
        ok = user_manager.admin_delete_user(admin_user_id=admin_id, target_user_id=user_id)
        return {"success": ok}
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


# ----------------- Public Users & Rooms Endpoints -----------------

@api_router.get("/users")
def get_users():
    return user_manager.list_users()


@api_router.post("/users")
def create_user(req: AdminCreateUserRequest):
    user = user_manager.admin_create_user(
        admin_user_id=req.admin_user_id if req.admin_user_id else "u_admin",
        username=req.username,
        nickname=req.nickname,
        password=req.password,
        avatar=req.avatar,
        is_admin=req.is_admin,
    )
    return user.to_dict()


class CreateRoomRequest(BaseModel):
    host_player_id: str
    room_name: str = "HPoker 现金桌"
    buyin_chips: int = Field(default=1000, ge=10)
    cash_value: float = Field(default=100.0, ge=1.0)
    small_blind: int = Field(default=10, ge=1)
    action_timeout: int = Field(default=15, ge=5, le=60)
    max_seats: int = Field(default=6, ge=2, le=9)


@api_router.get("/rooms")
def get_rooms():
    return room_manager.list_rooms()


@api_router.post("/rooms")
async def create_room(req: CreateRoomRequest):
    cfg = RoomConfig(
        room_name=req.room_name,
        buyin_chips=req.buyin_chips,
        cash_value=req.cash_value,
        small_blind=req.small_blind,
        action_timeout=req.action_timeout,
        max_seats=req.max_seats,
    )
    room = room_manager.create_room(host_player_id=req.host_player_id, config=cfg)
    # Schedule initial empty room cleanup in case creator never enters room
    from backend.app.websocket.router import schedule_room_empty_check
    schedule_room_empty_check(room.room_id, delay_seconds=30.0)
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


@api_router.delete("/rooms/{room_id}")
@api_router.post("/rooms/{room_id}/delete")
async def delete_room(room_id: str, requester_id: str = Query(...)):
    room = room_manager.get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="房间不存在")

    requester = user_manager.get_user(requester_id)
    is_admin = requester.is_admin if requester else False
    if requester_id != room.host_player_id and not is_admin:
        raise HTTPException(status_code=403, detail="只有房主或管理员有权删除房间")

    # Broadcast ROOM_DELETED to all connected WebSocket clients
    msg = make_message(EventType.ROOM_DELETED, {
        "room_id": room_id,
        "message": "房间已被房主解散",
        "deleted_by": requester_id,
    }, room_id=room_id)
    raw_msg = json.dumps(msg)
    for ws in list(ws_manager.get_room_connections(room_id)):
        try:
            await ws.send_text(raw_msg)
        except Exception:
            pass

    timeout_manager.cancel_all_timers(room_id)
    room_manager.delete_room(room_id)
    await ws_manager.close_room_connections(room_id, reason="Room deleted by host")
    return {"success": True, "message": "房间已成功删除"}
