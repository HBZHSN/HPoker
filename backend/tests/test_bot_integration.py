import asyncio
import json

import httpx
import pytest
from starlette.websockets import WebSocketDisconnect

from backend.main import app
from backend.app.engine.state_machine import ActionType
from backend.app.models.room import RoomConfig
from backend.app.services.room_manager import room_manager
from backend.app.services.timeout_manager import timeout_manager
from backend.app.services.user_manager import user_manager
from backend.app.websocket.protocol import EventType
from backend.app.websocket.router import trigger_room_after_action, websocket_endpoint


class FakeWebSocket:
    """Small in-process WebSocket double for exercising the event router."""

    def __init__(self, events: list[dict]):
        self.events = iter(events)
        self.messages: list[dict] = []

    async def accept(self):
        return None

    async def send_text(self, message: str):
        self.messages.append(json.loads(message))

    async def receive_text(self):
        try:
            return json.dumps(next(self.events))
        except StopIteration:
            raise WebSocketDisconnect(code=1000)

    async def close(self, **kwargs):
        return None


async def create_room(client: httpx.AsyncClient) -> str:
    response = await client.post(
        "/api/rooms",
        json={
            "host_player_id": "u_test1",
            "room_name": "Test Bot Room",
            "buyin_chips": 100,
            "cash_value": 10,
            "small_blind": 1,
            "action_timeout": 15,
            "max_seats": 6,
        },
    )
    assert response.status_code == 200
    return response.json()["room_id"]


@pytest.mark.asyncio
async def test_rest_add_test_bot_is_host_only():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        room_id = await create_room(client)

        forbidden = await client.post(f"/api/rooms/{room_id}/test-bots?requester_id=u_test2")
        assert forbidden.status_code == 403

        allowed = await client.post(f"/api/rooms/{room_id}/test-bots?requester_id=u_test1")
        assert allowed.status_code == 200
        bot_seats = [
            seat for seat in allowed.json()["table"]["seats"] if seat and seat["is_bot"]
        ]
        assert len(bot_seats) == 1
        assert bot_seats[0]["name"] == "测试机器人 1"


@pytest.mark.asyncio
async def test_websocket_add_test_bot_is_host_only():
    room = room_manager.create_room(
        host_player_id="u_test1",
        config=RoomConfig(
            room_name="Test Bot WS Room",
            buyin_chips=100,
            cash_value=10,
            small_blind=1,
            action_timeout=15,
            max_seats=6,
        ),
    )
    room_id = room.room_id
    t1_token = user_manager.get_or_create_token("u_test1")
    t2_token = user_manager.get_or_create_token("u_test2")

    guest_ws = FakeWebSocket([{"event": EventType.ADD_TEST_BOT.value}])
    await websocket_endpoint(guest_ws, room_id, "u_test2", token=t2_token)
    room = room_manager.get_room(room_id)
    assert room is not None
    assert not any(seat and seat.is_bot for seat in room.table.seats)

    host_ws = FakeWebSocket([{"event": EventType.ADD_TEST_BOT.value}])
    await websocket_endpoint(host_ws, room_id, "u_test1", token=t1_token)
    sound_messages = [
        message for message in host_ws.messages if message["event"] == EventType.SOUND_EFFECT.value
    ]
    assert len(sound_messages) == 1
    state_messages = [
        message for message in host_ws.messages if message["event"] == EventType.ROOM_STATE.value
    ]
    assert any(
        seat and seat["is_bot"]
        for seat in state_messages[-1]["payload"]["table"]["seats"]
    )
    timeout_manager.cancel_all_timers(room_id)


def test_bot_action_delay_range():
    from backend.app.websocket.router import get_bot_action_delay
    for _ in range(50):
        delay = get_bot_action_delay()
        assert delay == 0.0


@pytest.mark.asyncio
async def test_bot_automatically_acts_when_its_turn():
    room = room_manager.create_room(
        host_player_id="u_test1",
        config=RoomConfig(
            room_name="Test Bot Action Room",
            buyin_chips=100,
            cash_value=10,
            small_blind=1,
            action_timeout=15,
            max_seats=6,
        ),
    )
    room_id = room.room_id

    room.sit_down_player("u_test1", "test1", 0)
    bot = room.add_test_bot(seat_index=1)
    assert bot is not None
    bot_id = bot["player_id"]

    assert room.table.start_new_hand() is True
    assert room.table.current_turn_seat == 0
    assert room.table.handle_action("u_test1", ActionType.CALL) is True
    assert room.table.current_turn_seat == 1

    await trigger_room_after_action(room_id)
    # Bot acts immediately as soon as equity calculation completes in worker thread
    await asyncio.sleep(1.5)

    bot_seat = next(
        seat for seat in room.table.seats if seat and seat.player_id == bot_id
    )
    assert bot_seat.last_action is not None
    assert any(
        item["player_id"] == bot_id
        for item in room.table.last_action_history
    )
    timeout_manager.cancel_all_timers(room_id)


