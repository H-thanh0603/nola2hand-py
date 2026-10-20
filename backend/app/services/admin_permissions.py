"""Quyền quản trị — port src/services/admin-permissions.js."""
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from ..deps import CurrentUser
from ..errors import ApiError
from ..models import Role, User, UserRole

# Khóa tư vấn dùng chung với bản Node: hai backend không sửa phân quyền cùng lúc.
ADVISORY_LOCK_KEY = 1502026


def roles_of(db: Session, user_id: int) -> list[str]:
    return list(
        db.execute(
            select(Role.name).join(UserRole, UserRole.roleId == Role.id).where(UserRole.userId == user_id)
        ).scalars()
    )


def assert_role_manager(actor: CurrentUser, target_id: int) -> None:
    if not actor.canManageRoles or "ADMIN_FINANCE" not in actor.roles:
        raise ApiError(403, "Cần quyền quản lý phân quyền riêng")
    if actor.id == target_id:
        raise ApiError(403, "Không được thay đổi quyền của chính mình")


def _active_finance_managers(db: Session, exclude_user_id: int) -> int:
    return db.execute(
        select(func.count())
        .select_from(User)
        .join(UserRole, UserRole.userId == User.id)
        .join(Role, Role.id == UserRole.roleId)
        .where(
            User.id != exclude_user_id,
            User.status == "ACTIVE",
            User.canManageRoles.is_(True),
            Role.name == "ADMIN_FINANCE",
        )
    ).scalar_one()


def protect_admin_target(db: Session, actor: CurrentUser, target_id: int) -> User:
    """Không cho khóa/hạ quyền admin khác hoặc người quản lý phân quyền cuối cùng."""
    db.execute(text(f"SELECT pg_advisory_xact_lock({ADVISORY_LOCK_KEY})"))

    target = db.execute(select(User).where(User.id == target_id)).scalar_one_or_none()
    if target is None:
        raise ApiError(404, "Không tìm thấy tài khoản")

    if any(name.startswith("ADMIN") for name in roles_of(db, target_id)):
        assert_role_manager(actor, target_id)

    if target.canManageRoles and _active_finance_managers(db, target_id) == 0:
        raise ApiError(409, "Không được khóa người quản lý phân quyền cuối cùng")
    return target
