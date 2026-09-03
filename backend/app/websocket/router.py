"""WebSocket Router and Event Dispatcher for Texas Hold'em Room."""

from __future__ import annotations
import asyncio
import json
import logging
import secrets
import time
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Optional

from backend.app.websocket.protocol import (
    ALLOWED_EMOJI_REACTIONS,
    CHAT_MESSAGE_MAX_LENGTH,
    EventType,
    make_message,
    normalize_chat_message,
)
from backend.app.websocket.connection_manager import ws_manager
from backend.app.services.room_manager import room_manager
from backend.app.services.user_manager import user_manager
from backend.app.services.timeout_manager import timeout_manager
from backend.app.services.bot_player import choose_bot_action
from backend.app.engine.state_machine import ActionType, Street

logger = logging.getLogger("poker.router")
ws_router = APIRouter()
BOT_ACTION_DELAY_MIN: float = 3.0
BOT_ACTION_DELAY_MAX: float = 5.0
BOT_ACTION_DELAY_SECONDS: float = 3.0


def get_bot_action_delay() -> float:
    """Return a randomized bot decision delay between 3 and 5 seconds."""
    low = min(BOT_ACTION_DELAY_MIN, BOT_ACTION_DELAY_MAX)
    high = max(BOT_ACTION_DELAY_MIN, BOT_ACTION_DELAY_MAX)
    if low >= high:
        return low
    return round(low + (secrets.randbelow(int((high - low) * 1000) + 1) / 1000.0), 2)


async def start_all_in_slow_dealing(room_id: str):
    """Orchestrates dramatic step-by-step card dealing when all-in is reached."""
    timeout_manager.cancel_turn_timer(room_id)
    timeout_manager.cancel_rit_timer(room_id)

    async def _deal_flow(r_id: str):
        # Brief initial suspense pause (1.0s)
        await asyncio.sleep(1.0)

        while True:
            r = room_manager.get_room(r_id)
            if not r or r.is_ended:
                return

            step = r.table.deal_all_in_next_step()
            if step is None or step == "SHOWDOWN":
                break

            await ws_manager.broadcast_sound(r_id, "deal")
            await ws_manager.broadcast_room_state(r)
            # Suspense delay between dealing streets: 1.8s
            await asyncio.sleep(1.8)

        # Showdown & Pot Resolution
        r = room_manager.get_room(r_id)
        if not r or r.is_ended:
            return
        r.table.enter_showdown()
        await ws_manager.broadcast_sound(r_id, "win_pot")
        await ws_manager.broadcast_room_state(r)

    timeout_manager.start_deal_task(room_id, _deal_flow)


async def trigger_room_after_action(room_id: str):
    """Handle state transitions and timer scheduling after any game action or street advance."""
    room = room_manager.get_room(room_id)
    if not room or room.is_ended:
        timeout_manager.cancel_all_timers(room_id)
        return

    if room.table.street == Street.RIT_DECISION:
        timeout_manager.cancel_turn_timer(room_id)
        # RIT is deliberately not timed. Cancel any legacy task that may
        # still exist after a server-side reload, then wait for every voter.
        timeout_manager.cancel_rit_timer(room_id)
        await ws_manager.broadcast_sound(room_id, "allin")
        await ws_manager.broadcast_room_state(room)

        if any(
            seat and seat.is_bot and seat.player_id in room.table.rit_voters
            for seat in room.table.seats
        ):
            async def _on_bot_rit_choice(r_id: str):
                r = room_manager.get_room(r_id)
                if not r or r.is_ended or r.table.street != Street.RIT_DECISION:
                    return

                finalized = False
                for seat in r.table.active_in_hand_players:
                    if (
                        seat.is_bot
                        and seat.player_id in r.table.rit_voters
                        and seat.player_id not in r.table.rit_votes
                    ):
                        result, _ = r.table.vote_rit(seat.player_id, 1)
                        if result == "FINALIZED":
                            finalized = True
                            break

                if finalized:
                    timeout_manager.cancel_bot_action(r_id)
                    await ws_manager.broadcast_room_state(r)
                    await start_all_in_slow_dealing(r_id)
                else:
                    await ws_manager.broadcast_room_state(r)

            timeout_manager.start_bot_action_task(
                room_id,
                get_bot_action_delay(),
                _on_bot_rit_choice,
            )

    elif room.table.street not in (Street.IDLE, Street.SHOWDOWN, Street.HAND_END):
        await trigger_room_turn_timer(room_id)
    else:
        timeout_manager.cancel_turn_timer(room_id)


