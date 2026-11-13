"""Báo cáo vi phạm — port src/routes/reports.js."""
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, field_validator
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import CurrentUser, require_role
from ..errors import ApiError
from ..models import AuditLog, Listing, Report, Role, User, UserRole
from ..pagination import paged_result, paginate
from ..quota import account_limit
from ..serialize import to_dict
from ..services.admin_permissions import protect_admin_target
from ..utils import notify, now

router = APIRouter()

REPORT_STATUSES = ("NEW", "REVIEWING", "RESOLVED", "DISMISSED")


class ReportIn(BaseModel):
    targetType: Literal["COMMENT", "LISTING_DESC", "MESSAGE", "AVATAR", "LISTING", "SHOP", "USER"]
    targetId: int
    targetUserId: int | None = None
    reason: str
    description: str | None = None

    @field_validator("reason")
    @classmethod
    def _reason(cls, value: str) -> str:
        value = value.strip()
        if not 1 <= len(value) <= 200:
            raise ValueError("String must contain at least 1 character(s)" if not value else "String must contain at most 200 character(s)")
        return value

    @field_validator("description")
    @classmethod
    def _description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if len(value) > 1000:
            raise ValueError("String must contain at most 1000 character(s)")
        return value


class ReportActionIn(BaseModel):
    status: Literal["REVIEWING", "RESOLVED", "DISMISSED"]
    resolution: str | None = None
    action: Literal["NONE", "WARN_USER", "BAN_7_DAYS", "BAN_PERMANENT", "REMOVE_CONTENT"] = "NONE"

    @field_validator("resolution")
    @classmethod
    def _resolution(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if len(value) > 1000:
            raise ValueError("String must contain at most 1000 character(s)")
        return value


def _month_start_utc() -> datetime:
    local = datetime.now().astimezone()
    start = local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return start.astimezone(timezone.utc).replace(tzinfo=None)


@router.post("", status_code=201)
def create_report(
    payload: ReportIn,
    user: CurrentUser = Depends(account_limit("CREATE_REPORT", 10, 86_400_000)),
    db: Session = Depends(get_db),
):
    # 1. Validate SHOP/USER reports
    if payload.targetType in ("SHOP", "USER"):
        if payload.targetUserId != payload.targetId:
            raise ApiError(400, "targetUserId phải trùng targetId với báo cáo shop/người dùng")
        if payload.targetId == user.id:
            raise ApiError(400, "Không thể tự báo cáo chính mình")
        
        target = db.execute(select(User.id, User.status).where(User.id == payload.targetId)).first()
        if target is None:
            raise ApiError(404, "Không tìm thấy người dùng bị báo cáo")
        if target.status != "ACTIVE":
            raise ApiError(400, "Không thể báo cáo tài khoản đang bị khóa")

        # 2. Deduplication (chống gửi trùng trong 24h)
        since = now() - timedelta(hours=24)
        duplicate = db.execute(
            select(Report.id).where(
                Report.reporterId == user.id,
                Report.targetType == payload.targetType,
                Report.targetId == payload.targetId,
                Report.createdAt >= since,
            )
        ).first()
        if duplicate is not None:
            raise ApiError(409, "Bạn đã báo cáo mục này trong 24 giờ qua")

    # Create the report
    report = Report(**payload.model_dump(), reporterId=user.id, updatedAt=now())
    db.add(report)
    db.flush()

    # 3. Notify Admins (ADMIN_CONTENT)
    admin_ids = db.execute(
        select(User.id)
        .join(UserRole, UserRole.userId == User.id)
        .join(Role, Role.id == UserRole.roleId)
        .where(Role.name == "ADMIN_CONTENT", User.status == "ACTIVE")
    ).scalars().all()
    
    label = {
        "SHOP": "shop", "USER": "người dùng", "LISTING": "tin đăng",
        "COMMENT": "bình luận", "LISTING_DESC": "mô tả tin", 
        "MESSAGE": "tin nhắn", "AVATAR": "ảnh đại diện",
    }.get(payload.targetType, "nội dung")

    for admin_id in admin_ids:
        notify(
            db,
            admin_id,
            "REPORT",
            "Báo cáo vi phạm mới",
            f"{label.capitalize()} #{payload.targetId} bị báo cáo: {payload.reason}",
            {"reportId": report.id, "targetType": payload.targetType, "targetId": payload.targetId},
        )

    db.commit()
    return {"message": "Đã gửi báo cáo, cảm ơn bạn", "report": to_dict(report)}

@router.get("/admin/all")
def all_reports(
    request: Request,
    _admin: CurrentUser = Depends(require_role("ADMIN_CONTENT")),
    db: Session = Depends(get_db),
):
    page = paginate(dict(request.query_params))
    conditions = []
    status = request.query_params.get("status")
    if status:
        if status not in REPORT_STATUSES:
            raise ApiError(400, "Trạng thái báo cáo không hợp lệ (NEW/REVIEWING/RESOLVED/DISMISSED)")
        conditions.append(Report.status == status)
    target_type = request.query_params.get("targetType")
    if target_type:
        conditions.append(Report.targetType == target_type)
    query_text = request.query_params.get("q")
    if query_text:
        like = f"%{query_text}%"
        conditions.append(or_(Report.reason.ilike(like), Report.description.ilike(like)))

    rows = db.execute(
        select(Report)
        .where(*conditions)
        .order_by(Report.createdAt.desc())
        .offset(page["skip"])
        .limit(page["limit"])
    ).scalars().all()
    total = db.execute(
        select(func.count()).select_from(Report).where(*conditions)
    ).scalar_one()

    reports = list(rows)
    user_ids = {
        user_id
        for report in reports
        for user_id in (report.reporterId, report.handlerId)
        if user_id is not None
    }
    names = {
        user_id: full_name
        for user_id, full_name in db.execute(
            select(User.id, User.fullName).where(User.id.in_(user_ids))
        ).all()
    }

    items = []
    for report in reports:
        item = to_dict(report)
        item["reporter"] = (
            {"id": report.reporterId, "fullName": names.get(report.reporterId)}
            if report.reporterId
            else None
        )
        item["handler"] = (
            {"id": report.handlerId, "fullName": names.get(report.handlerId)}
            if report.handlerId
            else None
        )
        items.append(item)
    return paged_result(items, total, page["page"], page["limit"])


@router.get("/admin/stats")
def report_stats(
    _admin: CurrentUser = Depends(require_role("ADMIN_CONTENT")),
    db: Session = Depends(get_db),
):
    month_start = _month_start_utc()

    def count(*conditions) -> int:
        return db.execute(select(func.count()).select_from(Report).where(*conditions)).scalar_one()

    return {
        "new": count(Report.status == "NEW"),
        "reviewing": count(Report.status == "REVIEWING"),
        "resolvedThisMonth": count(Report.status == "RESOLVED", Report.updatedAt >= month_start),
        "dismissedThisMonth": count(Report.status == "DISMISSED", Report.updatedAt >= month_start),
    }


@router.patch("/admin/{report_id}")
def handle_report(
    report_id: int,
    payload: ReportActionIn,
    admin: CurrentUser = Depends(require_role("ADMIN_CONTENT")),
    db: Session = Depends(get_db),
):
    report = db.execute(select(Report).where(Report.id == report_id)).scalar_one_or_none()
    if report is None:
        raise ApiError(404, "Không tìm thấy báo cáo")

    status = payload.status
    action = payload.action
    db.execute(
        update(Report)
        .where(Report.id == report.id)
        .values(
            status=status,
            resolution=payload.resolution,
            handlerId=admin.id,
            updatedAt=now(),
        )
    )

    if report.targetUserId and action != "NONE" and status == "RESOLVED":
        if action == "WARN_USER":
            notify(
                db,
                report.targetUserId,
                "REPORT",
                "Cảnh cáo vi phạm",
                f"Nội dung của bạn bị báo cáo: {report.reason}. Vui lòng tuân thủ quy định cộng đồng.",
            )
        elif action in ("BAN_7_DAYS", "BAN_PERMANENT"):
            protect_admin_target(db, admin, report.targetUserId)
            db.execute(
                update(User)
                .where(User.id == report.targetUserId)
                .values(
                    status="BANNED",
                    banReason=f"{report.reason} ({'khóa 7 ngày' if action == 'BAN_7_DAYS' else 'khóa vĩnh viễn'})",
                    bannedAt=now(),
                    sessionVersion=User.sessionVersion + 1,
                    updatedAt=now(),
                )
            )
            db.add(
                AuditLog(
                    adminId=admin.id,
                    action=action,
                    target=f"user:{report.targetUserId}",
                    detail={"reportId": report.id, "reason": report.reason},
                )
            )
        elif action == "REMOVE_CONTENT" and report.targetType in ("SHOP", "USER"):
            db.add(
                AuditLog(
                    adminId=admin.id,
                    action="REMOVE_CONTENT_NOOP",
                    target=f"{report.targetType.lower()}:{report.targetId}",
                    detail={"reportId": report.id, "note": "No content to hide for SHOP/USER"},
                )
            )
    notify(
        db,
        report.reporterId,
        "REPORT",
        "Báo cáo của bạn đã được xử lý",
        f"Báo cáo #{report.id} ({report.reason}): {status}",
        {"reportId": report.id},
    )
    db.commit()
    db.refresh(report)
    return to_dict(report)
