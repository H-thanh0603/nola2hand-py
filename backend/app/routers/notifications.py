"""Trung tâm thông báo — port src/routes/notifications.js."""
from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import CurrentUser, current_user
from ..errors import ApiError
from ..models import Notification
from ..pagination import paged_result, paginate
from ..serialize import to_dict

router = APIRouter()


@router.get("")
def list_notifications(
    request: Request,
    user: CurrentUser = Depends(current_user),
    db: Session = Depends(get_db),
):
    page = paginate(dict(request.query_params))
    conditions = [Notification.userId == user.id]
    if request.query_params.get("unread") == "true":
        conditions.append(Notification.isRead.is_(False))

    items = db.execute(
        select(Notification)
        .where(*conditions)
        .order_by(Notification.createdAt.desc())
        .offset(page["skip"])
        .limit(page["limit"])
    ).scalars().all()
    total = db.execute(
        select(func.count()).select_from(Notification).where(*conditions)
    ).scalar_one()
    unread_count = db.execute(
        select(func.count())
        .select_from(Notification)
        .where(Notification.userId == user.id, Notification.isRead.is_(False))
    ).scalar_one()

    return {
        **paged_result([to_dict(item) for item in items], total, page["page"], page["limit"]),
        "unreadCount": unread_count,
    }


@router.patch("/read-all")
def read_all(user: CurrentUser = Depends(current_user), db: Session = Depends(get_db)):
    db.execute(
        update(Notification)
        .where(Notification.userId == user.id, Notification.isRead.is_(False))
        .values(isRead=True)
    )
    db.commit()
    return {"message": "Đã đánh dấu đọc tất cả"}


@router.patch("/{notification_id}/read")
def read_one(
    notification_id: int,
    user: CurrentUser = Depends(current_user),
    db: Session = Depends(get_db),
):
    notification = db.execute(
        select(Notification).where(
            Notification.id == notification_id, Notification.userId == user.id
        )
    ).scalar_one_or_none()
    if notification is None:
        raise ApiError(404, "Không tìm thấy thông báo")

    notification.isRead = True
    db.commit()
    return to_dict(notification)