@pytest.mark.asyncio
async def test_legacy_auto_ready_cannot_skip_server_countdown():
    import time
    room = room_manager.create_room(
        host_player_id='u_test1',
        config=RoomConfig(buyin_chips=100, cash_value=10, small_blind=1),
    )
    assert room.sit_down_player('u_test1', 'Alice', 0, is_test=True)
    assert room.sit_down_player('u_test2', 'Bob', 1, is_test=True)
    assert room.table.start_new_hand()
    actor = room.table.seats[room.table.current_turn_seat]
    assert room.table.handle_action(actor.player_id, ActionType.FOLD)
    room.table.set_player_ready('u_test2')
    assert room.table.show_card('u_test2', card_index=0)
    start = time.monotonic()
    ws = FakeWebSocket([{'event': 'PLAYER_READY', 'payload': {'ready': True, 'automatic': True}}])
    await websocket_endpoint(ws, room.room_id, 'u_test1', token=user_manager.get_or_create_token('u_test1'))
    assert time.monotonic() - start < 2.9
    assert room.table.hand_number == 1
    timeout_manager.cancel_all_timers(room.room_id)


@pytest.mark.asyncio
async def test_server_starts_next_hand_without_ready_messages():
    import time
    from backend.app.websocket.connection_manager import ws_manager
    room = room_manager.create_room(
        host_player_id='u_test1',
        config=RoomConfig(buyin_chips=100, cash_value=10, small_blind=1),
    )
    assert room.sit_down_player('u_test1', 'Alice', 0, is_test=True)
    assert room.sit_down_player('u_test2', 'Bob', 1, is_test=True)
    assert room.table.start_new_hand()
    actor = room.table.seats[room.table.current_turn_seat]
    assert room.table.handle_action(actor.player_id, ActionType.FOLD)
    assert 4.9 < room.table.next_hand_at - time.time() <= 5
    await ws_manager.broadcast_room_state(room)
    task = timeout_manager._next_hand_tasks[room.room_id]
    deadline = room.table.next_hand_at
    await ws_manager.broadcast_room_state(room)
    assert timeout_manager._next_hand_tasks[room.room_id] is task
    assert room.table.next_hand_at == deadline
    await asyncio.wait_for(asyncio.shield(task), timeout=6)
    assert room.table.hand_number == 2
    assert room.table.next_hand_at == 0
    timeout_manager.cancel_all_timers(room.room_id)


@pytest.mark.asyncio
async def test_reveal_extends_deadline_and_manual_ready_starts_immediately():
    import time
    room = room_manager.create_room(
        host_player_id='u_test1',
        config=RoomConfig(buyin_chips=100, cash_value=10, small_blind=1),
    )
    assert room.sit_down_player('u_test1', 'Alice', 0, is_test=True)
    assert room.sit_down_player('u_test2', 'Bob', 1, is_test=True)
    assert room.table.start_new_hand()
    actor = room.table.seats[room.table.current_turn_seat]
    assert room.table.handle_action(actor.player_id, ActionType.FOLD)
    deadline = room.table.next_hand_at
    assert room.table.show_card(actor.player_id, card_index=0)
    assert room.table.next_hand_at == deadline  # More than three seconds remain.
    room.table.next_hand_at = time.time() + 1
    assert room.table.show_card(actor.player_id, card_index=1)
    assert 2.9 < room.table.next_hand_at - time.time() <= 3
    deadline = room.table.next_hand_at
    assert room.table.show_card(actor.player_id, show_all=True)
    assert room.table.next_hand_at == deadline  # Repeated reveal is not new.
    assert room.table.show_card(actor.player_id, hide_all=True)
    assert room.table.next_hand_at == deadline
    room.table.set_player_ready('u_test2')
    ws = FakeWebSocket([{'event': 'PLAYER_READY', 'payload': {'ready': True}}])
    await websocket_endpoint(ws, room.room_id, 'u_test1', token=user_manager.get_or_create_token('u_test1'))
    assert room.table.hand_number == 2
    assert room.room_id not in timeout_manager._next_hand_tasks
    timeout_manager.cancel_all_timers(room.room_id)


@pytest.mark.asyncio
async def test_scheduled_start_observes_reveal_extension():
    import time
    from backend.app.websocket.connection_manager import ws_manager
    room = room_manager.create_room(
        host_player_id='u_test1',
        config=RoomConfig(buyin_chips=100, cash_value=10, small_blind=1),
    )
    assert room.sit_down_player('u_test1', 'Alice', 0, is_test=True)
    assert room.sit_down_player('u_test2', 'Bob', 1, is_test=True)
    assert room.table.start_new_hand()
    actor = room.table.seats[room.table.current_turn_seat]
    assert room.table.handle_action(actor.player_id, ActionType.FOLD)
    room.table.next_hand_at = time.time() + 0.1
    await ws_manager.broadcast_room_state(room)
    task = timeout_manager._next_hand_tasks[room.room_id]
    await asyncio.sleep(0.02)
    assert room.table.show_card(actor.player_id, card_index=0)
    await ws_manager.broadcast_room_state(room)
    await asyncio.sleep(0.15)
    assert room.table.hand_number == 1
    await asyncio.wait_for(asyncio.shield(task), timeout=4)
    assert room.table.hand_number == 2
    timeout_manager.cancel_all_timers(room.room_id)