def ensure_room_replenish_task(room_id: str) -> None:
    """Ensure recurring 15-minute background time card replenishment is running for the room."""
    room = room_manager.get_room(room_id)
    if not room or room.is_ended:
        return
    if room_id not in timeout_manager._replenish_tasks:
        async def _on_replenish(r_id: str):
            r = room_manager.get_room(r_id)
            if not r or r.is_ended:
                return
            added = r.add_periodic_time_cards()
            if added > 0:
                await ws_manager.broadcast_sound(r_id, "time_card_gain")
                await ws_manager.broadcast_room_state(r)

        interval = getattr(room.config, "time_card_replenish_interval", 900)
        timeout_manager.start_replenish_task(room_id, interval, _on_replenish)


async def trigger_room_turn_timer(room_id: str):
    """Setup turn timeout for the current active player."""
    room = room_manager.get_room(room_id)
    if not room or room.is_ended or room.table.street in (Street.IDLE, Street.SHOWDOWN, Street.HAND_END, Street.RIT_DECISION):
        timeout_manager.cancel_turn_timer(room_id)
        return

    current_seat_idx = room.table.current_turn_seat
    if current_seat_idx is None:
        timeout_manager.cancel_turn_timer(room_id)
        return

    current_player = room.table.seats[current_seat_idx]
    if not current_player:
        timeout_manager.cancel_turn_timer(room_id)
        return

    if current_player.is_bot:
        timeout_manager.cancel_turn_timer(room_id)

        async def _on_bot_action(r_id: str):
            r = room_manager.get_room(r_id)
            if (
                not r
                or r.is_ended
                or r.table.current_turn_seat != current_seat_idx
                or r.table.street in (Street.IDLE, Street.SHOWDOWN, Street.HAND_END, Street.RIT_DECISION)
            ):
                return

            bot = r.table.seats[current_seat_idx]
            if not bot or not bot.is_bot:
                return

            decision = choose_bot_action(r.table, bot.player_id)
            if decision is None:
                return

            action = decision.action
            amount = decision.amount
            prev_street = r.table.street
            success = r.table.handle_action(
                bot.player_id,
                action,
                raise_total_amount=amount,
            )
            if not success:
                # The decision helper only emits legal actions. This fallback
                # keeps a test hand moving if a state changes between the
                # snapshot and the delayed callback.
                legal = r.table.get_legal_actions(bot.player_id)
                action = (
                    ActionType.CHECK
                    if legal.can_check
                    else ActionType.CALL
                    if legal.can_call
                    else ActionType.FOLD
                )
                amount = legal.call_amount if action is ActionType.CALL else 0
                success = r.table.handle_action(
                    bot.player_id,
                    action,
                    raise_total_amount=amount,
                )

            if not success:
                logger.warning("Test bot action failed for player %s", bot.player_id)
                return

            sound_map = {
                ActionType.FOLD: "fold",
                ActionType.CHECK: "check",
                ActionType.CALL: "call",
                ActionType.BET: "bet",
                ActionType.RAISE: "raise",
                ActionType.ALL_IN: "allin",
            }
            await ws_manager.broadcast_sound(
                r_id,
                sound_map.get(action, "bet"),
                {"player_id": bot.player_id},
            )

            if r.table.street != prev_street:
                if r.table.street in (Street.FLOP, Street.TURN, Street.RIVER):
                    await ws_manager.broadcast_sound(r_id, "deal")
                elif r.table.street in (Street.SHOWDOWN, Street.HAND_END):
                    await ws_manager.broadcast_sound(r_id, "win_pot")

            await ws_manager.broadcast_room_state(r)
            await trigger_room_after_action(r_id)

        timeout_manager.start_bot_action_task(
            room_id,
            get_bot_action_delay(),
            _on_bot_action,
        )
        return

    timeout_duration = (
        room.table.current_turn_duration
        if getattr(room.table, "is_using_time_bank", False)
        else room.config.action_timeout
    )

    async def _on_timeout(r_id: str):
        r = room_manager.get_room(r_id)
        if not r or r.is_ended or r.table.current_turn_seat != current_seat_idx:
            return

        target_player = r.table.seats[current_seat_idx]
        if not target_player:
            return

        # Prioritize auto-consuming time card if available
        if target_player.time_bank_cards > 0:
            target_player.use_time_bank_card()
            r.table.is_using_time_bank = True
            r.table.current_turn_duration = 30
            r.table.turn_started_at = time.time()
            r.table.turn_count += 1
            target_player.last_action = "⏱️ 使用时间卡 +30s"
            await ws_manager.broadcast_sound(r_id, "time_card", {"player_id": target_player.player_id})
            await ws_manager.broadcast_room_state(r)
            timeout_manager.start_turn_timer(
                room_id=r_id,
                timeout_seconds=30,
                on_timeout_callback=_on_timeout
            )
            return

        # No time cards left: fallback to auto CHECK or FOLD
        r.table.is_using_time_bank = False
        r.table.current_turn_duration = r.config.action_timeout

        legal = r.table.get_legal_actions(target_player.player_id)
        if legal.can_check:
            action = ActionType.CHECK
            sound = "check"
        else:
            action = ActionType.FOLD
            sound = "fold"

        prev_street = r.table.street
        success = r.table.handle_action(target_player.player_id, action)
        if not success:
            logger.warning(f"Timeout auto-action {action} failed for player {target_player.player_id}, fallback FOLD")
            r.table.handle_action(target_player.player_id, ActionType.FOLD)
            action = ActionType.FOLD
            sound = "fold"

        await ws_manager.broadcast_sound(r_id, sound, {"player_id": target_player.player_id})

        if r.table.street != prev_street:
            if r.table.street in (Street.FLOP, Street.TURN, Street.RIVER):
                await ws_manager.broadcast_sound(r_id, "deal")
            elif r.table.street in (Street.SHOWDOWN, Street.HAND_END):
                await ws_manager.broadcast_sound(r_id, "win_pot")

        await ws_manager.broadcast_room_state(r)
        await trigger_room_after_action(r_id)

    timeout_manager.start_turn_timer(
        room_id=room_id,
        timeout_seconds=timeout_duration,
        on_timeout_callback=_on_timeout
    )


