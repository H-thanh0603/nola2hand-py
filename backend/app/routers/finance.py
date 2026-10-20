"""Tài chính quản trị — port src/routes/finance.js."""
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, field_validator
from sqlalchemy import func, or_, select
from sqlalchemy.orm import aliased
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import CurrentUser, current_user, require_role
from ..errors import ApiError
from ..models import (
    AuditLog,
    Category,
    Dispute,
    FeeConfig,
    Listing,
    Order,
    User,
    Wallet,
    WalletTransaction,
    WithdrawalRequest,
)
from ..pagination import js_parse_int, paged_result, paginate
from ..serialize import to_dict
from ..services.revenue import daily_revenue, date_range
from ..services.withdrawals import transition_withdrawal
from ..utils import now

router = APIRouter(dependencies=[Depends(require_role("ADMIN_FINANCE"))])

WITHDRAWAL_STATUSES = ("PENDING", "APPROVED", "PAID", "REJECTED", "FAILED", "CANCELLED")


class FeeIn(BaseModel):
    kind: Literal["PLATFORM_TXN", "WITHDRAW", "PENALTY"]
    name: str
    percent: float | None = None
    amount: int | None = None
    minAmount: int | None = None
    condition: str | None = None
    isActive: bool | None = None

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("String must contain at least 1 character(s)")
        if len(value) > 150:
            raise ValueError("String must contain at most 150 character(s)")
        return value

    @field_validator("percent")
    @classmethod
    def _percent(cls, value: float | None) -> float | None:
        if value is not None and not 0 <= value <= 100:
            raise ValueError("Number must be less than or equal to 100")
        return value

    @field_validator("amount", "minAmount")
    @classmethod
    def _non_negative(cls, value: int | None) -> int | None:
        if value is not None and value < 0:
            raise ValueError("Number must be greater than or equal to 0")
        return value

    @field_validator("condition")
    @classmethod
    def _condition(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if len(value) > 500:
            raise ValueError("String must contain at most 500 character(s)")
        return value


class FeePatch(BaseModel):
    kind: Literal["PLATFORM_TXN", "WITHDRAW", "PENALTY"] | None = None
    name: str | None = None
    percent: float | None = None
    amount: int | None = None
    minAmount: int | None = None
    condition: str | None = None
    isActive: bool | None = None

    @field_validator("name")
    @classmethod
    def _name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not 1 <= len(value) <= 150:
            raise ValueError("String must contain at least 1 character(s)" if not value else "String must contain at most 150 character(s)")
        return value

    @field_validator("percent")
    @classmethod
    def _percent(cls, value: float | None) -> float | None:
        if value is not None and not 0 <= value <= 100:
            raise ValueError("Number must be less than or equal to 100")
        return value

    @field_validator("amount", "minAmount")
    @classmethod
    def _non_negative(cls, value: int | None) -> int | None:
        if value is not None and value < 0:
            raise ValueError("Number must be greater than or equal to 0")
        return value


class WithdrawalActionIn(BaseModel):
    action: Literal["APPROVE", "PAY", "REJECT", "FAIL"]
    resolution: str
    transferReference: str | None = None

    @field_validator("resolution")
    @classmethod
    def _resolution(cls, value: str) -> str:
        value = value.strip()
        if not 3 <= len(value) <= 1000:
            raise ValueError("String must contain at least 3 character(s)" if len(value) < 3 else "String must contain at most 1000 character(s)")
        return value

    @field_validator("transferReference")
    @classmethod
    def _reference(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not 3 <= len(value) <= 150:
            raise ValueError("String must contain at least 3 character(s)" if len(value) < 3 else "String must contain at most 150 character(s)")
        return value


def _month_start_utc() -> datetime:
    """setDate(1)/setHours(0,0,0,0) của JS tính theo giờ máy chủ; DB lưu UTC."""
    local = datetime.now().astimezone()
    start = local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return start.astimezone(timezone.utc).replace(tzinfo=None)


@router.get("/overview")
def overview(db: Session = Depends(get_db)):
    month_start = _month_start_utc()

    revenue = db.execute(
        select(func.coalesce(func.sum(WalletTransaction.amount), 0)).where(
            WalletTransaction.type == "PLATFORM_FEE",
            WalletTransaction.amount < 0,
            WalletTransaction.createdAt >= month_start,
        )
    ).scalar_one()
    total_transactions = db.execute(
        select(func.count())
        .select_from(WalletTransaction)
        .where(WalletTransaction.createdAt >= month_start)
    ).scalar_one()
    pending_refunds = db.execute(
        select(func.count()).select_from(Dispute).where(Dispute.status.in_(("OPEN", "REVIEWING")))
    ).scalar_one()
    open_disputes = db.execute(
        select(func.count()).select_from(Dispute).where(Dispute.status == "OPEN")
    ).scalar_one()

    recent_transactions = []
    for txn, wallet, full_name in db.execute(
        select(WalletTransaction, Wallet, User.fullName)
        .join(Wallet, Wallet.id == WalletTransaction.walletId)
        .join(User, User.id == Wallet.userId)
        .order_by(WalletTransaction.createdAt.desc())
        .limit(5)
    ).all():
        item = to_dict(txn)
        item["wallet"] = {**to_dict(wallet), "user": {"fullName": full_name}}
        recent_transactions.append(item)

    buyer = aliased(User)
    seller = aliased(User)
    recent_disputes = []
    for dispute, buyer_name, seller_name, code in db.execute(
        select(Dispute, buyer.fullName, seller.fullName, Order.code)
        .join(buyer, buyer.id == Dispute.buyerId)
        .join(seller, seller.id == Dispute.sellerId)
        .join(Order, Order.id == Dispute.orderId)
        .where(Dispute.status.in_(("OPEN", "REVIEWING")))
        .order_by(Dispute.createdAt.desc())
        .limit(5)
    ).all():
        item = to_dict(dispute)
        item["buyer"] = {"fullName": buyer_name}
        item["seller"] = {"fullName": seller_name}
        item["order"] = {"code": code}
        recent_disputes.append(item)

    return {
        "kpis": {
            "monthlyRevenue": abs(revenue),
            "totalTransactions": total_transactions,
            "pendingRefunds": pending_refunds,
            "openDisputes": open_disputes,
        },
        "recentTransactions": recent_transactions,
        "recentDisputes": recent_disputes,
    }


@router.get("/transactions")
def transactions(request: Request, db: Session = Depends(get_db)):
    page = paginate(dict(request.query_params))
    conditions = []
    type_filter = request.query_params.get("type")
    if type_filter:
        conditions.append(WalletTransaction.type == type_filter)
    query_text = request.query_params.get("q")
    if query_text:
        like = f"%{query_text}%"
        conditions.append(
            or_(
                WalletTransaction.reference.ilike(like),
                WalletTransaction.note.ilike(like),
                WalletTransaction.walletId.in_(
                    select(Wallet.id)
                    .join(User, User.id == Wallet.userId)
                    .where(User.fullName.ilike(like))
                ),
            )
        )
    if request.query_params.get("from") or request.query_params.get("to"):
        start, end = date_range(dict(request.query_params))
        conditions.append(WalletTransaction.createdAt >= start)
        conditions.append(WalletTransaction.createdAt <= end)

    rows = db.execute(
        select(WalletTransaction, Wallet, User.id, User.fullName)
        .join(Wallet, Wallet.id == WalletTransaction.walletId)
        .join(User, User.id == Wallet.userId)
        .where(*conditions)
        .order_by(WalletTransaction.createdAt.desc())
        .offset(page["skip"])
        .limit(page["limit"])
    ).all()
    total = db.execute(
        select(func.count()).select_from(WalletTransaction).where(*conditions)
    ).scalar_one()

    data = []
    for txn, wallet, user_id, full_name in rows:
        item = to_dict(txn)
        item["wallet"] = {
            **to_dict(wallet),
            "user": {"id": user_id, "fullName": full_name},
        }
        data.append(item)
    return paged_result(data, total, page["page"], page["limit"])


@router.get("/revenue")
def revenue_report(request: Request, db: Session = Depends(get_db)):
    raw_months = request.query_params.get("months") or "6"
    parsed = js_parse_int(raw_months)
    # parseInt('abc') = NaN → vòng lặp của bản Node không chạy, trả mảng rỗng.
    months = 0 if parsed is None else min(12, max(1, parsed))

    labels = []
    monthly = []
    local_now = datetime.now().astimezone()
    for offset in range(months - 1, -1, -1):
        start_local = local_now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        year = start_local.year
        month = start_local.month - offset
        while month <= 0:
            month += 12
            year -= 1
        start_local = start_local.replace(year=year, month=month)
        next_local = start_local.replace(
            year=year + (1 if month == 12 else 0),
            month=1 if month == 12 else month + 1,
        )
        start = start_local.astimezone(timezone.utc).replace(tzinfo=None)
        end = next_local.astimezone(timezone.utc).replace(tzinfo=None)

        collected = db.execute(
            select(func.coalesce(func.sum(WalletTransaction.amount), 0)).where(
                WalletTransaction.type == "PLATFORM_FEE",
                WalletTransaction.amount < 0,
                WalletTransaction.createdAt >= start,
                WalletTransaction.createdAt < end,
            )
        ).scalar_one()
        labels.append(f"{month:02d}/{year}")
        monthly.append(abs(collected))

    by_category: dict[str, dict] = {}
    for listing_id, fee_sum, orders_count in db.execute(
        select(Order.listingId, func.coalesce(func.sum(Order.platformFee), 0), func.count())
        .where(Order.status == "COMPLETED")
        .group_by(Order.listingId)
    ).all():
        name = db.execute(
            select(Category.name)
            .join(Listing, Listing.categoryId == Category.id)
            .where(Listing.id == listing_id)
        ).scalar_one_or_none() or "Khác"
        bucket = by_category.setdefault(name, {"category": name, "orders": 0, "fee": 0})
        bucket["orders"] += orders_count
        bucket["fee"] += int(fee_sum)

    return {
        "total": sum(monthly),
        "labels": labels,
        "monthly": monthly,
        "byCategory": sorted(by_category.values(), key=lambda item: -item["fee"]),
    }


@router.get("/fees")
def list_fees(request: Request, db: Session = Depends(get_db)):
    conditions = []
    kind = request.query_params.get("kind")
    if kind:
        conditions.append(FeeConfig.kind == kind)
    rows = db.execute(
        select(FeeConfig).where(*conditions).order_by(FeeConfig.kind.asc(), FeeConfig.id.asc())
    ).scalars().all()
    return [to_dict(row) for row in rows]


@router.post("/fees", status_code=201)
def create_fee(
    payload: FeeIn,
    admin: CurrentUser = Depends(current_user),
    db: Session = Depends(get_db),
):
    fee = FeeConfig(**payload.model_dump(exclude_none=True), updatedAt=now())
    db.add(fee)
    db.flush()
    db.add(
        AuditLog(
            adminId=admin.id,
            action="CREATE_FEE",
            target=f"fee:{fee.id}",
            detail=payload.model_dump(exclude_none=True),
        )
    )
    db.commit()
    return to_dict(fee)


@router.patch("/fees/{fee_id}")
def update_fee(
    fee_id: int,
    payload: FeePatch,
    admin: CurrentUser = Depends(current_user),
    db: Session = Depends(get_db),
):
    fee = db.execute(select(FeeConfig).where(FeeConfig.id == fee_id)).scalar_one_or_none()
    if fee is None:
        raise ApiError(404, "Không tìm thấy dữ liệu")
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(fee, field, value)
    fee.updatedAt = now()
    db.add(
        AuditLog(
            adminId=admin.id,
            action="UPDATE_FEE",
            target=f"fee:{fee.id}",
            detail=changes,
        )
    )
    db.commit()
    return to_dict(fee)


@router.delete("/fees/{fee_id}")
def delete_fee(
    fee_id: int,
    admin: CurrentUser = Depends(current_user),
    db: Session = Depends(get_db),
):
    fee = db.execute(select(FeeConfig).where(FeeConfig.id == fee_id)).scalar_one_or_none()
    if fee is None:
        raise ApiError(404, "Không tìm thấy dữ liệu")
    db.delete(fee)
    db.add(AuditLog(adminId=admin.id, action="DELETE_FEE", target=f"fee:{fee_id}"))
    db.commit()
    return {"message": "Đã xoá cấu hình phí"}


@router.get("/charts/revenue")
def chart_revenue(request: Request, db: Session = Depends(get_db)):
    return daily_revenue(db, dict(request.query_params))


@router.get("/charts/order-status")
def chart_order_status(db: Session = Depends(get_db)):
    rows = db.execute(
        select(Order.status, func.count()).group_by(Order.status)
    ).all()
    return [{"status": status, "count": count} for status, count in rows]


@router.get("/withdrawals")
def withdrawals(request: Request, db: Session = Depends(get_db)):
    page = paginate(dict(request.query_params))
    conditions = []
    status = request.query_params.get("status")
    if status:
        if status not in WITHDRAWAL_STATUSES:
            raise ApiError(
                400,
                "Dữ liệu không hợp lệ",
                details=[{"field": "status", "message": f"Invalid enum value. Expected {' | '.join(WITHDRAWAL_STATUSES)}"}],
            )
        conditions.append(WithdrawalRequest.status == status)

    query_text = request.query_params.get("q")
    if query_text:
        like = f"%{query_text}%"
        conditions.append(
            or_(
                WithdrawalRequest.reference.ilike(like),
                WithdrawalRequest.userId.in_(select(User.id).where(User.fullName.ilike(like))),
            )
        )

    rows = db.execute(
        select(WithdrawalRequest, User.id, User.fullName)
        .join(User, User.id == WithdrawalRequest.userId)
        .where(*conditions)
        .order_by(WithdrawalRequest.createdAt.desc())
        .offset(page["skip"])
        .limit(page["limit"])
    ).all()
    total = db.execute(
        select(func.count()).select_from(WithdrawalRequest).where(*conditions)
    ).scalar_one()

    data = []
    for row, user_id, full_name in rows:
        item = to_dict(row)
        item["user"] = {"id": user_id, "fullName": full_name}
        data.append(item)
    return paged_result(data, total, page["page"], page["limit"])


@router.patch("/withdrawals/{withdrawal_id}")
def handle_withdrawal(
    withdrawal_id: int,
    payload: WithdrawalActionIn,
    admin: CurrentUser = Depends(current_user),
    db: Session = Depends(get_db),
):
    if withdrawal_id <= 0:
        raise ApiError(400, "Dữ liệu không hợp lệ", details=[{"field": "id", "message": "Invalid input"}])
    updated = transition_withdrawal(
        db,
        admin,
        withdrawal_id,
        {
            "action": payload.action,
            "resolution": payload.resolution,
            "transferReference": payload.transferReference,
        },
    )
    return to_dict(updated)
