"""Băm mật khẩu và JWT — phải khớp bản Node (bcryptjs cost 10, JWT HS256)."""
import re
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from .config import settings

# bcryptjs cắt âm thầm ở 72 byte; thư viện Python thì báo lỗi → tự cắt cho giống.
BCRYPT_MAX_BYTES = 72


def _password_bytes(password: str) -> bytes:
    return password.encode("utf-8")[:BCRYPT_MAX_BYTES]


def hash_password(password: str) -> str:
    # prefix b"2a" để ra đúng dạng hash bcryptjs sinh ra ($2a$10$...)
    salt = bcrypt.gensalt(rounds=10, prefix=b"2a")
    return bcrypt.hashpw(_password_bytes(password), salt).decode()


def verify_password(password: str, password_hash: str) -> bool:
    if not password_hash:
        return False
    try:
        return bcrypt.checkpw(_password_bytes(password), password_hash.encode())
    except ValueError:
        return False


_UNIT_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400}


def _expiry_seconds(value: str) -> int:
    """'7d' | '12h' | '30m' | '3600' → số giây, giống cách jsonwebtoken hiểu."""
    match = re.fullmatch(r"(\d+)([smhd]?)", value.strip())
    if not match:
        raise ValueError(f"JWT_EXPIRES_IN không hợp lệ: {value!r}")
    return int(match.group(1)) * _UNIT_SECONDS.get(match.group(2), 1)


def create_access_token(user_id: int, session_version: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "purpose": "access",
        "sessionVersion": session_version,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=_expiry_seconds(settings.jwt_expires_in))).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


class TokenError(Exception):
    """Token sai, hết hạn, hoặc không phải token đăng nhập."""


def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.InvalidTokenError as exc:
        raise TokenError("invalid") from exc
    if payload.get("purpose") != "access":
        raise TokenError("wrong_purpose")
    return payload
