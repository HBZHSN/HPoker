import json
import re
from pathlib import Path

import pytest

from backend.app.websocket.connection_manager import ConnectionManager
from backend.app.websocket.protocol import (
    ALLOWED_EMOJI_REACTIONS,
    CHAT_MESSAGE_MAX_LENGTH,
    EventType,
    normalize_chat_message,
)


class FakeWebSocket:
    def __init__(self):
        self.messages = []

    async def send_text(self, message):
        self.messages.append(json.loads(message))


def test_normalize_chat_message():
    assert normalize_chat_message("  好牌！\n继续  ") == "好牌！ 继续"
    assert normalize_chat_message("") is None
    assert normalize_chat_message(" \n\t ") is None
    assert normalize_chat_message(123) is None
    assert normalize_chat_message("x" * CHAT_MESSAGE_MAX_LENGTH) is not None
    assert normalize_chat_message("x" * (CHAT_MESSAGE_MAX_LENGTH + 1)) is None


def test_reaction_allowlist_is_fixed_and_unique():
    assert "🔥" in ALLOWED_EMOJI_REACTIONS
    assert "not-an-emoji" not in ALLOWED_EMOJI_REACTIONS
    assert len(ALLOWED_EMOJI_REACTIONS) == len(set(ALLOWED_EMOJI_REACTIONS))
    assert len(ALLOWED_EMOJI_REACTIONS) >= 60


def test_frontend_emoji_picker_matches_server_allowlist():
    source = (
        Path(__file__).parents[2]
        / "frontend"
        / "src"
        / "components"
        / "TableSocialControls.jsx"
    ).read_text(encoding="utf-8")
    array_source = re.search(
        r"export const TABLE_EMOJIS = \[(.*?)\];",
        source,
        flags=re.DOTALL,
    )
    assert array_source is not None
    frontend_emojis = tuple(re.findall(r"'([^']+)'", array_source.group(1)))
    assert frontend_emojis == ALLOWED_EMOJI_REACTIONS


@pytest.mark.asyncio
async def test_ephemeral_event_broadcasts_to_every_room_socket():
    manager = ConnectionManager()
    first = FakeWebSocket()
    second = FakeWebSocket()
    outsider = FakeWebSocket()
    manager.room_connections = {
        "room-1": {first, second},
        "room-2": {outsider},
    }

    await manager.broadcast_event(
        "room-1",
        EventType.CHAT_MESSAGE,
        {"player_id": "u_test1", "message": "好牌！"},
    )

    assert len(first.messages) == 1
    assert len(second.messages) == 1
    assert outsider.messages == []
    assert first.messages[0]["event"] == EventType.CHAT_MESSAGE.value
    assert first.messages[0]["room_id"] == "room-1"
    assert first.messages[0]["payload"] == {
        "player_id": "u_test1",
        "message": "好牌！",
    }
