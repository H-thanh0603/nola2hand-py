"""Nhật ký quản trị — port src/routes/audit.js."""
from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import CurrentUser, require_role
from ..models import AuditLog, User
from ..pagination import paged_result, paginate
from ..serialize import to_dict
from ..services.revenue import date_range

router = APIRouter()


@router.get("")
def audit_log(
    request: Request,
    _admin: CurrentUser = Depends(require_role("ADMIN_CONTENT", "ADMIN_FINANCE")),
    db: Session = Depends(get_db),
):
    page = paginate(dict(request.query_params))
    conditions = []
    query_text = request.query_params.get("q")
    if query_text:
        like = f"%{query_text}%"
        conditions.append(or_(AuditLog.action.ilike(like), AuditLog.target.ilike(like)))
    if request.query_params.get("from") or request.query_params.get("to"):
        start, end = date_range(dict(request.query_params))
        conditions.extend([AuditLog.createdAt >= start, AuditLog.createdAt <= end])

    rows = db.execute(
        select(AuditLog)
        .where(*conditions)
        .order_by(AuditLog.createdAt.desc())
        .offset(page["skip"])
        .limit(page["limit"])
    ).scalars().all()
    total = db.execute(
        select(func.count()).select_from(AuditLog).where(*conditions)
    ).scalar_one()

    admin_ids = {row.adminId for row in rows}
    names = {
        user_id: full_name
        for user_id, full_name in db.execute(
            select(User.id, User.fullName).where(User.id.in_(admin_ids))
        ).all()
    }
    items = []
    for row in rows:
        item = to_dict(row)
        item["admin"] = {"fullName": names.get(row.adminId)}
        items.append(item)
    return paged_result(items, total, page["page"], page["limit"])
