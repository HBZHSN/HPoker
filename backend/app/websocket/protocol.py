"""WebSocket Message Protocol and Event Definitions for Poker."""

from enum import Enum
from typing import Any, Dict, Optional
import time


class EventType(str, Enum):
    # Client -> Server
    JOIN_ROOM = "JOIN_ROOM"
    SIT_DOWN = "SIT_DOWN"
    STAND_UP = "STAND_UP"
    START_GAME = "START_GAME"
    PLAYER_ACTION = "PLAYER_ACTION"
    REBUY = "REBUY"
    SHOW_CARD = "SHOW_CARD"
    PLAYER_READY = "PLAYER_READY"
    RIT_CHOICE = "RIT_CHOICE"
    USE_TIME_CARD = "USE_TIME_CARD"
    END_ROOM = "END_ROOM"
    DELETE_ROOM = "DELETE_ROOM"
    PING = "PING"

    # Server -> Client
    ROOM_STATE = "ROOM_STATE"
    ACTION_EVENT = "ACTION_EVENT"
    SOUND_EFFECT = "SOUND_EFFECT"
    SETTLEMENT_REPORT = "SETTLEMENT_REPORT"
    ROOM_DELETED = "ROOM_DELETED"
    ERROR_MESSAGE = "ERROR_MESSAGE"
    PONG = "PONG"


def make_message(event: EventType, payload: Dict[str, Any], room_id: Optional[str] = None) -> dict:
    return {
        "event": event.value,
        "room_id": room_id,
        "payload": payload,
        "timestamp": time.time(),
    }
