"""Precompute public table statistics independently of clicks and game actions."""

import asyncio
import logging

from backend.app.services.hand_history_manager import hand_history_manager
from backend.app.services.room_manager import room_manager
from backend.app.websocket.connection_manager import ws_manager

logger = logging.getLogger(__name__)


async def refresh_active_table_statistics():
    for item in room_manager.list_rooms():
        room_id = item['room_id']
        try:
            # One worker at a time, so simultaneous viewers never duplicate work.
            changed = await asyncio.to_thread(hand_history_manager.refresh_table_statistics, room_id)
            room = room_manager.get_room(room_id)
            if changed and room is not None and not room.is_ended:
                await ws_manager.broadcast_room_state(room, checkpoint=False)
        except Exception:
            # Keep the last successful snapshot and retry on the next pass.
            logger.exception('Failed to refresh table statistics for %s', room_id)


async def maintain_table_statistics(stop):
    while not stop.is_set():
        await refresh_active_table_statistics()
        try:
            await asyncio.wait_for(stop.wait(), timeout=1)
        except asyncio.TimeoutError:
            pass
