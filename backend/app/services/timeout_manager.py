"""Asynchronous Action Timeout and Auto-decision Scheduler."""

from __future__ import annotations
import asyncio
from typing import Dict, Optional, Callable, Awaitable
import logging

logger = logging.getLogger("poker.timeout")


class TimeoutManager:
    """Manages turn countdown timers, RIT voting timers, and slow dealing runout tasks."""

    def __init__(self):
        # room_id -> active turn asyncio.Task
        self._turn_tasks: Dict[str, asyncio.Task] = {}
        # room_id -> active RIT decision asyncio.Task
        self._rit_tasks: Dict[str, asyncio.Task] = {}
        # room_id -> active slow all-in dealing asyncio.Task
        self._deal_tasks: Dict[str, asyncio.Task] = {}
        # room_id -> active recurring replenishment asyncio.Task
        self._replenish_tasks: Dict[str, asyncio.Task] = {}
        # room_id -> delayed test-bot action asyncio.Task
        self._bot_tasks: Dict[str, asyncio.Task] = {}
        # room_id -> active empty room auto-cleanup asyncio.Task
        self._empty_room_tasks: Dict[str, asyncio.Task] = {}
        # (room_id, user_id) -> delayed automatic leave/cash-out task
        self._disconnect_tasks: Dict[tuple[str, str], asyncio.Task] = {}

    def cancel_turn_timer(self, room_id: str) -> None:
        """Cancel existing turn timer for a room if any."""
        task = self._turn_tasks.pop(room_id, None)
        if task and not task.done():
            task.cancel()

    def cancel_rit_timer(self, room_id: str) -> None:
        """Cancel existing RIT voting timer for a room if any."""
        task = self._rit_tasks.pop(room_id, None)
        if task and not task.done():
            task.cancel()

    def cancel_deal_task(self, room_id: str) -> None:
        """Cancel existing slow dealing task for a room if any."""
        task = self._deal_tasks.pop(room_id, None)
        if task and not task.done():
            task.cancel()

    def cancel_replenish_task(self, room_id: str) -> None:
        """Cancel existing replenish task for a room if any."""
        task = self._replenish_tasks.pop(room_id, None)
        if task and not task.done():
            task.cancel()

    def cancel_bot_action(self, room_id: str) -> None:
        """Cancel a delayed test-bot action for a room if any."""
        task = self._bot_tasks.pop(room_id, None)
        try:
            current_task = asyncio.current_task()
        except RuntimeError:
            current_task = None
        if task and task is not current_task and not task.done():
            task.cancel()

    def cancel_empty_room_cleanup(self, room_id: str) -> None:
        """Cancel existing empty room auto-cleanup task for a room if any."""
        task = self._empty_room_tasks.pop(room_id, None)
        if task and not task.done():
            task.cancel()

    def cancel_disconnect_timeout(self, room_id: str, user_id: str) -> None:
        key = (room_id, user_id)
        task = self._disconnect_tasks.pop(key, None)
        try:
            current_task = asyncio.current_task()
        except RuntimeError:
            current_task = None
        if task and task is not current_task and not task.done():
            task.cancel()

    # Backwards-compatible alias
    def cancel_timer(self, room_id: str) -> None:
        self.cancel_turn_timer(room_id)

    def cancel_all_timers(self, room_id: str) -> None:
        """Cancel every background task associated with a room."""
        self.cancel_turn_timer(room_id)
        self.cancel_rit_timer(room_id)
        self.cancel_deal_task(room_id)
        self.cancel_replenish_task(room_id)
        self.cancel_bot_action(room_id)
        self.cancel_empty_room_cleanup(room_id)
        for task_room_id, user_id in tuple(self._disconnect_tasks):
            if task_room_id == room_id:
                self.cancel_disconnect_timeout(task_room_id, user_id)

    def schedule_disconnect_timeout(
        self,
        room_id: str,
        user_id: str,
        delay_seconds: float,
        timeout_callback: Callable[[str, str], Awaitable[None]],
    ) -> None:
        """Cash a disconnected user out after the reconnect grace period."""
        self.cancel_disconnect_timeout(room_id, user_id)
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return

        async def _disconnect_worker():
            current_task = asyncio.current_task()
            key = (room_id, user_id)
            try:
                await asyncio.sleep(delay_seconds)
                await timeout_callback(room_id, user_id)
            except asyncio.CancelledError:
                pass
            except Exception as exc:
                logger.exception(
                    "Error in disconnect timeout for %s/%s: %s",
                    room_id,
                    user_id,
                    exc,
                )
            finally:
                if self._disconnect_tasks.get(key) is current_task:
                    self._disconnect_tasks.pop(key, None)

        self._disconnect_tasks[(room_id, user_id)] = loop.create_task(
            _disconnect_worker()
        )

    def schedule_empty_room_cleanup(
        self,
        room_id: str,
        delay_seconds: float,
        cleanup_callback: Callable[[str], Awaitable[None]]
    ) -> None:
        """Schedule an auto-cleanup task if room stays empty for delay_seconds."""
        self.cancel_empty_room_cleanup(room_id)

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            async def _empty_room_worker():
                current_task = asyncio.current_task()
                try:
                    await asyncio.sleep(delay_seconds)
                    await cleanup_callback(room_id)
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    logger.exception(f"Error in empty room cleanup worker for room {room_id}: {e}")
                finally:
                    if self._empty_room_tasks.get(room_id) is current_task:
                        self._empty_room_tasks.pop(room_id, None)

            self._empty_room_tasks[room_id] = loop.create_task(_empty_room_worker())

    def start_replenish_task(
        self,
        room_id: str,
        interval_seconds: int,
        on_replenish_callback: Callable[[str], Awaitable[None]]
    ) -> None:
        """Start a recurring background timer for periodic time card replenishment."""
        self.cancel_replenish_task(room_id)

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            async def _replenish_worker():
                current_task = asyncio.current_task()
                try:
                    while True:
                        await asyncio.sleep(interval_seconds)
                        await on_replenish_callback(room_id)
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    logger.exception(f"Error in replenish worker for room {room_id}: {e}")
                finally:
                    if self._replenish_tasks.get(room_id) is current_task:
                        self._replenish_tasks.pop(room_id, None)

            self._replenish_tasks[room_id] = loop.create_task(_replenish_worker())

    def start_turn_timer(
        self,
        room_id: str,
        timeout_seconds: int,
        on_timeout_callback: Callable[[str], Awaitable[None]]
    ) -> None:
        """Start a countdown timer for current player's turn."""
        self.cancel_turn_timer(room_id)

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            async def _turn_worker():
                current_task = asyncio.current_task()
                try:
                    await asyncio.sleep(timeout_seconds)
                    await on_timeout_callback(room_id)
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    logger.exception(f"Error in turn timeout worker for room {room_id}: {e}")
                finally:
                    if self._turn_tasks.get(room_id) is current_task:
                        self._turn_tasks.pop(room_id, None)

            self._turn_tasks[room_id] = loop.create_task(_turn_worker())

    def start_bot_action_task(
        self,
        room_id: str,
        delay_seconds: float,
        on_action_callback: Callable[[str], Awaitable[None]],
    ) -> None:
        """Run a delayed test-bot callback, replacing any previous callback."""
        self.cancel_bot_action(room_id)

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            async def _bot_worker():
                current_task = asyncio.current_task()
                try:
                    await asyncio.sleep(delay_seconds)
                    await on_action_callback(room_id)
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    logger.exception(f"Error in test-bot worker for room {room_id}: {e}")
                finally:
                    if self._bot_tasks.get(room_id) is current_task:
                        self._bot_tasks.pop(room_id, None)

            self._bot_tasks[room_id] = loop.create_task(_bot_worker())

    def start_rit_timer(
        self,
        room_id: str,
        timeout_seconds: int,
        on_timeout_callback: Callable[[str], Awaitable[None]]
    ) -> None:
        """Deprecated no-op; RIT waits for every contender to vote."""
        self.cancel_rit_timer(room_id)

    def start_deal_task(
        self,
        room_id: str,
        deal_coroutine: Callable[[str], Awaitable[None]]
    ) -> None:
        """Start background slow dealing task."""
        self.cancel_deal_task(room_id)

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            async def _deal_worker():
                current_task = asyncio.current_task()
                try:
                    await deal_coroutine(room_id)
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    logger.exception(f"Error in slow dealing task for room {room_id}: {e}")
                finally:
                    if self._deal_tasks.get(room_id) is current_task:
                        self._deal_tasks.pop(room_id, None)

            self._deal_tasks[room_id] = loop.create_task(_deal_worker())

    # Backwards-compatible alias
    def start_timer(
        self,
        room_id: str,
        timeout_seconds: int,
        on_timeout_callback: Callable[[str], Awaitable[None]]
    ) -> None:
        self.start_turn_timer(room_id, timeout_seconds, on_timeout_callback)


# Global singleton
timeout_manager = TimeoutManager()
