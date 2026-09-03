"""REST API Endpoints for Poker Users, Authentication, and Room Management."""

import json
from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional

from backend.app.services.user_manager import user_manager
from backend.app.services.room_manager import room_manager
from backend.app.services.balance_manager import balance_manager
from backend.app.services.timeout_manager import timeout_manager
from backend.app.websocket.connection_manager import ws_manager
from backend.app.websocket.protocol import EventType, make_message
from backend.app.models.room import RoomConfig
from backend.app.models.user import User

api_router = APIRouter()


# ----------------- Auth Models & Endpoints -----------------

class LoginRequest(BaseModel):
    username: str
    password: str


class UpdateProfileRequest(BaseModel):
    user_id: Optional[str] = None
    nickname: Optional[str] = None
    avatar: Optional[str] = None
    old_password: Optional[str] = None
    new_password: Optional[str] = None


class AdminCreateUserRequest(BaseModel):
    admin_user_id: Optional[str] = None
    username: str
    nickname: str
    password: str = "123"
    avatar: str = "👤"
    is_admin: bool = False
    is_test: bool = False


class AdminUpdateUserRequest(BaseModel):
    admin_user_id: Optional[str] = None
    username: Optional[str] = None
    nickname: Optional[str] = None
    password: Optional[str] = None
    avatar: Optional[str] = None
    is_admin: Optional[bool] = None
    is_test: Optional[bool] = None


