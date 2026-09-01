"""Preconfigured and Admin-managed User Models."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional
import uuid


@dataclass
class User:
    user_id: str
    username: str
    nickname: str
    avatar: str                       # e.g., "shark", "lion", "fox", "dragon"
    is_admin: bool = False
    created_at: float = 0.0

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "username": self.username,
            "nickname": self.nickname,
            "avatar": self.avatar,
            "is_admin": self.is_admin,
        }
