"""User Manager service for managing preconfigured users, authentication, persistence, and admin creation."""

from __future__ import annotations
import json
import os
import time
from typing import Dict, List, Optional, Tuple
import uuid

from backend.app.models.user import User, hash_password


DEFAULT_PRESET_USERS = [
    {"user_id": "u_admin", "username": "admin", "nickname": "房主 (Admin)", "avatar": "👑", "is_admin": True, "is_test": False, "password": "admin"},
    {"user_id": "u_fwd", "username": "fwd", "nickname": "fwd", "avatar": "🦈", "is_admin": False, "is_test": False, "password": "123"},
    {"user_id": "u_hx", "username": "hx", "nickname": "hx", "avatar": "🦁", "is_admin": False, "is_test": False, "password": "123"},
    {"user_id": "u_yy", "username": "yy", "nickname": "yy", "avatar": "🦊", "is_admin": False, "is_test": False, "password": "123"},
    {"user_id": "u_test1", "username": "test1", "nickname": "test1", "avatar": "🧪", "is_admin": False, "is_test": True, "password": "123"},
    {"user_id": "u_test2", "username": "test2", "nickname": "test2", "avatar": "🧪", "is_admin": False, "is_test": True, "password": "123"},
    {"user_id": "u_test3", "username": "test3", "nickname": "test3", "avatar": "🧪", "is_admin": False, "is_test": True, "password": "123"},
]

DEFAULT_STORAGE_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data",
    "users.json",
)


