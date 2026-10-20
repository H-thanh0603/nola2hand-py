"""SafePay: giữ cọc, hoàn cọc, thanh toán phần còn lại — port src/routes/escrow.js.

Bản Node gắn router này ở /api/v1/escrow nên đường dẫn thật là
/api/v1/escrow/orders/:id/deposit và /api/v1/escrow/:id/refund.
"""
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import CurrentUser, current_user
from ..errors import ApiError
from ..models import Escrow, Listing, Order, ReturnRequest
from ..serialize import to_dict
from ..utils import apply_wallet, notify, now, push_timeline, vnd

router = APIRouter()


class DepositIn(BaseModel):
    amount: int | None = Field(None, ge=1)
    paymentMethod: Literal["MOMO_QR", "SAFEPAY_WALLET", "BANK_TRANSFER", "NAPAS"] = "SAFEPAY_WALLET"


class RefundIn(BaseModel):
    reason: str

    @field_validator("reason")
    @classmethod
    def _reason(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("String must contain at least 1 character(s)")
        if len(value) > 500:
            raise ValueError("String must contain at most 500 character(s)")
        return value


@router.post("/orders/{order_id}/deposit", status_code=201)
def deposit(
    order_id: int,
    payload: DepositIn,
    user: CurrentUser = Depends(current_user),
    db: Session = Depends(get_db),
):
    order = db.execute(select(Order).where(Order.id == order_id)).scalar_one_or_none()
    if order is None:
        raise ApiError(404, "Không tìm thấy đơn hàng")
    if order.buyerId != user.id:
        raise ApiError(403, "Chỉ người mua đặt cọc được")
    if order.status != "PENDING_DEPOSIT":
        raise ApiError(400, f"Đơn đang ở trạng thái {order.status}")
    if payload.paymentMethod != "SAFEPAY_WALLET":
        raise ApiError(400, "Thanh toán qua cổng ngoài chưa được tích hợp webhook xác minh")

    minimum = -(-order.totalAmount * 10 // 100)  # Math.ceil(10%)
    amount = payload.amount or -(-order.totalAmount * 20 // 100)
    if amount < minimum:
        raise ApiError(400, f"Tiền cọc tối thiểu {vnd(minimum)}đ (10%)")
    if amount > order.totalAmount:
        raise ApiError(400, "Tiền cọc không vượt quá giá trị đơn")

    moment = now()
    moved = db.execute(
        update(Order)
        .where(
            Order.id == order.id,
            Order.status == "PENDING_DEPOSIT",
            (Order.reservationExpiresAt.is_(None)) | (Order.reservationExpiresAt > moment),
        )
        .values(
            status="DEPOSITED",
            depositAmount=amount,
            remainingAmount=order.totalAmount - amount,
            paymentMethod=payload.paymentMethod,
            updatedAt=moment,
        )
    )
    if moved.rowcount == 0:
        raise ApiError(409, "Đơn đã hết hạn giữ món hoặc đã được xử lý")

    apply_wallet(
        db,
        user.id,
        "ORDER_PAYMENT",
        -amount,
        order.code,
        f"Đặt cọc đơn {order.code}",
    )
    escrow = Escrow(orderId=order.id, amount=amount, status="HELD")
    db.add(escrow)
    db.flush()
    push_timeline(db, order.id, "DEPOSITED", f"Đã đặt cọc {vnd(amount)}đ qua SafePay")

    updated = db.execute(select(Order).where(Order.id == order.id)).scalar_one()
    order_payload = to_dict(updated)
    order_payload["escrow"] = to_dict(escrow)

    notify(
        db,
        order.sellerId,
        "ESCROW",
        "Người mua đã đặt cọc",
        f"Đơn {order.code} đã cọc {vnd(amount)}đ — hãy chuẩn bị gửi hàng",
        {"orderId": order.id},
    )
    db.commit()
    return {
        "message": "Đặt cọc thành công, tiền được SafePay giữ hộ",
        "order": order_payload,
        "escrow": to_dict(escrow),
    }


@router.post("/{escrow_id}/refund")
def refund(
    escrow_id: int,
    payload: RefundIn,
    user: CurrentUser = Depends(current_user),
    db: Session = Depends(get_db),
):
    escrow = db.execute(select(Escrow).where(Escrow.id == escrow_id)).scalar_one_or_none()
    if escrow is None:
        raise ApiError(404, "Không tìm thấy khoản ký quỹ")
    if escrow.status != "HELD":
        raise ApiError(400, f"Khoản ký quỹ đang ở trạng thái {escrow.status}")

    order = db.execute(select(Order).where(Order.id == escrow.orderId)).scalar_one()
    was_shipping = order.status == "SHIPPING"
    is_admin = "ADMIN_FINANCE" in user.roles
    is_seller_cancel = user.id == order.sellerId
    if not is_admin and not is_seller_cancel:
        raise ApiError(403, "Không có quyền hoàn cọc")

    allowed = ["DEPOSITED", "CONFIRMED", "SHIPPING"] + (["DISPUTED"] if is_admin else [])
    moved = db.execute(
        update(Order)
        .where(Order.id == escrow.orderId, Order.status.in_(allowed))
        .values(status="REFUNDED", updatedAt=now())
    )
    if moved.rowcount == 0:
        raise ApiError(409, "Đơn không còn được phép hoàn tiền")

    returning = db.execute(
        select(ReturnRequest).where(ReturnRequest.orderId == escrow.orderId)
    ).scalar_one_or_none()
    if returning is not None and returning.status not in ("REJECTED", "CANCELLED"):
        raise ApiError(409, "Phải hoàn tiền qua tiến trình trả hàng")

    current = db.execute(select(Escrow).where(Escrow.id == escrow.id)).scalar_one_or_none()
    if current is None or current.status != "HELD":
        raise ApiError(409, "Khoản ký quỹ không còn khả dụng")

    refunded = db.execute(
        update(Escrow)
        .where(Escrow.id == escrow.id, Escrow.status == "HELD")
        .values(status="REFUNDED", releasedAt=now())
    )
    if refunded.rowcount == 0:
        raise ApiError(409, "Khoản ký quỹ vừa được xử lý, vui lòng tải lại")

    apply_wallet(
        db,
        order.buyerId,
        "REFUND",
        current.amount,
        order.code,
        f"Hoàn cọc: {payload.reason}",
    )
    db.execute(
        update(Listing)
        .where(Listing.id == order.listingId, Listing.status == "RESERVED")
        .values(status="HIDDEN" if was_shipping else "ACTIVE", updatedAt=now())
    )
    push_timeline(db, escrow.orderId, "REFUNDED", f"Hoàn cọc: {payload.reason}")
    notify(
        db,
        order.buyerId,
        "ESCROW",
        "Đã hoàn tiền cọc",
        f"{vnd(current.amount)}đ đã được hoàn về ví",
        {"orderId": escrow.orderId},
    )
    db.commit()
    return {"message": "Hoàn cọc thành công", "refundedAmount": current.amount}


@router.get("/mine")
def my_escrows(user: CurrentUser = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.execute(
        select(Escrow, Order.code, Order.priceAgreed, Order.status)
        .join(Order, Order.id == Escrow.orderId)
        .where((Order.buyerId == user.id) | (Order.sellerId == user.id))
        .order_by(Escrow.heldAt.desc())
    ).all()

    items = []
    for escrow, code, price_agreed, status in rows:
        item = to_dict(escrow)
        item["order"] = {"code": code, "priceAgreed": price_agreed, "status": status}
        items.append(item)
    return items


@router.post("/orders/{order_id}/pay-remainder")
def pay_remainder(
    order_id: int,
    user: CurrentUser = Depends(current_user),
    db: Session = Depends(get_db),
):
    order = db.execute(select(Order).where(Order.id == order_id)).scalar_one_or_none()
    if order is None or order.buyerId != user.id:
        raise ApiError(404, "Không tìm thấy đơn mua")
    if order.status not in ("DEPOSITED", "CONFIRMED", "SHIPPING", "DELIVERED") or order.remainingAmount <= 0:
        raise ApiError(400, "Đơn không còn khoản thanh toán khả dụng")

    # update() đồng bộ luôn object trong session, nên phải giữ giá trị gốc trước khi ghi.
    remaining = order.remainingAmount
    moved = db.execute(
        update(Order)
        .where(Order.id == order.id, Order.status == order.status, Order.remainingAmount == remaining)
        .values(remainingAmount=0, settlementMethod="WALLET", updatedAt=now())
    )
    if moved.rowcount == 0:
        raise ApiError(409, "Đơn vừa được thanh toán hoặc thay đổi")

    escrow = db.execute(
        update(Escrow)
        .where(Escrow.orderId == order.id, Escrow.status == "HELD")
        .values(amount=Escrow.amount + remaining)
    )
    if escrow.rowcount == 0:
        raise ApiError(409, "Khoản ký quỹ không còn khả dụng")

    apply_wallet(
        db,
        order.buyerId,
        "ORDER_PAYMENT",
        -remaining,
        order.code,
        "Thanh toán phần còn lại vào ký quỹ",
    )
    push_timeline(
        db,
        order.id,
        "FULLY_PAID",
        "Đã thanh toán đủ qua ví; toàn bộ tiền được giữ trong SafePay",
    )
    db.commit()
    return {"message": "Đã thanh toán phần còn lại, tiền được giữ trong SafePay"}