def schedule_room_empty_check(room_id: str, delay_seconds: float = 3.0) -> None:
    """Retain an empty active room so disconnected clients can resume it.

    Kept as a compatibility hook for older callers. Rooms are now removed only
    by an explicit host/admin disband operation.
    """
    timeout_manager.cancel_empty_room_cleanup(room_id)


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
    avatar = user.avatar if user else "👤"

    # Auto-seat player if room is active and player is not yet seated
    if not room.is_ended:
        is_already_seated = any(s and s.player_id == user_id for s in room.table.seats)
        if not is_already_seated:
            for idx in range(room.config.max_seats):
                if room.table.seats[idx] is None:
                    room.sit_down_player(user_id, nickname, idx, avatar=avatar)
                    break

    timeout_manager.cancel_empty_room_cleanup(room_id)
    await ws_manager.connect(websocket, room_id, user_id)
    ensure_room_replenish_task(room_id)

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

            elif event == EventType.CHAT_MESSAGE:
                message = normalize_chat_message(payload.get("message"))
                if message is None:
                    await ws_manager.send_personal_message(
                        websocket,
                        make_message(
                            EventType.ERROR_MESSAGE,
                            {"message": f"聊天内容需为 1-{CHAT_MESSAGE_MAX_LENGTH} 个字符"},
                            room_id=room_id,
                        ),
                    )
                    continue
                await ws_manager.broadcast_event(
                    room_id,
                    EventType.CHAT_MESSAGE,
                    {
                        "message_id": secrets.token_hex(8),
                        "player_id": user_id,
                        "name": nickname,
                        "avatar": avatar,
                        "message": message,
                    },
                )

            elif event == EventType.EMOJI_REACTION:
                emoji = payload.get("emoji")
                is_seated = any(
                    seat and seat.player_id == user_id
                    for seat in room.table.seats
                )
                if emoji not in ALLOWED_EMOJI_REACTIONS or not is_seated:
                    await ws_manager.send_personal_message(
                        websocket,
                        make_message(
                            EventType.ERROR_MESSAGE,
                            {"message": "当前无法发送该表情"},
                            room_id=room_id,
                        ),
                    )
                    continue
                await ws_manager.broadcast_event(
                    room_id,
                    EventType.EMOJI_REACTION,
                    {
                        "reaction_id": secrets.token_hex(8),
                        "player_id": user_id,
                        "name": nickname,
                        "avatar": avatar,
                        "emoji": emoji,
                    },
                )

            elif event == EventType.SIT_DOWN:
                seat_index = payload.get("seat_index")
                if seat_index is not None:
                    ok = room.sit_down_player(user_id, nickname, seat_index, avatar=avatar)
                    if ok:
                        await ws_manager.broadcast_sound(room_id, "sit")
                        await ws_manager.broadcast_room_state(room)

            elif event == EventType.REBUY:
                ok = room.rebuy_player(user_id)
                if ok:
                    await ws_manager.broadcast_sound(room_id, "rebuy")
                    await ws_manager.broadcast_room_state(room)

            elif event == EventType.START_GAME:
                # Only room host can trigger start of next hand when idle / hand_end
                if user_id == room.host_player_id:
                    for seat in room.table.seats:
                        if seat and seat.is_bot and seat.chips <= 0:
                            room.rebuy_player(seat.player_id)
                    if room.table.can_start_hand():
                        timeout_manager.cancel_all_timers(room_id)
                        ok = room.table.start_new_hand()
                        if ok:
                            await ws_manager.broadcast_sound(room_id, "deal")
                            await ws_manager.broadcast_room_state(room)
                            await trigger_room_after_action(room_id)

            elif event in (EventType.ADD_TEST_BOT, EventType.ADD_BOT):
                # Test bots are intentionally a host-only room control. They
                # can only be seated between hands so they never enter a hand
                # after cards have already been dealt.
                if user_id == room.host_player_id:
                    seat_index = payload.get("seat_index")
                    if seat_index is not None:
                        try:
                            seat_index = int(seat_index)
                        except (TypeError, ValueError):
                            seat_index = None
                    bot = room.add_test_bot(seat_index=seat_index)
                    if bot:
                        await ws_manager.broadcast_sound(room_id, "sit")
                        await ws_manager.broadcast_room_state(room)
                    else:
                        await ws_manager.send_personal_message(
                            websocket,
                            make_message(
                                EventType.ERROR_MESSAGE,
                                {"message": "添加机器人失败：仅能在手牌间隙且有空座时添加"},
                                room_id=room_id,
                            ),
                        )
                else:
                    await ws_manager.send_personal_message(
                        websocket,
                        make_message(
                            EventType.ERROR_MESSAGE,
                            {"message": "只有房主才能添加测试机器人"},
                            room_id=room_id,
                        ),
                    )

            elif event == EventType.PLAYER_ACTION:
                action_str = payload.get("action")
                raw_amount = payload.get("amount", 0)
                try:
                    amount = int(float(raw_amount))
                except (ValueError, TypeError):
                    amount = 0
                try:
                    action = ActionType(action_str)
                except ValueError:
                    continue

                prev_street = room.table.street
                success = room.table.handle_action(user_id, action, raise_total_amount=amount)
                if success:
                    timeout_manager.cancel_turn_timer(room_id)

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
                    await trigger_room_after_action(room_id)

            elif event == EventType.RIT_CHOICE:
                choice = payload.get("choice", 1)
                try:
                    choice = int(choice)
                except (ValueError, TypeError):
                    choice = 1

                res, is_twice = room.table.vote_rit(user_id, choice)
                if res == "FINALIZED":
                    timeout_manager.cancel_rit_timer(room_id)
                    timeout_manager.cancel_bot_action(room_id)
                    await ws_manager.broadcast_room_state(room)
                    await start_all_in_slow_dealing(room_id)
                elif res == "WAITING":
                    await ws_manager.broadcast_room_state(room)

            elif event == EventType.SHOW_CARD:
                card_index = payload.get("card_index")
                show_all = payload.get("show_all", False)
                hide_all = payload.get("hide_all", False)
                toggle_index = payload.get("toggle_index")
                ok = room.table.show_card(user_id, card_index=card_index, show_all=show_all, hide_all=hide_all, toggle_index=toggle_index)
                if ok:
                    await ws_manager.broadcast_room_state(room)

            elif event == EventType.REVEAL_BOARD_CARDS:
                if room.table.reveal_board_cards():
                    await ws_manager.broadcast_sound(room_id, "deal")
                    await ws_manager.broadcast_room_state(room)

            elif event == EventType.PLAYER_READY:
                ready = payload.get("ready", True)
                all_ready = room.table.set_player_ready(user_id, ready)
                if all_ready and room.table.can_start_hand():
                    timeout_manager.cancel_all_timers(room_id)
                    ok = room.table.start_new_hand()
                    if ok:
                        await ws_manager.broadcast_sound(room_id, "deal")
                        await ws_manager.broadcast_room_state(room)
                        await trigger_room_after_action(room_id)
                else:
                    await ws_manager.broadcast_room_state(room)

            elif event == EventType.USE_TIME_CARD:
                if room.table.current_turn_seat is not None:
                    curr_p = room.table.seats[room.table.current_turn_seat]
                    if curr_p and curr_p.player_id == user_id and curr_p.time_bank_cards > 0:
                        ok = room.table.use_time_bank_for_current_player()
                        if ok:
                            timeout_manager.cancel_turn_timer(room_id)
                            await ws_manager.broadcast_sound(room_id, "time_card", {"player_id": user_id})
                            await ws_manager.broadcast_room_state(room)
                            await trigger_room_turn_timer(room_id)

            elif event == EventType.END_ROOM:
                report = room.end_room(requester_id=user_id)
                if report:
                    timeout_manager.cancel_all_timers(room_id)
                    await ws_manager.broadcast_sound(room_id, "win_pot")
                    await ws_manager.broadcast_room_state(room)

            elif event == EventType.DELETE_ROOM:
                requester = user_manager.get_user(user_id)
                is_admin = requester.is_admin if requester else False
                if user_id == room.host_player_id or is_admin:
                    msg = make_message(EventType.ROOM_DELETED, {
                        "room_id": room_id,
                        "message": "房间已被房主解散",
                        "deleted_by": user_id,
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
                    return

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.exception(f"Unexpected WebSocket error: {e}")
    finally:
        r_id, u_id = ws_manager.disconnect(websocket)
        if r_id:
            if ws_manager.get_room_connection_count(r_id) > 0:
                active_r = room_manager.get_room(r_id)
                if active_r and not active_r.is_ended:
                    await ws_manager.broadcast_room_state(active_r)
