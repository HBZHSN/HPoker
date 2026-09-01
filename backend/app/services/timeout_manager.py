"""Asynchronous Action Timeout and Auto-decision Scheduler."""

from __future__ import annotations
import asyncio
from typing import Dict, Optional, Callable, Awaitable
import logging

from backend.app.engine.state_machine import ActionType

logger = logging.getLogger("poker.timeout")


class TimeoutManager:
    """Manages turn countdown timers and automated check/fold decisions."""

    def __init__(self):
        # room_id -> active asyncio.Task
        self._tasks: Dict[str, asyncio.Task] = {}

    def cancel_timer(self, room_id: str) -> None:
        """Cancel existing turn timer for a room if any."""
        task = self._tasks.pop(room_id, None)
        if task and not task.done():
            task.cancel()

    def start_timer(
        self,
        room_id: str,
        timeout_seconds: int,
        on_timeout_callback: Callable[[str], Awaitable[None]]
    ) -> None:
        """Start a countdown timer for current player's turn."""
        self.cancel_timer(room_id)

        async def _timer_worker():
            try:
                await asyncio.sleep(timeout_seconds)
                # If we reach here without cancellation, trigger auto action
                await on_timeout_callback(room_id)
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.exception(f"Error in timeout worker for room {room_id}: {e}")
            finally:
                self._tasks.pop(room_id, None)

        self._tasks[room_id] = asyncio.create_task(_timer_worker())


# Global singleton
timeout_manager = TimeoutManager()
