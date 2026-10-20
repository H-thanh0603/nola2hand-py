"""Admin quản lý tài khoản — port src/routes/admin-users.js."""
from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import CurrentUser, current_user, require_role
from ..errors import ApiError
from ..models import AuditLog, Listing, Notification, Order, Role, SellerProfile, User, UserRole
from ..pagination import paged_result, paginate
from ..services.admin_permissions import protect_admin_target, roles_of
from ..utils import now

router = APIRouter(dependencies=[Depends(require_role("ADMIN_FINANCE", "ADMIN_CONTENT"))])


class ReasonIn(BaseModel):
    reason: str

    @field_validator("reason")
    @classmethod
    def _reason(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("String must contain at least 1 character(s)")
        if len(v) > 500:
            raise ValueError("String must contain at most 500 character(s)")
        return v


class RolesIn(BaseModel):
    roles: list[Literal["BUYER", "SELLER", "ADMIN_FINANCE", "ADMIN_CONTENT"]] = Field(min_length=1)


def _notify(db: Session, user_id: int, title: str, body: str | None) -> None:
    db.add(Notification(userId=user_id, type="SYSTEM", title=title, body=body, data={}))


def _audit(db: Session, admin_id: int, action: str, target: int, detail: dict | None = None) -> None:
    db.add(AuditLog(adminId=admin_id, action=action, target=f"user:{target}", detail=detail))


@router.get("")
def list_users(request: Request, db: Session = Depends(get_db)):
    query = dict(request.query_params)
    page = paginate(query)

    conditions = []
    if query.get("status"):
        conditions.append(User.status == query["status"])
    if query.get("q"):
        like = f"%{query['q']}%"
        conditions.append(
            User.fullName.ilike(like) | User.email.ilike(like) | User.phone.like(like)
        )
    if query.get("role"):
        conditions.append(
            User.id.in_(
                select(UserRole.userId)
                .join(Role, Role.id == UserRole.roleId)
                .where(Role.name == query["role"])
            )
        )

    listing_count = (
        select(func.count()).select_from(Listing).where(Listing.sellerId == User.id).scalar_subquery()
    )
    order_count = (
        select(func.count()).select_from(Order).where(Order.buyerId == User.id).scalar_subquery()
    )

    rows = db.execute(
        select(User, listing_count, order_count)
        .where(*conditions)
        .order_by(User.createdAt.desc())
        .offset(page["skip"])
        .limit(page["limit"])
    ).all()
    total = db.execute(select(func.count()).select_from(User).where(*conditions)).scalar_one()

    ids = [row[0].id for row in rows]
    roles_by_user: dict[int, list[str]] = {user_id: [] for user_id in ids}
    if ids:
        for user_id, name in db.execute(
            select(UserRole.userId, Role.name)
            .join(Role, Role.id == UserRole.roleId)
            .where(UserRole.userId.in_(ids))
        ):
            roles_by_user[user_id].append(name)

    data = [
        {
            "id": user.id,
            "fullName": user.fullName,
            "email": user.email,
            "phone": user.phone,
            "avatarUrl": user.avatarUrl,
            "status": user.status,
            "isVerified": user.isVerified,
            "idVerified": user.idVerified,
            "banReason": user.banReason,
            "createdAt": user.createdAt,
            "roles": roles_by_user[user.id],
            "_count": {"listings": listings, "ordersBuyer": orders},
        }
        for user, listings, orders in rows
    ]
    return paged_result(data, total, page["page"], page["limit"])


@router.get("/stats")
def user_stats(db: Session = Depends(get_db)):
    def count(status: str | None = None) -> int:
        stmt = select(func.count()).select_from(User)
        if status:
            stmt = stmt.where(User.status == status)
        return db.execute(stmt).scalar_one()

    return {
        "total": count(),
        "active": count("ACTIVE"),
        "pendingVerification": count("PENDING_VERIFICATION"),
        "banned": count("BANNED"),
    }


@router.patch("/{user_id}/lock")
def lock_user(
    user_id: int,
    payload: ReasonIn,
    user: CurrentUser = Depends(current_user),
    db: Session = Depends(get_db),
):
    if user_id == user.id:
        raise ApiError(400, "Không thể tự khóa chính mình")

    target = protect_admin_target(db, user, user_id)
    target.status = "BANNED"
    target.banReason = payload.reason
    target.bannedAt = now()
    target.sessionVersion = (target.sessionVersion or 0) + 1
    target.updatedAt = now()

    _audit(db, user.id, "LOCK_USER", user_id, {"reason": payload.reason})
    _notify(db, user_id, "Tài khoản của bạn đã bị khóa", f"Lý do: {payload.reason}")
    db.commit()
    return {"message": "Đã khóa tài khoản"}


@router.patch("/{user_id}/unlock")
def unlock_user(
    user_id: int,
    payload: ReasonIn,
    user: CurrentUser = Depends(current_user),
    db: Session = Depends(get_db),
):
    target = protect_admin_target(db, user, user_id)
    target.status = "ACTIVE"
    target.banReason = None
    target.bannedAt = None
    target.updatedAt = now()

    _audit(db, user.id, "UNLOCK_USER", user_id, {"reason": payload.reason})
    _notify(db, user_id, "Tài khoản đã được mở khóa", payload.reason)
    db.commit()
    return {"message": "Đã mở khóa tài khoản"}


@router.patch("/{user_id}/verify")
def verify_user(
    user_id: int,
    user: CurrentUser = Depends(current_user),
    db: Session = Depends(get_db),
):
    target = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    if target is None:
        raise ApiError(404, "Không tìm thấy dữ liệu")

    target.idVerified = True
    target.updatedAt = now()
    _audit(db, user.id, "VERIFY_USER", user_id)
    _notify(db, user_id, "Xác minh danh tính thành công", "Tài khoản của bạn đã được gắn huy hiệu đã xác thực ✓")
    db.commit()
    return {"message": "Đã duyệt xác minh"}


@router.patch("/{user_id}/roles")
def set_roles(
    user_id: int,
    payload: RolesIn,
    user: CurrentUser = Depends(current_user),
    db: Session = Depends(get_db),
):
    if not user.canManageRoles or "ADMIN_FINANCE" not in user.roles:
        raise ApiError(403, "Cần quyền quản lý phân quyền riêng")
    if user_id <= 0:
        raise ApiError(400, "Người dùng không hợp lệ")
    if user_id == user.id:
        raise ApiError(403, "Không được thay đổi vai trò của chính mình")

    db.execute(text("SELECT pg_advisory_xact_lock(1502026)"))

    # Đọc lại người thực hiện trong transaction: quyền có thể vừa bị thu hồi.
    executor = db.execute(select(User).where(User.id == user.id)).scalar_one_or_none()
    if (
        executor is None
        or executor.status != "ACTIVE"
        or not executor.canManageRoles
        or "ADMIN_FINANCE" not in roles_of(db, user.id)
    ):
        raise ApiError(403, "Quyền quản lý phân quyền đã bị thu hồi")

    target = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    if target is None:
        raise ApiError(404, "Không tìm thấy tài khoản")

    old_roles = set(roles_of(db, user_id))
    if "ADMIN_FINANCE" in old_roles and "ADMIN_FINANCE" not in payload.roles:
        remaining = db.execute(
            select(func.count())
            .select_from(User)
            .join(UserRole, UserRole.userId == User.id)
            .join(Role, Role.id == UserRole.roleId)
            .where(
                User.id != user_id,
                User.status == "ACTIVE",
                Role.name == "ADMIN_FINANCE",
            )
        ).scalar_one()
        if not remaining:
            raise ApiError(409, "Phải giữ ít nhất một admin tài chính hoạt động")
        if target.canManageRoles:
            managers = db.execute(
                select(func.count())
                .select_from(User)
                .join(UserRole, UserRole.userId == User.id)
                .join(Role, Role.id == UserRole.roleId)
                .where(
                    User.id != user_id,
                    User.status == "ACTIVE",
                    User.canManageRoles.is_(True),
                    Role.name == "ADMIN_FINANCE",
                )
            ).scalar_one()
            if not managers:
                raise ApiError(409, "Phải giữ ít nhất một người quản lý phân quyền")

    roles = db.execute(select(Role).where(Role.name.in_(payload.roles))).scalars().all()
    db.execute(UserRole.__table__.delete().where(UserRole.userId == user_id))
    db.add_all([UserRole(userId=user_id, roleId=role.id) for role in roles])

    if "SELLER" in payload.roles:
        profile = db.execute(
            select(SellerProfile).where(SellerProfile.userId == user_id)
        ).scalar_one_or_none()
        if profile is None:
            db.add(SellerProfile(userId=user_id, shopName=f"Shop {target.fullName}"))

    target.sessionVersion = (target.sessionVersion or 0) + 1
    if "ADMIN_FINANCE" not in payload.roles:
        target.canManageRoles = False
    target.updatedAt = now()

    _audit(db, user.id, "SET_ROLES", user_id, {"roles": payload.roles})
    db.commit()
    return {"message": "Đã cập nhật phân quyền", "roles": payload.roles}
