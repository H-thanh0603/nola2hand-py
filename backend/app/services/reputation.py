"""Uy tín gian hàng — port src/services/reputation.js."""
from datetime import timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..models import Message, Order, ReturnRequest, Review, User
from ..utils import js_round, now


def response_stats(messages: list[dict]) -> dict:
    """Tỉ lệ phản hồi và trung vị thời gian trả lời (giây) trong 90 ngày."""
    waiting: dict[str, int] = {}
    durations: list[float] = []
    turns = 0
    responses = 0

    for message in messages:
        key = f"{message['otherId']}:{message['listingId'] or 0}"
        if message["incoming"]:
            if key not in waiting:
                waiting[key] = int(message["createdAt"].timestamp() * 1000)
                turns += 1
        elif key in waiting:
            durations.append(max(0, int(message["createdAt"].timestamp() * 1000) - waiting[key]) / 1000)
            responses += 1
            del waiting[key]

    durations.sort()
    if durations:
        median = (durations[(len(durations) - 1) // 2] + durations[len(durations) // 2]) / 2
    else:
        median = None
    return {
        "inquiries": turns,
        "responses": responses,
        "responseRate": js_round(responses / turns * 100) if turns else None,
        "medianResponseSeconds": median,
    }


def shop_reputation(db: Session, user: User) -> dict:
    order_rows = db.execute(
        select(Order.status, func.count()).where(Order.sellerId == user.id).group_by(Order.status)
    ).all()
    counts = {status: total for status, total in order_rows}

    since = now() - timedelta(days=90)
    message_rows = db.execute(
        select(Message)
        .where(
            or_(Message.senderId == user.id, Message.receiverId == user.id),
            Message.createdAt >= since,
        )
        .order_by(Message.createdAt.desc())
        .limit(10000)
    ).scalars().all()

    rating, review_count = db.execute(
        select(func.avg(Review.rating), func.count()).where(Review.revieweeId == user.id)
    ).one()
    returned = db.execute(
        select(func.count())
        .select_from(ReturnRequest)
        .join(Order, Order.id == ReturnRequest.orderId)
        .where(Order.sellerId == user.id, ReturnRequest.status == "REFUNDED")
    ).scalar_one()

    total_orders = sum(counts.values())
    cancelled = counts.get("CANCELLED", 0)
    replies = response_stats(
        [
            {
                "incoming": message.receiverId == user.id,
                "otherId": message.receiverId if message.senderId == user.id else message.senderId,
                "listingId": message.listingId,
                "createdAt": message.createdAt,
            }
            for message in reversed(message_rows)  # Node đảo lại thành cũ → mới
        ]
    )

    return {
        "totalOrders": total_orders,
        "completedOrders": counts.get("COMPLETED", 0),
        "cancelledOrders": cancelled,
        "refundedOrders": counts.get("REFUNDED", 0),
        "returnedOrders": returned,
        "cancellationRate": js_round(cancelled / total_orders * 1000) / 10 if total_orders else None,
        "rating": float(rating or 0),
        "totalReviews": review_count,
        **replies,
        "emailVerified": bool(user.emailVerifiedAt),
        "identityVerified": user.idVerified is True,
        "responseWindowDays": 90,
        "messageSample": len(message_rows),
    }
