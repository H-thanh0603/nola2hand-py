"""Báo cáo doanh thu theo ngày — port src/services/revenue.js."""
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..errors import ApiError
from ..models import Order, Wallet, WalletTransaction


def _parse_day(value: str) -> datetime:
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", value):
        raise ApiError(400, "Ngày phải có định dạng YYYY-MM-DD")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise ApiError(400, "Ngày không hợp lệ") from exc
    return parsed


def date_range(query: dict, moment: datetime | None = None) -> tuple[datetime, datetime]:
    today = (moment or datetime.now(timezone.utc)).astimezone(timezone.utc)
    start_value = query.get("from") or (today - timedelta(days=30)).strftime("%Y-%m-%d")
    end_value = query.get("to") or today.strftime("%Y-%m-%d")

    start = _parse_day(start_value)
    end = _parse_day(end_value)
    if end < start or end - start > timedelta(days=365):
        raise ApiError(400, "Khoảng ngày tối đa 366 ngày và ngày đến phải sau ngày từ")

    end = end.replace(hour=23, minute=59, second=59, microsecond=999000)
    return start, end


def daily_revenue(db: Session, query: dict, seller_id: int | None = None) -> dict:
    start, end = date_range(query)

    if seller_id:
        conditions = [
            WalletTransaction.createdAt >= start,
            WalletTransaction.createdAt <= end,
            WalletTransaction.status == "SUCCESS",
            WalletTransaction.type.in_(("ORDER_INCOME", "PLATFORM_FEE")),
            WalletTransaction.walletId.in_(select(Wallet.id).where(Wallet.userId == seller_id)),
        ]
    else:
        conditions = [
            WalletTransaction.createdAt >= start,
            WalletTransaction.createdAt <= end,
            WalletTransaction.status == "SUCCESS",
            WalletTransaction.type == "PLATFORM_FEE",
            WalletTransaction.amount < 0,
        ]

    days: dict[str, dict[str, int]] = {}
    for created_at, amount in db.execute(
        select(WalletTransaction.createdAt, WalletTransaction.amount).where(*conditions)
    ).all():
        key = created_at.strftime("%Y-%m-%d")
        bucket = days.setdefault(key, {"revenue": 0, "orders": 0})
        bucket["revenue"] += amount if seller_id else -amount

    order_conditions = [Order.createdAt >= start, Order.createdAt <= end]
    if seller_id:
        order_conditions.append(Order.sellerId == seller_id)
    for created_at in db.execute(select(Order.createdAt).where(*order_conditions)).scalars():
        key = created_at.strftime("%Y-%m-%d")
        days.setdefault(key, {"revenue": 0, "orders": 0})["orders"] += 1

    data = []
    day = start
    while day <= end:
        key = day.strftime("%Y-%m-%d")
        bucket = days.get(key, {"revenue": 0, "orders": 0})
        data.append({"date": key, "revenue": bucket["revenue"], "orders": bucket["orders"]})
        day += timedelta(days=1)

    return {
        "from": start.strftime("%Y-%m-%d"),
        "to": end.strftime("%Y-%m-%d"),
        "basis": "NET_WALLET_INCOME" if seller_id else "COLLECTED_PLATFORM_FEES",
        "timezone": "UTC",
        "data": data,
    }
