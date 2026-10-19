"""Xác thực, phân quyền, tài khoản đã xác minh — port src/middleware.js + src/services/guards.js."""
from collections.abc import Callable
from dataclasses import dataclass, field

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_db
from .errors import ApiError
from .models import Role, User, UserRole
from .security import TokenError, decode_access_token


@dataclass
class CurrentUser:
    id: int
    roles: list[str] = field(default_factory=list)
    canManageRoles: bool = False
    emailVerified: bool = False
    idVerified: bool = False


def _user_and_roles(db: Session, user_id: int) -> tuple[User | None, list[str]]:
    user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    if user is None:
        return None, []
    names = db.execute(
        select(Role.name).join(UserRole, UserRole.roleId == Role.id).where(UserRole.userId == user_id)
    ).scalars().all()
    return user, list(names)


def bearer_token(request: Request) -> str | None:
    header = request.headers.get("authorization", "")
    return header[7:] if header.startswith("Bearer ") else None


def current_user(request: Request, db: Session = Depends(get_db)) -> CurrentUser:
    token = bearer_token(request)
    if not token:
        raise ApiError(401, "Thiếu token đăng nhập")
    try:
        payload = decode_access_token(token)
    except TokenError as exc:
        if exc.args[0] == "wrong_purpose":
            raise ApiError(401, "Token không dùng để đăng nhập") from exc
        raise ApiError(401, "Token không hợp lệ hoặc đã hết hạn") from exc

    user, roles = _user_and_roles(db, int(payload["sub"]))
    if user is None or user.status != "ACTIVE":
        raise ApiError(401, "Tài khoản không còn hiệu lực")
    if (payload.get("sessionVersion") or 0) != (user.sessionVersion or 0):
        raise ApiError(401, "Phiên đã bị thu hồi. Hãy đăng nhập lại.")
    return CurrentUser(
        id=user.id,
        roles=roles,
        canManageRoles=user.canManageRoles is True,
        emailVerified=bool(user.emailVerifiedAt),
        idVerified=user.idVerified is True,
    )


def require_role(*roles: str) -> Callable[[CurrentUser], CurrentUser]:
    def dependency(user: CurrentUser = Depends(current_user)) -> CurrentUser:
        if not set(user.roles) & set(roles):
            raise ApiError(403, "Bạn không có quyền thực hiện thao tác này")
        return user

    return dependency


def verified_account(user: CurrentUser = Depends(current_user)) -> CurrentUser:
    if not user.emailVerified and not user.idVerified:
        raise ApiError(403, "Hãy xác nhận email hoặc danh tính trước khi đặt hàng/đăng tin.")
    return user
