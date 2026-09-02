"""WebSocket Client for real-time Texas Hold'em gameplay."""

from __future__ import annotations
import asyncio
import json
import logging
from typing import Any, Callable, Dict, Optional
import websockets
from websockets.exceptions import ConnectionClosed

logger = logging.getLogger("poker.cli.ws")


class PokerWsClient:
    """Manages WebSocket connection and event handling for a poker room."""

    def __init__(self, ws_url: str):
        self.ws_url = ws_url
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self._running = False
        self._receive_task: Optional[asyncio.Task] = None
        self._ping_task: Optional[asyncio.Task] = None

        # Callbacks
        self.on_room_state: Optional[Callable[[Dict[str, Any]], Any]] = None
        self.on_sound_effect: Optional[Callable[[str, Dict[str, Any]], Any]] = None
        self.on_error: Optional[Callable[[str], Any]] = None
        self.on_disconnect: Optional[Callable[[], Any]] = None

    @property
    def is_connected(self) -> bool:
        if self.websocket is None:
            return False
        # Modern websockets >= 13.0 (has .state: State.OPEN, etc.)
        state = getattr(self.websocket, "state", None)
        if state is not None:
            # Check string representation or name or value
            state_name = getattr(state, "name", "")
            if state_name in ("OPEN", "1", "State.OPEN"):
                return True
            if state_name in ("CLOSING", "CLOSED", "2", "3"):
                return False
            val = getattr(state, "value", None)
            if val == 1:
                return True
            elif val in (2, 3):
                return False

        # Legacy websockets < 13.0 or explicit mock boolean attributes
        if hasattr(self.websocket, "closed"):
            closed = getattr(self.websocket, "closed")
            if isinstance(closed, bool):
                return not closed
        if hasattr(self.websocket, "open"):
            open_attr = getattr(self.websocket, "open")
            if isinstance(open_attr, bool):
                return open_attr

        return True

    async def connect(self):
        """Establish WebSocket connection and start background listening and pinging."""
        import inspect
        connect_kwargs = {
            "ping_interval": None,  # We manage manual app-level pings
            "max_size": 10_000_000,
        }
        sig = inspect.signature(websockets.connect)
        if "proxy" in sig.parameters:
            connect_kwargs["proxy"] = None

        self.websocket = await websockets.connect(
            self.ws_url,
            **connect_kwargs,
        )
        self._running = True
        self._receive_task = asyncio.create_task(self._listen_loop())
        self._ping_task = asyncio.create_task(self._ping_loop())

    async def disconnect(self):
        """Cleanly disconnect from WebSocket."""
        self._running = False
        if self._ping_task and not self._ping_task.done():
            self._ping_task.cancel()
        if self._receive_task and not self._receive_task.done():
            self._receive_task.cancel()

        if self.websocket:
            try:
                await self.websocket.close()
            except Exception:
                pass
            self.websocket = None

    async def _ping_loop(self):
        """Periodically send PING event to keep connection alive."""
        try:
            while self._running:
                await asyncio.sleep(15)
                if self.is_connected:
                    await self.send_event("PING", {})
        except asyncio.CancelledError:
            pass

    async def _listen_loop(self):
        """Continuously receive messages from WebSocket server."""
        try:
            while self._running and self.websocket:
                msg_text = await self.websocket.recv()
                try:
                    data = json.loads(msg_text)
                except json.JSONDecodeError:
                    continue

                event = data.get("event")
                payload = data.get("payload", {})

                if event == "ROOM_STATE":
                    if self.on_room_state:
                        res = self.on_room_state(payload)
                        if asyncio.iscoroutine(res):
                            await res
                elif event == "SOUND_EFFECT":
                    if self.on_sound_effect:
                        sound = payload.get("sound", "")
                        extra = payload.get("extra", {})
                        res = self.on_sound_effect(sound, extra)
                        if asyncio.iscoroutine(res):
                            await res
                elif event == "ERROR_MESSAGE":
                    if self.on_error:
                        msg = payload.get("message", "Unknown error")
                        res = self.on_error(msg)
                        if asyncio.iscoroutine(res):
                            await res
                elif event == "PONG":
                    pass

        except ConnectionClosed:
            logger.info("WebSocket connection closed")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"WebSocket listen error: {e}")
        finally:
            if self._running and self.on_disconnect:
                res = self.on_disconnect()
                if asyncio.iscoroutine(res):
                    await res

    async def send_event(self, event: str, payload: Dict[str, Any] = None):
        """Send event payload to WebSocket server."""
        if not self.is_connected:
            raise ConnectionError("WebSocket is not connected")

        msg = {
            "event": event,
            "payload": payload or {},
        }
        await self.websocket.send(json.dumps(msg))

    # Helper action wrappers
    async def sit_down(self, seat_index: int):
        await self.send_event("SIT_DOWN", {"seat_index": seat_index})

    async def stand_up(self, seat_index: int):
        await self.send_event("STAND_UP", {"seat_index": seat_index})

    async def start_game(self):
        await self.send_event("START_GAME", {})

    async def player_ready(self, ready: bool = True):
        await self.send_event("PLAYER_READY", {"ready": ready})

    async def player_action(self, action: str, amount: int = 0):
        await self.send_event("PLAYER_ACTION", {"action": action, "amount": amount})

    async def rebuy(self):
        await self.send_event("REBUY", {})

    async def show_card(
        self,
        card_index: Optional[int] = None,
        show_all: bool = False,
        hide_all: bool = False,
        toggle_index: Optional[int] = None,
    ):
        payload = {
            "card_index": card_index,
            "show_all": show_all,
            "hide_all": hide_all,
            "toggle_index": toggle_index,
        }
        await self.send_event("SHOW_CARD", payload)

    async def rit_choice(self, choice: int):
        await self.send_event("RIT_CHOICE", {"choice": choice})

    async def use_time_card(self):
        await self.send_event("USE_TIME_CARD", {})

    async def end_room(self):
        await self.send_event("END_ROOM", {})
