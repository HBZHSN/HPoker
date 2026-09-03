"""Preconfigured and Admin-managed User Models."""

from __future__ import annotations
from dataclasses import dataclass, field
import hashlib
import time
from typing import Dict, List, Optional
import uuid


def hash_password(password: str) -> str:
    return hashlib.sha256(f"poker_salt_{password}".encode("utf-8")).hexdigest()


@dataclass
class User:
    user_id: str
    username: str
    nickname: str
    avatar: str                       # e.g., "👑", "🦈", "🦁"
    is_admin: bool = False
    is_test: bool = False
    password_hash: str = field(default_factory=lambda: hash_password("123456"))
    created_at: float = field(default_factory=time.time)

    def verify_password(self, password: str) -> bool:
        return self.password_hash == hash_password(password)

    def set_password(self, password: str) -> None:
        self.password_hash = hash_password(password)

    @property
    def is_test_account(self) -> bool:
        return bool(self.is_test or (self.username and self.username.lower().startswith("test")))

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "username": self.username,
            "nickname": self.nickname,
            "avatar": self.avatar,
            "is_admin": self.is_admin,
            "is_test": self.is_test_account,
            "created_at": self.created_at,
        }

    def to_storage_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "username": self.username,
            "nickname": self.nickname,
            "avatar": self.avatar,
            "is_admin": self.is_admin,
            "is_test": self.is_test_account,
            "password_hash": self.password_hash,
            "created_at": self.created_at,
        }

    @classmethod
    def from_storage_dict(cls, data: dict) -> User:
        username = data["username"]
        is_test_val = data.get("is_test")
        if is_test_val is None:
            is_test_val = bool(username.lower().startswith("test"))
        return cls(
            user_id=data["user_id"],
            username=username,
            nickname=data.get("nickname", username),
            avatar=data.get("avatar", "👤"),
            is_admin=data.get("is_admin", False),
            is_test=is_test_val,
            password_hash=data.get("password_hash", hash_password("123")),
            created_at=data.get("created_at", time.time()),
        )

