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
    REVEAL_BOARD_CARDS = "REVEAL_BOARD_CARDS"
    PLAYER_READY = "PLAYER_READY"
    RIT_CHOICE = "RIT_CHOICE"
    USE_TIME_CARD = "USE_TIME_CARD"
    USE_EQUITY_ASSISTANT = "USE_EQUITY_ASSISTANT"
    END_ROOM = "END_ROOM"
    KICK_PLAYER = "KICK_PLAYER"
    DELETE_ROOM = "DELETE_ROOM"
    ADD_TEST_BOT = "ADD_TEST_BOT"
    # Short alias retained for lightweight clients that call it ADD_BOT.
    ADD_BOT = "ADD_BOT"
    CHAT_MESSAGE = "CHAT_MESSAGE"
    EMOJI_REACTION = "EMOJI_REACTION"
    PING = "PING"

    # Server -> Client
    ROOM_STATE = "ROOM_STATE"
    ACTION_EVENT = "ACTION_EVENT"
    SOUND_EFFECT = "SOUND_EFFECT"
    SETTLEMENT_REPORT = "SETTLEMENT_REPORT"
    ROOM_DELETED = "ROOM_DELETED"
    PLAYER_KICKED = "PLAYER_KICKED"
    ONLINE_USERS_UPDATE = "ONLINE_USERS_UPDATE"
    ERROR_MESSAGE = "ERROR_MESSAGE"
    PONG = "PONG"


CHAT_MESSAGE_MAX_LENGTH = 120
ALLOWED_EMOJI_REACTIONS = (
    "😀", "😃", "😄", "😁", "😆", "😂", "🤣", "😊", "😇", "🙂",
    "🙃", "😉", "😍", "🥰", "😘", "😋", "😜", "🤪", "🤩", "🥳",
    "😎", "🤓", "🧐", "🤔", "🤫", "🤭", "🫡", "😴", "😢", "😭",
    "😤", "😡", "🤬", "😱", "😨", "🥶", "🥵", "🤢", "🤮", "🤡",
    "👻", "💀", "👽", "🤖", "💩", "👍", "👎", "👏", "🙌", "🫶",
    "🤝", "💪", "🙏", "👊", "✌️", "🤞", "👌", "🤟", "❤️", "🧡",
    "💛", "💚", "💙", "💜", "🖤", "💯", "🔥", "🎉", "🎊", "⭐",
    "✨", "💥", "🏆", "🃏", "♠️", "♥️", "♣️", "♦️",
    "😮", "😯", "😲", "😳", "🥺", "🥹", "😏", "😒", "🙄", "😬",
    "😶", "🫠", "🫣", "🤗", "🤠", "👋", "🤌", "🤏", "👈", "👉",
    "☝️", "👇", "👆", "✋", "🤚", "🖐️", "🖖", "🫰", "🤙", "💅",
    "❓", "❔", "⁉️", "‼️", "❗", "❕", "❌", "⭕", "✅", "⚠️",
    "🔔", "💤", "💢", "💦", "💨", "💫", "🌀", "👀", "🎰", "🎱",
    "🎴", "🪙", "💵", "💸", "💳", "📈", "📉", "🏅", "🥇", "🥈",
    "🥉", "🚀", "🧨", "🎁", "🎈", "🎵", "🎶", "📣", "🐭", "🐹",
    "🐰", "🐻", "🐨", "🐮", "🐷", "🐸", "🐵", "🐔", "🐧", "🐢",
    "🐠", "🐟", "🦉", "🐲", "🦓", "🍎", "🍌", "🍓", "🍒", "🍇",
    "🍩", "🍪", "🌭", "🍟", "🍻", "🥂", "🍷", "☕", "🍵", "🌶️",
    "?", "!", "!!", "???", "？", "！", "！？", "GG", "EZ", "+1",
    "XD", "LOL", "OwO", "ಠ_ಠ", "(ง •̀_•́)ง",
)


def normalize_chat_message(value: Any) -> Optional[str]:
    """Return a compact valid chat message, or None for invalid input."""
    if not isinstance(value, str):
        return None
    message = " ".join(value.split()).strip()
    if not message or len(message) > CHAT_MESSAGE_MAX_LENGTH:
        return None
    return message


def make_message(event: EventType, payload: Dict[str, Any], room_id: Optional[str] = None) -> dict:
    return {
        "event": event.value,
        "room_id": room_id,
        "payload": payload,
        "timestamp": time.time(),
    }
