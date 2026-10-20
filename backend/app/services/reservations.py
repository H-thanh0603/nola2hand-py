"""Tự huỷ đơn hết hạn giữ món — port src/services/reservations.js.

Bản Node chạy hàm này mỗi lần tạo đơn và mỗi 60 giây bằng setInterval.
"""
from datetime import timedelta

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from ..models import ActionQuota, Listing, Order
from ..utils import notify, now, push_timeline


def expire_reservations(db: Session) -> int:
    moment = now()
    orders = db.execute(
        select(Order)
        .where(Order.status == "PENDING_DEPOSIT", Order.reservationExpiresAt <= moment)
        .order_by(Order.reservationExpiresAt.asc())
        .limit(100)
    ).scalars().all()

    db.execute(delete(ActionQuota).where(ActionQuota.windowStart < moment - timedelta(days=2)))
    db.commit()

    expired = 0
    for order in orders:
        moved = db.execute(
            update(Order)
            .where(
                Order.id == order.id,
                Order.status == "PENDING_DEPOSIT",
                Order.reservationExpiresAt <= moment,
            )
            .values(
                status="CANCELLED",
                cancelReason="Hết thời hạn đặt cọc",
                updatedAt=now(),
            )
        )
        if moved.rowcount == 0:
            db.rollback()
            continue

        db.execute(
            update(Listing)
            .where(Listing.id == order.listingId, Listing.status == "RESERVED")
            .values(status="ACTIVE", updatedAt=now())
        )
        push_timeline(db, order.id, "CANCELLED", "Tự hủy sau khi hết 30 phút chờ đặt cọc")
        notify(db, order.buyerId, "ORDER", "Đơn hết thời hạn giữ món", order.code, {"orderId": order.id})
        db.commit()
        expired += 1
    return expired
