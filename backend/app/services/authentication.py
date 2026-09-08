"""Authentication helpers shared by REST and WebSocket transports.

The transport may carry a user id for routing or backwards compatibility, but
the id is never an authentication credential.  A registered user's identity
always comes from the token resolved by :mod:`user_manager`.
"""

from __future__ import annotations

import secrets
from typing import Optional, Tuple

from backend.app.models.user import User
from backend.app.services.user_manager import user_manager


class AuthenticationError(ValueError):
    """Raised when a transport cannot establish one unambiguous principal."""


def extract_token(
    authorization: Optional[str] = None,
    token: Optional[str] = None,
) -> Optional[str]:
    """Extract one token and reject conflicting REST/header credentials."""

    header_token: Optional[str] = None
    if authorization:
        scheme, separator, value = authorization.partition(" ")
        if not separator or scheme.lower() != "bearer" or not value.strip():
            raise AuthenticationError("认证凭据格式无效")
        header_token = value.strip()

    query_token = token.strip() if isinstance(token, str) and token.strip() else None
    if header_token and query_token and header_token != query_token:
        raise AuthenticationError("认证凭据不一致")
    return header_token or query_token


def authenticate_rest(
    authorization: Optional[str] = None,
    token: Optional[str] = None,
) -> User:
    """Resolve the REST principal exclusively from a bearer/query token."""

    auth_token = extract_token(authorization=authorization, token=token)
    user = user_manager.get_user_by_token(auth_token) if auth_token else None
    if user is None:
        raise AuthenticationError("未提供有效认证 Token")
    return user


def optional_rest_user(
    authorization: Optional[str] = None,
    token: Optional[str] = None,
) -> Optional[User]:
    """Return an anonymous REST principal only when no credential was sent."""

    auth_token = extract_token(authorization=authorization, token=token)
    if not auth_token:
        return None
    user = user_manager.get_user_by_token(auth_token)
    if user is None:
        raise AuthenticationError("无效或已过期的 Token")
    return user


def authenticate_websocket(
    claimed_user_id: str,
    token: Optional[str] = None,
    authorization: Optional[str] = None,
) -> Tuple[Optional[User], str]:
    """Resolve a WebSocket connection to a user or an isolated spectator.

    A valid token is mandatory for registered users and must match the path
    claim.  A connection without a token may observe as a generated spectator,
    but its caller supplied path id is never used as the runtime identity.
    """

    auth_token = extract_token(authorization=authorization, token=token)
    if auth_token:
        user = user_manager.get_user_by_token(auth_token)
        if user is None or user.user_id != claimed_user_id:
            raise AuthenticationError("认证失败：Token 与身份不匹配")
        return user, user.user_id

    if user_manager.get_user(claimed_user_id) is not None:
        raise AuthenticationError("认证失败：注册用户必须提供有效 Token")

    spectator_id = f"spectator_{secrets.token_urlsafe(12)}"
    return None, spectator_id