class UserManager:
    """Manages preconfigured users, persistent storage, authentication, and admin controls."""

    def __init__(self, storage_path: Optional[str] = None):
        if storage_path is not None:
            self.storage_path = storage_path
        else:
            self.storage_path = os.environ.get("USERS_DATA_FILE", DEFAULT_STORAGE_FILE)

        self._users: Dict[str, User] = {}
        self._tokens: Dict[str, str] = {}  # token -> user_id
        self.load_from_storage()

    def load_from_storage(self) -> None:
        """Load users and tokens from persistent JSON storage, ensuring default users exist."""
        self._users.clear()
        self._tokens.clear()

        has_file = False
        if self.storage_path and self.storage_path != ":memory:" and os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for u_data in data.get("users", []):
                        user = User.from_storage_dict(u_data)
                        self._users[user.user_id] = user
                    self._tokens = data.get("tokens", {})
                has_file = True
            except Exception as e:
                print(f"[UserManager] Warning: Failed to load storage from {self.storage_path}: {e}")

        # Ensure preset users exist (admin, fwd, hx, yy, test1, test2, test3)
        modified = False
        existing_usernames = {u.username.lower(): u for u in self._users.values()}
        now = time.time()
        for preset in DEFAULT_PRESET_USERS:
            uname = preset["username"].lower()
            if uname not in existing_usernames:
                pwd = preset.get("password", "123")
                user = User(
                    user_id=preset["user_id"],
                    username=preset["username"],
                    nickname=preset["nickname"],
                    avatar=preset["avatar"],
                    is_admin=preset.get("is_admin", False),
                    is_test=preset.get("is_test", False),
                    password_hash=hash_password(pwd),
                    created_at=now,
                )
                self._users[user.user_id] = user
                existing_usernames[uname] = user
                modified = True
            else:
                existing_user = existing_usernames[uname]
                preset_admin = preset.get("is_admin", False)
                if existing_user.is_admin != preset_admin:
                    existing_user.is_admin = preset_admin
                    modified = True
                preset_test = preset.get("is_test", False)
                if existing_user.is_test != preset_test:
                    existing_user.is_test = preset_test
                    modified = True

        if modified or not has_file:
            self.save_to_storage()

    def save_to_storage(self) -> None:
        """Persist users and tokens to JSON file."""
        if not self.storage_path or self.storage_path == ":memory:":
            return

        try:
            os.makedirs(os.path.dirname(os.path.abspath(self.storage_path)), exist_ok=True)
            payload = {
                "users": [u.to_storage_dict() for u in self._users.values()],
                "tokens": self._tokens,
            }
            tmp_path = f"{self.storage_path}.tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, self.storage_path)
        except Exception as e:
            print(f"[UserManager] Warning: Failed to save storage to {self.storage_path}: {e}")

    def authenticate(self, username: str, password: str) -> Tuple[Optional[User], Optional[str]]:
        """Authenticate user by username and password, return (User, token) if successful."""
        for user in self._users.values():
            if user.username.lower() == username.lower().strip():
                if user.verify_password(password):
                    # Reuse existing token for user or generate a new persistent token
                    existing_token = next((t for t, uid in self._tokens.items() if uid == user.user_id), None)
                    if existing_token:
                        token = existing_token
                    else:
                        token = f"token_{uuid.uuid4().hex}"
                        self._tokens[token] = user.user_id
                        self.save_to_storage()
                    return user, token
                return None, None
        return None, None

    def get_user_by_token(self, token: str) -> Optional[User]:
        if not token:
            return None
        user_id = self._tokens.get(token)
        if not user_id:
            return None
        return self._users.get(user_id)

    def get_user(self, user_id: str) -> Optional[User]:
        return self._users.get(user_id)

    def list_users(self) -> List[dict]:
        return [u.to_dict() for u in self._users.values()]

    def update_profile(
        self,
        user_id: str,
        nickname: Optional[str] = None,
        username: Optional[str] = None,
        old_password: Optional[str] = None,
        new_password: Optional[str] = None,
        avatar: Optional[str] = None,
        is_admin_override: bool = False,
    ) -> Optional[User]:
        """Allow a logged-in user to update their nickname, avatar, and password (requires old password)."""
        user = self._users.get(user_id)
        if not user:
            return None

        if username and username.strip() and is_admin_override:
            clean_username = username.strip()
            for other_uid, other_u in self._users.items():
                if other_uid != user_id and other_u.username.lower() == clean_username.lower():
                    raise ValueError(f"用户名 '{clean_username}' 已被占用")
            user.username = clean_username

        if nickname and nickname.strip():
            user.nickname = nickname.strip()

        if avatar and avatar.strip():
            user.avatar = avatar.strip()

        if new_password and len(new_password.strip()) >= 3:
            clean_pwd = new_password.strip()
            if not is_admin_override:
                if not old_password or not user.verify_password(old_password):
                    raise ValueError("原密码错误")
            user.set_password(clean_pwd)

        self.save_to_storage()
        return user

    def admin_create_user(
        self,
        admin_user_id: str,
        username: str,
        nickname: str,
        password: str = "123",
        avatar: str = "👤",
        is_admin: bool = False,
        is_test: bool = False,
    ) -> User:
        """Admin creates a new user account with password."""
        admin = self._users.get(admin_user_id)
        if not admin or not admin.is_admin:
            raise PermissionError("仅管理员可创建用户账号")

        clean_username = username.strip()
        for u in self._users.values():
            if u.username.lower() == clean_username.lower():
                raise ValueError(f"用户名 '{clean_username}' 已存在")

        user_id = f"u_{uuid.uuid4().hex[:6]}"
        user = User(
            user_id=user_id,
            username=clean_username,
            nickname=nickname.strip() or clean_username,
            avatar=avatar,
            is_admin=is_admin,
            is_test=is_test or clean_username.lower().startswith("test"),
            password_hash=hash_password(password or "123"),
            created_at=time.time(),
        )
        self._users[user_id] = user
        self.save_to_storage()
        return user

    def admin_update_user(
        self,
        admin_user_id: str,
        target_user_id: str,
        username: Optional[str] = None,
        nickname: Optional[str] = None,
        password: Optional[str] = None,
        avatar: Optional[str] = None,
        is_admin: Optional[bool] = None,
        is_test: Optional[bool] = None,
    ) -> User:
        """Admin updates any user's credentials, role, nickname, or resets password."""
        admin = self._users.get(admin_user_id)
        if not admin or not admin.is_admin:
            raise PermissionError("仅管理员可管理用户账号")

        target = self._users.get(target_user_id)
        if not target:
            raise ValueError("用户不存在")

        if username and username.strip():
            clean_username = username.strip()
            for other_uid, other_u in self._users.items():
                if other_uid != target_user_id and other_u.username.lower() == clean_username.lower():
                    raise ValueError(f"用户名 '{clean_username}' 已被占用")
            target.username = clean_username

        if nickname and nickname.strip():
            target.nickname = nickname.strip()

        if avatar and avatar.strip():
            target.avatar = avatar.strip()

        if password and len(password.strip()) >= 3:
            target.set_password(password.strip())

        if is_admin is not None:
            target.is_admin = is_admin

        if is_test is not None:
            target.is_test = is_test

        self.save_to_storage()
        return target

    def is_test_user(self, user_id_or_username: str) -> bool:
        """Check if a given user_id or username belongs to a test account or bot."""
        if not user_id_or_username:
            return False
        if user_id_or_username.startswith("bot_"):
            return True
        user = self._users.get(user_id_or_username)
        if user:
            return user.is_test_account
        for u in self._users.values():
            if u.username.lower() == user_id_or_username.lower():
                return u.is_test_account
        return user_id_or_username.lower().startswith("test")

    def admin_delete_user(self, admin_user_id: str, target_user_id: str) -> bool:
        """Admin deletes a user account (cannot delete self)."""
        admin = self._users.get(admin_user_id)
        if not admin or not admin.is_admin:
            raise PermissionError("仅管理员可删除用户账号")

        if admin_user_id == target_user_id:
            raise ValueError("不能删除管理员自身账号")

        if target_user_id in self._users:
            del self._users[target_user_id]
            # Invalidate tokens
            self._tokens = {t: uid for t, uid in self._tokens.items() if uid != target_user_id}
            self.save_to_storage()
            return True
        return False


# Global singleton
user_manager = UserManager()
