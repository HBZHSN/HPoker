"""WebSocket Router and Event Dispatcher for Texas Hold'em Room."""

from __future__ import annotations
import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Optional

from backend.app.websocket.protocol import EventType, make_message
from backend.app.websocket.connection_manager import ws_manager
from backend.app.services.room_manager import room_manager
from backend.app.services.user_manager import user_manager
from backend.app.services.timeout_manager import timeout_manager
from backend.app.engine.state_machine import ActionType, Street

logger = logging.getLogger("poker.router")
ws_router = APIRouter()


async def trigger_room_turn_timer(room_id: str):
    """Setup turn timeout for the current active player."""
    room = room_manager.get_room(room_id)
    if not room or room.is_ended or room.table.street in (Street.IDLE, Street.SHOWDOWN, Street.HAND_END):
        timeout_manager.cancel_timer(room_id)
        return

    current_seat_idx = room.table.current_turn_seat
    if current_seat_idx is None:
        timeout_manager.cancel_timer(room_id)
        return

    current_player = room.table.seats[current_seat_idx]
    if not current_player:
        timeout_manager.cancel_timer(room_id)
        return

    async def _on_timeout(r_id: str):
        r = room_manager.get_room(r_id)
        if not r or r.is_ended or r.table.current_turn_seat != current_seat_idx:
            return

        legal = r.table.get_legal_actions(current_player.player_id)
        if legal.can_check:
            action = ActionType.CHECK
            sound = "check"
        else:
            action = ActionType.FOLD
            sound = "fold"

        prev_street = r.table.street
        r.table.handle_action(current_player.player_id, action)
        await ws_manager.broadcast_sound(r_id, sound, {"player_id": current_player.player_id})

        if r.table.street != prev_street:
            if r.table.street in (Street.FLOP, Street.TURN, Street.RIVER):
                await ws_manager.broadcast_sound(r_id, "deal")
            elif r.table.street in (Street.SHOWDOWN, Street.HAND_END):
                await ws_manager.broadcast_sound(r_id, "win_pot")

        await ws_manager.broadcast_room_state(r)
        await trigger_room_turn_timer(r_id)

    timeout_manager.start_timer(
        room_id=room_id,
        timeout_seconds=room.config.action_timeout,
        on_timeout_callback=_on_timeout
    )


@ws_router.websocket("/ws/{room_id}/{user_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str, user_id: str):
    room = room_manager.get_room(room_id)
    if not room:
        await websocket.accept()
        await websocket.send_text(json.dumps(make_message(EventType.ERROR_MESSAGE, {"message": "Room not found"})))
        await websocket.close()
        return

    user = user_manager.get_user(user_id)
    nickname = user.nickname if user else f"Player_{user_id[-4:]}"

    await ws_manager.connect(websocket, room_id, user_id)

    # Initial state sync
    await ws_manager.broadcast_room_state(room)

    try:
        while True:
            data_text = await websocket.receive_text()
            try:
                msg = json.loads(data_text)
            except Exception:
                continue

            event = msg.get("event")
            payload = msg.get("payload", {})

            if event == EventType.PING:
                await ws_manager.send_personal_message(websocket, make_message(EventType.PONG, {}))
                continue

            elif event == EventType.SIT_DOWN:
                seat_index = payload.get("seat_index")
                if seat_index is not None:
                    ok = room.sit_down_player(user_id, nickname, seat_index)
                    if ok:
                        await ws_manager.broadcast_sound(room_id, "sit")
                        await ws_manager.broadcast_room_state(room)

            elif event == EventType.STAND_UP:
                seat_index = payload.get("seat_index")
                if seat_index is not None:
                    room.stand_up_player(seat_index)
                    await ws_manager.broadcast_room_state(room)
                    await trigger_room_turn_timer(room_id)

            elif event == EventType.REBUY:
                ok = room.rebuy_player(user_id)
                if ok:
                    await ws_manager.broadcast_sound(room_id, "rebuy")
                    await ws_manager.broadcast_room_state(room)

            elif event == EventType.START_GAME:
                # Any seated player or host can trigger start of next hand when idle
                if room.table.can_start_hand():
                    ok = room.table.start_new_hand()
                    if ok:
                        await ws_manager.broadcast_sound(room_id, "deal")
                        await ws_manager.broadcast_room_state(room)
                        await trigger_room_turn_timer(room_id)

            elif event == EventType.PLAYER_ACTION:
                action_str = payload.get("action")
                amount = payload.get("amount", 0)
                try:
                    action = ActionType(action_str)
                except ValueError:
                    continue

                prev_street = room.table.street
                success = room.table.handle_action(user_id, action, raise_total_amount=amount)
                if success:
                    # Cancel turn timer immediately upon active player action
                    timeout_manager.cancel_timer(room_id)

                    # Sound mapping
                    sound_map = {
                        ActionType.FOLD: "fold",
                        ActionType.CHECK: "check",
                        ActionType.CALL: "call",
                        ActionType.BET: "bet",
                        ActionType.RAISE: "raise",
                        ActionType.ALL_IN: "allin",
                    }
                    sound = sound_map.get(action, "bet")
                    await ws_manager.broadcast_sound(room_id, sound, {"player_id": user_id})

                    # Check if street transitioned
                    if room.table.street != prev_street:
                        if room.table.street in (Street.FLOP, Street.TURN, Street.RIVER):
                            await ws_manager.broadcast_sound(room_id, "deal")
                        elif room.table.street in (Street.SHOWDOWN, Street.HAND_END):
                            await ws_manager.broadcast_sound(room_id, "win_pot")

                    await ws_manager.broadcast_room_state(room)
                    await trigger_room_turn_timer(room_id)

            elif event == EventType.SHOW_CARD:
                card_index = payload.get("card_index")
                show_all = payload.get("show_all", False)
                ok = room.table.show_card(user_id, card_index=card_index, show_all=show_all)
                if ok:
                    await ws_manager.broadcast_room_state(room)

            elif event == EventType.END_ROOM:
                report = room.end_room(requester_id=user_id)
                if report:
                    timeout_manager.cancel_timer(room_id)
                    await ws_manager.broadcast_sound(room_id, "win_pot")
                    await ws_manager.broadcast_room_state(room)

    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        logger.exception(f"Unexpected WebSocket error: {e}")
        ws_manager.disconnect(websocket)
