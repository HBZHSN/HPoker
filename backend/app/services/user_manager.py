"""User Manager service for managing preconfigured users and admin creation."""

from __future__ import annotations
from typing import Dict, List, Optional
import time
import uuid

from backend.app.models.user import User


DEFAULT_PRESET_USERS = [
    {"user_id": "u_admin", "username": "admin", "nickname": "房主 (Admin)", "avatar": "👑", "is_admin": True},
    {"user_id": "u_tom", "username": "tom_dwan", "nickname": "Tom Dwan", "avatar": "🦈", "is_admin": False},
    {"user_id": "u_ivey", "username": "phil_ivey", "nickname": "Phil Ivey", "avatar": "🦁", "is_admin": False},
    {"user_id": "u_antonius", "username": "patrik", "nickname": "Patrik Antonius", "avatar": "🐺", "is_admin": False},
    {"user_id": "u_linus", "username": "llinusllove", "nickname": "Linus Love", "avatar": "🦅", "is_admin": False},
    {"user_id": "u_negr", "username": "kidpoker", "nickname": "Daniel Negreanu", "avatar": "🦊", "is_admin": False},
    {"user_id": "u_garrett", "username": "garrett", "nickname": "Garrett Adelstein", "avatar": "🐯", "is_admin": False},
    {"user_id": "u_durrrr", "username": "durrrr", "nickname": "Durrrr", "avatar": "🐉", "is_admin": False},
    {"user_id": "u_fedik", "username": "fedik", "nickname": "Fedor Holz", "avatar": "🐼", "is_admin": False},
]


class UserManager:
    """Manages preconfigured and dynamically created users without public registration."""

    def __init__(self):
        self._users: Dict[str, User] = {}
        self._init_defaults()

    def _init_defaults(self) -> None:
        now = time.time()
        for u in DEFAULT_PRESET_USERS:
            user = User(
                user_id=u["user_id"],
                username=u["username"],
                nickname=u["nickname"],
                avatar=u["avatar"],
                is_admin=u.get("is_admin", False),
                created_at=now,
            )
            self._users[user.user_id] = user

    def get_user(self, user_id: str) -> Optional[User]:
        return self._users.get(user_id)

    def list_users(self) -> List[dict]:
        return [u.to_dict() for u in self._users.values()]

    def create_user_by_admin(self, username: str, nickname: str, avatar: str = "👤", is_admin: bool = False) -> User:
        """Only backend / admin can create new users."""
        user_id = f"u_{uuid.uuid4().hex[:6]}"
        user = User(
            user_id=user_id,
            username=username,
            nickname=nickname,
            avatar=avatar,
            is_admin=is_admin,
            created_at=time.time(),
        )
        self._users[user_id] = user
        return user


# Global singleton
user_manager = UserManager()
