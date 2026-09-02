"""Reliable WebSocket client for real-time Texas Hold'em room updates."""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
from typing import Any, Callable, Dict, Optional

import websockets
from websockets.exceptions import ConnectionClosed

logger = logging.getLogger("poker.cli.ws")

Callback = Callable[..., Any]


class PokerWsClient:
    """Owns one room connection and dispatches all server event types."""

    def __init__(self, ws_url: str):
        self.ws_url = ws_url
        self.websocket: Any = None
        self._running = False
        self._receive_task: Optional[asyncio.Task] = None
        self._ping_task: Optional[asyncio.Task] = None
        self._send_lock = asyncio.Lock()
        self.last_error: Optional[str] = None

        # Callbacks. Keeping them optional makes the transport easy to test
        # and lets the controller choose how much UI to render.
        self.on_room_state: Optional[Callback] = None
        self.on_action_event: Optional[Callback] = None
        self.on_sound_effect: Optional[Callback] = None
        self.on_settlement_report: Optional[Callback] = None
        self.on_room_deleted: Optional[Callback] = None
        self.on_error: Optional[Callback] = None
        self.on_event: Optional[Callback] = None
        self.on_disconnect: Optional[Callback] = None

    @property
    def is_connected(self) -> bool:
        """Return a useful answer for both old/new websockets and test mocks."""

        websocket = self.websocket
        if websocket is None:
            return False

        state = getattr(websocket, "state", None)
        if state is not None and not callable(state):
            state_name = getattr(state, "name", "")
            if state_name in {"OPEN", "1", "State.OPEN"}:
                return True
            if state_name in {"CLOSING", "CLOSED", "2", "3"}:
                return False
            state_value = getattr(state, "value", None)
            if state_value == 1:
                return True
            if state_value in (2, 3):
                return False

        closed = getattr(websocket, "closed", None)
        if isinstance(closed, bool):
            return not closed
        open_attr = getattr(websocket, "open", None)
        if isinstance(open_attr, bool):
            return open_attr
        return True

    async def connect(self, retries: int = 0, retry_delay: float = 1.0) -> None:
        """Connect and start listener/heartbeat tasks.

        ``retries`` is opt-in so a typoed URL fails immediately in the normal
        interactive flow, while the controller can request a few retries for
        a transient server restart.
        """

        if self.is_connected and self._running:
            return

        connect_kwargs: Dict[str, Any] = {
            "ping_interval": None,
            "max_size": 10_000_000,
        }
        # websockets 12/13 accept no proxy argument; newer releases do. The
        # CLI has its own server URL and should not unexpectedly use env proxy
        # settings for a LAN room.
        try:
            signature = inspect.signature(websockets.connect)
            if "proxy" in signature.parameters:
                connect_kwargs["proxy"] = None
        except (TypeError, ValueError):
            pass

        attempts = max(0, int(retries)) + 1
        for attempt in range(attempts):
            try:
                self.websocket = await websockets.connect(self.ws_url, **connect_kwargs)
                self.last_error = None
                self._running = True
                self._receive_task = asyncio.create_task(self._listen_loop())
                self._ping_task = asyncio.create_task(self._ping_loop())
                return
            except Exception as exc:
                self.last_error = str(exc)
                if attempt + 1 >= attempts:
                    raise
                await asyncio.sleep(max(0.0, retry_delay))

    async def disconnect(self) -> None:
        """Cancel background tasks and close the socket without leaking work."""

        self._running = False
        tasks = [task for task in (self._ping_task, self._receive_task) if task]
        self._ping_task = None
        self._receive_task = None
        for task in tasks:
            if not task.done() and task is not asyncio.current_task():
                task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        websocket = self.websocket
        self.websocket = None
        if websocket is not None:
            try:
                await websocket.close()
            except Exception:
                pass

    async def reconnect(self, retries: int = 2, retry_delay: float = 1.0) -> None:
        """Reconnect the same room socket after a transient disconnect."""

        await self.disconnect()
        await self.connect(retries=retries, retry_delay=retry_delay)

    async def _ping_loop(self) -> None:
        try:
            while self._running:
                await asyncio.sleep(15)
                if self.is_connected:
                    await self.send_event("PING", {})
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.debug("WebSocket heartbeat stopped: %s", exc)

    async def _call_callback(self, callback: Optional[Callback], *args: Any) -> None:
        if not callback:
            return
        result = callback(*args)
        if inspect.isawaitable(result):
            await result

    async def _dispatch(self, data: Dict[str, Any]) -> None:
        event = data.get("event")
        payload = data.get("payload") or {}
        await self._call_callback(self.on_event, event, payload, data)

        if event == "ROOM_STATE":
            await self._call_callback(self.on_room_state, payload)
        elif event == "ACTION_EVENT":
            await self._call_callback(self.on_action_event, payload)
        elif event == "SOUND_EFFECT":
            sound = payload.get("sound", "")
            # Older servers nested metadata under ``extra``; current backend
            # emits player_id beside sound. Support both wire formats.
            extra = payload.get("extra")
            if not isinstance(extra, dict):
                extra = {key: value for key, value in payload.items() if key != "sound"}
            await self._call_callback(self.on_sound_effect, sound, extra)
        elif event == "SETTLEMENT_REPORT":
            await self._call_callback(self.on_settlement_report, payload)
        elif event == "ROOM_DELETED":
            await self._call_callback(self.on_room_deleted, payload)
        elif event == "ERROR_MESSAGE":
            await self._call_callback(self.on_error, payload.get("message", "服务器返回错误"))

    async def _listen_loop(self) -> None:
        websocket = self.websocket
        try:
            while self._running and websocket is not None:
                msg_text = await websocket.recv()
                if isinstance(msg_text, bytes):
                    msg_text = msg_text.decode("utf-8", errors="replace")
                try:
                    data = json.loads(msg_text)
                except (json.JSONDecodeError, TypeError):
                    logger.debug("Ignoring malformed WebSocket message")
                    continue
                if isinstance(data, dict):
                    await self._dispatch(data)
        except ConnectionClosed:
            logger.info("WebSocket connection closed")
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            self.last_error = str(exc)
            logger.error("WebSocket listen error: %s", exc)
        finally:
            was_running = self._running
            self._running = False
            if was_running:
                await self._call_callback(self.on_disconnect)

    async def send_event(self, event: str, payload: Optional[Dict[str, Any]] = None) -> None:
        """Send one protocol event, serializing concurrent user actions."""

        if not self.is_connected:
            raise ConnectionError("WebSocket is not connected")
        message = {"event": event, "payload": payload or {}}
        async with self._send_lock:
            await self.websocket.send(json.dumps(message, ensure_ascii=False))

    # Helper action wrappers
    async def sit_down(self, seat_index: int) -> None:
        await self.send_event("SIT_DOWN", {"seat_index": seat_index})

    async def stand_up(self, seat_index: int) -> None:
        await self.send_event("STAND_UP", {"seat_index": seat_index})

    async def start_game(self) -> None:
        await self.send_event("START_GAME", {})

    async def player_ready(self, ready: bool = True) -> None:
        await self.send_event("PLAYER_READY", {"ready": ready})

    async def player_action(self, action: str, amount: int = 0) -> None:
        await self.send_event("PLAYER_ACTION", {"action": action, "amount": amount})

    async def rebuy(self) -> None:
        await self.send_event("REBUY", {})

    async def show_card(
        self,
        card_index: Optional[int] = None,
        show_all: bool = False,
        hide_all: bool = False,
        toggle_index: Optional[int] = None,
    ) -> None:
        await self.send_event(
            "SHOW_CARD",
            {
                "card_index": card_index,
                "show_all": show_all,
                "hide_all": hide_all,
                "toggle_index": toggle_index,
            },
        )

    async def rit_choice(self, choice: int) -> None:
        await self.send_event("RIT_CHOICE", {"choice": choice})

    async def use_time_card(self) -> None:
        await self.send_event("USE_TIME_CARD", {})

    async def end_room(self) -> None:
        await self.send_event("END_ROOM", {})

    async def delete_room(self) -> None:
        await self.send_event("DELETE_ROOM", {})