def _verify_admin(
    authorization: Optional[str] = None,
    token: Optional[str] = None,
    admin_id: Optional[str] = None,
) -> User:
    auth_token = token
    if not auth_token and authorization and authorization.startswith("Bearer "):
        auth_token = authorization.split("Bearer ")[1].strip()

    if auth_token:
        user = user_manager.get_user_by_token(auth_token)
        if user and user.is_admin:
            return user
        if user and not user.is_admin:
            raise HTTPException(status_code=403, detail="仅管理员有权限访问")

    if admin_id:
        user = user_manager.get_user(admin_id)
        if user and user.is_admin:
            return user
        if user and not user.is_admin:
            raise HTTPException(status_code=403, detail="仅管理员有权限访问")

    raise HTTPException(status_code=403, detail="仅管理员有权限访问")


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
def update_profile(
    req: UpdateProfileRequest,
    authorization: Optional[str] = Header(None),
    token: Optional[str] = Query(None),
):
    auth_token = token
    if not auth_token and authorization and authorization.startswith("Bearer "):
        auth_token = authorization.split("Bearer ")[1].strip()

    auth_user = user_manager.get_user_by_token(auth_token) if auth_token else None
    target_user_id = auth_user.user_id if auth_user else req.user_id

    if not target_user_id:
        raise HTTPException(status_code=401, detail="未提供认证信息")

    try:
        user = user_manager.update_profile(
            user_id=target_user_id,
            nickname=req.nickname,
            old_password=req.old_password,
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
def admin_list_users(
    admin_id: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
    token: Optional[str] = Query(None),
):
    _verify_admin(authorization=authorization, token=token, admin_id=admin_id)
    return user_manager.list_users()


@api_router.post("/admin/users")
def admin_create_user(
    req: AdminCreateUserRequest,
    authorization: Optional[str] = Header(None),
    token: Optional[str] = Query(None),
):
    admin = _verify_admin(authorization=authorization, token=token, admin_id=req.admin_user_id)
    try:
        user = user_manager.admin_create_user(
            admin_user_id=admin.user_id,
            username=req.username,
            nickname=req.nickname,
            password=req.password,
            avatar=req.avatar,
            is_admin=req.is_admin,
            is_test=req.is_test,
        )
        return user.to_dict()
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


@api_router.put("/admin/users/{user_id}")
def admin_update_user(
    user_id: str,
    req: AdminUpdateUserRequest,
    authorization: Optional[str] = Header(None),
    token: Optional[str] = Query(None),
):
    admin = _verify_admin(authorization=authorization, token=token, admin_id=req.admin_user_id)
    try:
        user = user_manager.admin_update_user(
            admin_user_id=admin.user_id,
            target_user_id=user_id,
            username=req.username,
            nickname=req.nickname,
            password=req.password,
            avatar=req.avatar,
            is_admin=req.is_admin,
            is_test=req.is_test,
        )
        return user.to_dict()
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


@api_router.delete("/admin/users/{user_id}")
def admin_delete_user(
    user_id: str,
    admin_id: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
    token: Optional[str] = Query(None),
):
    admin = _verify_admin(authorization=authorization, token=token, admin_id=admin_id)
    try:
        ok = user_manager.admin_delete_user(admin_user_id=admin.user_id, target_user_id=user_id)
        return {"success": ok}
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


class CreateRoomRequest(BaseModel):
    host_player_id: str
    room_name: str = "HPoker 现金桌"
    buyin_chips: int = Field(default=1000, ge=10)
    cash_value: float = Field(default=100.0, ge=1.0)
    small_blind: int = Field(default=10, ge=1)
    action_timeout: int = Field(default=15, ge=5, le=60)
    max_seats: int = Field(default=6, ge=2, le=9)


@api_router.get("/lobby/users")
@api_router.get("/lobby/online-users")
def get_lobby_users():
    """List all registered users with their real-time online status and active game room."""
    online_uids = ws_manager.get_online_user_ids()
    users = user_manager.list_users()
    res = []
    for u in users:
        uid = u["user_id"]
        is_online = uid in online_uids
        current_room_id = ws_manager.get_user_room(uid)
        current_room_name = None
        if current_room_id:
            r = room_manager.get_room(current_room_id)
            if r:
                current_room_name = r.config.room_name
        res.append({
            "user_id": u["user_id"],
            "username": u["username"],
            "nickname": u["nickname"],
            "avatar": u["avatar"],
            "is_admin": u.get("is_admin", False),
            "is_test": u.get("is_test", False),
            "is_online": is_online,
            "current_room_id": current_room_id,
            "current_room_name": current_room_name,
        })
    return res


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
    return room.to_dict()


@api_router.get("/rooms/{room_id}")
def get_room_details(room_id: str, viewer_id: Optional[str] = None):
    room = room_manager.get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    return room.to_dict(viewer_player_id=viewer_id)


@api_router.post("/rooms/{room_id}/test-bots")
async def add_test_bot(
    room_id: str,
    requester_id: str = Query(...),
    seat_index: Optional[int] = Query(None, ge=0, le=8),
):
    """Add a virtual random-action bot; only the room host may request it."""
    room = room_manager.get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    if requester_id != room.host_player_id:
        raise HTTPException(status_code=403, detail="Only the room host can add a test bot")

    bot = room.add_test_bot(seat_index=seat_index)
    if not bot:
        raise HTTPException(
            status_code=409,
            detail="Test bots can only be added between hands when an empty seat is available",
        )

    await ws_manager.broadcast_sound(room_id, "sit")
    await ws_manager.broadcast_room_state(room)
    return room.to_dict()


@api_router.post("/rooms/{room_id}/leave")
@api_router.post("/rooms/{room_id}/stand-up")
async def leave_room(room_id: str, requester_id: str = Query(...)):
    """Explicitly leave a seat and keep the cash-out in room settlement staging."""
    room = room_manager.get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    departed = room.leave_player(requester_id)
    if not departed:
        raise HTTPException(
            status_code=409,
            detail="当前无法离开：请确认你已入座，且全下牌局已结束",
        )

    await ws_manager.broadcast_room_state(room)
    from backend.app.websocket.router import trigger_room_after_action
    await trigger_room_after_action(room_id)
    return {"success": True, **room.to_dict(viewer_player_id=requester_id)}


@api_router.post("/rooms/{room_id}/kick")
async def kick_room_player(
    room_id: str,
    requester_id: str = Query(...),
    target_player_id: str = Query(...),
):
    """Let the room host remove one seated player from the table."""
    room = room_manager.get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    if requester_id != room.host_player_id:
        raise HTTPException(status_code=403, detail="Only the room host can kick a player")
    if target_player_id == requester_id:
        raise HTTPException(status_code=400, detail="房主不能踢出自己")

    kicked = room.kick_player(target_player_id)
    if not kicked:
        raise HTTPException(
            status_code=409,
            detail="当前无法踢出该玩家：请确认玩家已入座，且全下牌局已结束",
        )

    await ws_manager.close_user_connections(
        room_id,
        target_player_id,
        reason="Removed by room host",
        message=make_message(
            EventType.PLAYER_KICKED,
            {
                "room_id": room_id,
                "message": "你已被房主移出房间",
                "kicked_by": requester_id,
            },
            room_id=room_id,
        ),
    )
    await ws_manager.broadcast_room_state(room)
    from backend.app.websocket.router import broadcast_lobby_online_users, trigger_room_after_action
    await trigger_room_after_action(room_id)
    await broadcast_lobby_online_users()
    return {"success": True, **room.to_dict(viewer_player_id=requester_id)}


@api_router.post("/rooms/{room_id}/end")
def end_room(room_id: str, requester_id: str = Query(...), settlement_type: str = Query("balance")):
    room = room_manager.get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    try:
        report = room.end_room(requester_id=requester_id, settlement_type=settlement_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not report:
        raise HTTPException(status_code=403, detail="Only host can end room or room already ended")
    timeout_manager.cancel_all_timers(room_id)
    room_manager.delete_room(room_id)
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


# ----------------- Balance & Ledger Endpoints -----------------

class SettleBatchRequest(BaseModel):
    operator_id: str
    include_test: bool = False
    entry_ids: Optional[List[str]] = None


@api_router.get("/balance/overview")
def get_balance_overview(include_test: bool = Query(False)):
    """Get aggregated unsettled user balances and preview of minimal peer-to-peer transfers."""
    balances = balance_manager.get_user_balances(include_test=include_test)
    preview = balance_manager.preview_batch_settlement(include_test=include_test)
    return {
        "user_balances": [b.to_dict() for b in balances],
        "preview": preview,
    }


@api_router.get("/balance/my")
def get_my_balance(user_id: str = Query(...), include_settled: bool = Query(True)):
    """Get a user's pending balance and their match history ledger records."""
    user = user_manager.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    # Find this user's summary in pending balances
    balances = balance_manager.get_user_balances(include_test=user.is_test_account)
    summary = next((b for b in balances if b.user_id == user_id), None)
    records = balance_manager.get_user_records(user_id, include_settled=include_settled)

    return {
        "user_id": user_id,
        "nickname": user.nickname,
        "avatar": user.avatar,
        "is_test": user.is_test_account,
        "pending_net_cash": summary.net_cash if summary else 0.0,
        "pending_net_chips": summary.net_chips if summary else 0,
        "unsettled_games_count": summary.unsettled_games_count if summary else 0,
        "records": records,
    }


@api_router.get("/balance/records")
def list_balance_records(
    include_test: bool = Query(True),
    status: Optional[str] = Query(None),
):
    """List game ledger records with optional filters."""
    return balance_manager.list_entries(include_test=include_test, status=status)


@api_router.get("/balance/batches")
def list_settlement_batches():
    """List all historical one-time batch settlements."""
    return balance_manager.list_batches()


@api_router.get("/balance/batches/{batch_id}")
def get_settlement_batch(batch_id: str):
    """Get details of a settlement batch."""
    batch = balance_manager.get_batch(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="结算批次不存在")
    return batch


@api_router.post("/balance/settle-batch")
def settle_batch(
    req: SettleBatchRequest,
    authorization: Optional[str] = Header(None),
    token: Optional[str] = Query(None),
):
    """Admin executes one-time consolidated debt settlement."""
    operator = _verify_admin(authorization=authorization, token=token, admin_id=req.operator_id)

    try:
        batch = balance_manager.settle_batch(
            operator_id=operator.user_id,
            operator_name=operator.nickname or operator.username,
            include_test=req.include_test,
            entry_ids=req.entry_ids,
        )
        return batch.to_dict()
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


@api_router.delete("/balance/test-records")
def clear_test_records(
    admin_id: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
    token: Optional[str] = Query(None),
):
    """Admin purges test game records to keep the production ledger clean."""
    _verify_admin(authorization=authorization, token=token, admin_id=admin_id)

    deleted_count = balance_manager.clear_test_records()
    return {"deleted_count": deleted_count, "message": f"已清空 {deleted_count} 条测试账单记录"}


@api_router.delete("/balance/all-records")
def clear_all_balance_records(
    admin_id: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
    token: Optional[str] = Query(None),
):
    """Admin clears all ledger entries and settlement batches to restart balance accounting afresh."""
    _verify_admin(authorization=authorization, token=token, admin_id=admin_id)

    cleared_entries, cleared_batches = balance_manager.clear_all_records()
    return {
        "cleared_entries_count": cleared_entries,
        "cleared_batches_count": cleared_batches,
        "message": f"已成功清空所有结算记录（{cleared_entries} 条对局账单，{cleared_batches} 个对账批次），余额中心已重置。"
    }


@api_router.post("/balance/clear-all")
def clear_all_balance_records_post(
    admin_id: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
    token: Optional[str] = Query(None),
):
    """Alias POST endpoint to clear all ledger entries and settlement batches."""
    return clear_all_balance_records(admin_id=admin_id, authorization=authorization, token=token)


# ----------------- Equity Calculation Endpoint -----------------

class EquityCardRequest(BaseModel):
    """A single card, described by either notation ('As') or rank+suit."""
    notation: Optional[str] = None
    rank: Optional[int] = None
    suit: Optional[str] = None


class EquityRequest(BaseModel):
    hero_cards: List[EquityCardRequest]
    board_cards: List[EquityCardRequest] = Field(default_factory=list)
    num_opponents: int = Field(default=1, ge=1, le=8)
    pot_size: Optional[int] = Field(default=None, ge=0)
    to_call: Optional[int] = Field(default=None, ge=0)


@api_router.post("/equity")
async def calculate_equity(req: EquityRequest):
    """Compute poker equity, drawing probabilities, and hand strength.

    Accepts 2 hero hole cards and 0..5 board cards (as notation strings or
    rank+suit pairs). Returns win/tie/lose rates, drawing outcome
    distribution, and projected equity at future streets.

    Runs in a thread pool so CPU-heavy Monte Carlo simulation does not
    block other WebSocket / REST requests.
    """
    import asyncio
    from fastapi.concurrency import run_in_threadpool
    from backend.app.engine.card import Card, Rank, Suit

    def _compute_sync():
        from backend.app.engine.equity import compute_equity

        def _parse(c: EquityCardRequest) -> Card:
            if c.notation:
                return Card.from_str(c.notation)
            if c.rank is not None and c.suit:
                return Card(rank=Rank(c.rank), suit=Suit(c.suit))
            raise ValueError(f"Invalid card: {c}")

        hero = [_parse(c) for c in req.hero_cards]
        board = [_parse(c) for c in req.board_cards]
        if len(hero) != 2:
            raise ValueError("hero_cards must have exactly 2 cards")
        if len(board) > 5:
            raise ValueError("board_cards must have at most 5 cards")
        return compute_equity(hero, board, req.num_opponents, req.pot_size, req.to_call)

    try:
        result = await run_in_threadpool(_compute_sync)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"计算错误: {e}")

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result
