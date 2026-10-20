"""Đơn hàng — port src/routes/orders.js."""
from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, field_validator
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import CurrentUser, current_user, require_role, verified_account
from ..errors import ApiError
from ..models import Escrow, Listing, Order
from ..pagination import paged_result, paginate
from ..quota import account_limit
from ..serialize import to_dict
from ..services.orders import create_single_order, serialize_order, serialize_orders
from ..utils import apply_wallet, notify, now, push_timeline, vnd
from ..validators import phone_vn

router = APIRouter()

TRANSITIONS = {
    "PENDING_DEPOSIT": ["CANCELLED"],
    "DEPOSITED": ["CONFIRMED", "CANCELLED"],
    "CONFIRMED": ["SHIPPING", "CANCELLED"],
    "SHIPPING": ["DELIVERED"],
    "DELIVERED": ["COMPLETED"],
}


class OrderIn(BaseModel):
    listingId: int
    offerId: int | None = None
    shipName: str
    shipPhone: str
    shipAddress: str
    note: str | None = None
    paymentMethod: Literal["MOMO_QR", "SAFEPAY_WALLET", "BANK_TRANSFER", "NAPAS", "COD"] = "MOMO_QR"
    promoCode: str | None = None
    settlementMethod: Literal["COD", "WALLET"] = "COD"

    @field_validator("shipName")
    @classmethod
    def _ship_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Tên người nhận không được bỏ trống")
        if len(value) > 100:
            raise ValueError("String must contain at most 100 character(s)")
        return value

    @field_validator("shipPhone")
    @classmethod
    def _ship_phone(cls, value: str) -> str:
        return phone_vn(value)

    @field_validator("shipAddress")
    @classmethod
    def _ship_address(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Địa chỉ nhận hàng không được bỏ trống")
        if len(value) > 500:
            raise ValueError("String must contain at most 500 character(s)")
        return value

    @field_validator("note")
    @classmethod
    def _note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if len(value) > 500:
            raise ValueError("String must contain at most 500 character(s)")
        return value


class StatusIn(BaseModel):
    to: Literal["CONFIRMED", "SHIPPING", "DELIVERED", "COMPLETED", "CANCELLED"]
    note: str | None = None
    trackingCode: str | None = None

    @field_validator("note")
    @classmethod
    def _note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if len(value) > 500:
            raise ValueError("String must contain at most 500 character(s)")
        return value

    @field_validator("trackingCode")
    @classmethod
    def _tracking(cls, value: str | None) -> str | None:
        return None if value is None else value.strip()


@router.post("", status_code=201)
def create_order(
    payload: OrderIn,
    user: CurrentUser = Depends(verified_account),
    _quota: CurrentUser = Depends(account_limit("CREATE_ORDER", 20, 86_400_000)),
    db: Session = Depends(get_db),
):
    ship = {
        "shipName": payload.shipName,
        "shipPhone": payload.shipPhone,
        "shipAddress": payload.shipAddress,
        "note": payload.note,
        "paymentMethod": payload.paymentMethod,
        "settlementMethod": payload.settlementMethod,
    }
    order = create_single_order(
        db,
        user.id,
        listing_id=payload.listingId,
        offer_id=payload.offerId,
        promo_code=payload.promoCode,
        ship=ship,
    )
    return to_dict(order)


@router.get("/mine")
def my_orders(
    request: Request,
    user: CurrentUser = Depends(current_user),
    db: Session = Depends(get_db),
):
    page = paginate(dict(request.query_params))
    conditions = [Order.buyerId == user.id]
    status = request.query_params.get("status")
    if status:
        conditions.append(Order.status == status)

    orders = db.execute(
        select(Order)
        .where(*conditions)
        .order_by(Order.createdAt.desc())
        .offset(page["skip"])
        .limit(page["limit"])
    ).scalars().all()
    total = db.execute(select(func.count()).select_from(Order).where(*conditions)).scalar_one()
    return paged_result(serialize_orders(db, orders), total, page["page"], page["limit"])


@router.get("/sales", dependencies=[Depends(require_role("SELLER"))])
def my_sales(
    request: Request,
    user: CurrentUser = Depends(current_user),
    db: Session = Depends(get_db),
):
    page = paginate(dict(request.query_params))
    conditions = [Order.sellerId == user.id]
    status = request.query_params.get("status")
    if status:
        conditions.append(Order.status == status)

    orders = db.execute(
        select(Order)
        .where(*conditions)
        .order_by(Order.createdAt.desc())
        .offset(page["skip"])
        .limit(page["limit"])
    ).scalars().all()
    total = db.execute(select(func.count()).select_from(Order).where(*conditions)).scalar_one()
    return paged_result(serialize_orders(db, orders), total, page["page"], page["limit"])


@router.get("/admin/all", dependencies=[Depends(require_role("ADMIN_FINANCE", "ADMIN_CONTENT"))])
def all_orders(request: Request, db: Session = Depends(get_db)):
    page = paginate(dict(request.query_params))
    conditions = []
    status = request.query_params.get("status")
    if status:
        conditions.append(Order.status == status)
    code = request.query_params.get("q")
    if code:
        conditions.append(Order.code.ilike(f"%{code}%"))

    orders = db.execute(
        select(Order)
        .where(*conditions)
        .order_by(Order.createdAt.desc())
        .offset(page["skip"])
        .limit(page["limit"])
    ).scalars().all()
    total = db.execute(select(func.count()).select_from(Order).where(*conditions)).scalar_one()
    return paged_result(serialize_orders(db, orders), total, page["page"], page["limit"])


@router.get("/{order_id}")
def order_detail(
    order_id: int,
    user: CurrentUser = Depends(current_user),
    db: Session = Depends(get_db),
):
    order = db.execute(select(Order).where(Order.id == order_id)).scalar_one_or_none()
    if order is None:
        raise ApiError(404, "Không tìm thấy đơn hàng")
    if (
        order.buyerId != user.id
        and order.sellerId != user.id
        and not any(role.startswith("ADMIN") for role in user.roles)
    ):
        raise ApiError(403, "Không có quyền xem đơn này")
    return serialize_order(db, order, with_review=True)


@router.patch("/{order_id}/status")
def change_status(
    order_id: int,
    payload: StatusIn,
    user: CurrentUser = Depends(current_user),
    db: Session = Depends(get_db),
):
    order = db.execute(select(Order).where(Order.id == order_id)).scalar_one_or_none()
    if order is None:
        raise ApiError(404, "Không tìm thấy đơn hàng")

    to = payload.to
    if to not in TRANSITIONS.get(order.status, []):
        raise ApiError(400, f"Không thể chuyển từ {order.status} sang {to}")

    is_buyer = order.buyerId == user.id
    is_seller = order.sellerId == user.id
    if to in ("CONFIRMED", "SHIPPING", "DELIVERED") and not is_seller:
        raise ApiError(403, "Chỉ người bán thực hiện bước này")
    if to == "COMPLETED" and not is_buyer:
        raise ApiError(403, "Chỉ người mua xác nhận đã nhận hàng")
    if to == "COMPLETED" and order.remainingAmount > 0:
        raise ApiError(
            400,
            "Cần thanh toán phần còn lại hoặc người bán xác nhận đã thu COD trước khi hoàn tất",
        )
    if to == "CANCELLED" and not is_buyer and not is_seller:
        raise ApiError(403, "Không có quyền huỷ đơn")

    moved = db.execute(
        update(Order)
        .where(Order.id == order.id, Order.status == order.status)
        .values(
            status=to,
            trackingCode=payload.trackingCode or order.trackingCode,
            cancelReason=payload.note if to == "CANCELLED" else order.cancelReason,
            updatedAt=now(),
        )
    )
    if moved.rowcount == 0:
        raise ApiError(409, "Trạng thái đơn vừa thay đổi, vui lòng tải lại")

    updated = db.execute(select(Order).where(Order.id == order.id)).scalar_one()
    push_timeline(db, updated.id, to, payload.note)

    if to == "CANCELLED":
        escrow = db.execute(select(Escrow).where(Escrow.orderId == updated.id)).scalar_one_or_none()
        if escrow is not None and escrow.status == "HELD":
            refunded = db.execute(
                update(Escrow)
                .where(Escrow.id == escrow.id, Escrow.status == "HELD")
                .values(status="REFUNDED", releasedAt=now())
            )
            if refunded.rowcount:
                apply_wallet(
                    db,
                    updated.buyerId,
                    "REFUND",
                    escrow.amount,
                    updated.code,
                    f"Hoàn cọc đơn đã huỷ {updated.code}",
                )
        db.execute(
            update(Listing)
            .where(Listing.id == updated.listingId, Listing.status == "RESERVED")
            .values(status="ACTIVE", updatedAt=now())
        )

    if to == "COMPLETED":
        escrow = db.execute(select(Escrow).where(Escrow.orderId == updated.id)).scalar_one_or_none()
        if escrow is not None and escrow.status == "HELD":
            released = db.execute(
                update(Escrow)
                .where(Escrow.id == escrow.id, Escrow.status == "HELD")
                .values(status="RELEASED", releasedAt=now())
            )
            if released.rowcount:
                platform_fee = min(updated.platformFee, escrow.amount)
                if escrow.amount:
                    apply_wallet(
                        db,
                        updated.sellerId,
                        "ORDER_INCOME",
                        escrow.amount,
                        updated.code,
                        f"Tiền cọc đơn {updated.code}",
                    )
                if platform_fee:
                    apply_wallet(
                        db,
                        updated.sellerId,
                        "PLATFORM_FEE",
                        -platform_fee,
                        updated.code,
                        f"Phí sàn đơn {updated.code}",
                    )
                db.execute(
                    update(Listing)
                    .where(Listing.id == updated.listingId)
                    .values(status="SOLD_OUT", updatedAt=now())
                )

    other_id = order.sellerId if is_buyer else order.buyerId
    notify(
        db,
        other_id,
        "ORDER",
        f"Đơn {order.code}: {to}",
        payload.note or f"Trạng thái đơn hàng chuyển sang {to}",
        {"orderId": order.id},
    )
    db.commit()
    return to_dict(updated)


@router.post("/{order_id}/confirm-cod")
def confirm_cod(
    order_id: int,
    user: CurrentUser = Depends(current_user),
    db: Session = Depends(get_db),
):
    order = db.execute(select(Order).where(Order.id == order_id)).scalar_one_or_none()
    if order is None or order.sellerId != user.id:
        raise ApiError(404, "Không tìm thấy đơn bán")
    if order.settlementMethod != "COD" or order.status != "DELIVERED" or order.remainingAmount <= 0:
        raise ApiError(400, "Chỉ xác nhận COD sau khi giao hàng và còn tiền cần thu")

    # update() đồng bộ object trong session → giữ số tiền gốc để ghi timeline.
    collected = order.remainingAmount
    moved = db.execute(
        update(Order)
        .where(
            Order.id == order.id,
            Order.status == "DELIVERED",
            Order.remainingAmount == collected,
            Order.codCollectedAt.is_(None),
        )
        .values(remainingAmount=0, codCollectedAt=now(), updatedAt=now())
    )
    if moved.rowcount == 0:
        raise ApiError(409, "Đơn vừa thay đổi")
    push_timeline(
        db,
        order.id,
        "COD_COLLECTED",
        f"Người bán khai báo đã thu {vnd(collected)}đ COD; chờ người mua xác nhận hoàn tất",
    )
    notify(db, order.buyerId, "ORDER", "Người bán đã xác nhận thu COD", order.code, {"orderId": order.id})
    db.commit()
    return {"message": "Đã ghi nhận thu COD; tiền này không được cộng lần nữa vào ví"}
