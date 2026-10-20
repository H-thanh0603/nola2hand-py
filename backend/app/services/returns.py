"""Trả hàng sau giao — port src/services/returns.js."""
import uuid
from datetime import timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..deps import CurrentUser
from ..errors import ApiError
from ..models import AuditLog, Dispute, Escrow, Listing, Order, OrderTimeline, ReturnRequest
from ..utils import apply_wallet, notify, now, push_timeline
from .locks import lock_order
from .wallet_holds import finish_hold, hold_wallet, post_held_ledger

STAGES = {
    "APPROVE": "REQUESTED",
    "REJECT": "REQUESTED",
    "CANCEL": "REQUESTED",
    "SHIP": "APPROVED",
    "RECEIVE": "SHIPPED",
    "REFUND": "RECEIVED",
    "COD_REFUND": "RECEIVED",
    "COD_CONFIRM": "RECEIVED",
}


def check_return_window(db: Session, order_id: int, moment=None) -> None:
    """Chỉ cho trả hàng trong 7 ngày kể từ lúc giao hoặc hoàn tất."""
    moment = moment or now()
    stamps = db.execute(
        select(OrderTimeline.status, OrderTimeline.createdAt)
        .where(OrderTimeline.orderId == order_id, OrderTimeline.status.in_(("DELIVERED", "COMPLETED")))
        .order_by(OrderTimeline.createdAt.asc())
    ).all()
    delivered = next((stamp for status, stamp in stamps if status == "DELIVERED"), None)
    completed = next((stamp for status, stamp in stamps if status == "COMPLETED"), None)
    anchor = delivered or completed
    if anchor is None or moment - anchor > timedelta(days=7):
        raise ApiError(400, "Hết thời hạn 7 ngày yêu cầu trả hàng")


def request_return(db: Session, buyer_id: int, order_id: int, payload: dict) -> ReturnRequest:
    lock_order(db, order_id)

    order = db.execute(select(Order).where(Order.id == order_id)).scalar_one_or_none()
    if order is None or order.buyerId != buyer_id:
        raise ApiError(404, "Không tìm thấy đơn mua")
    existing = db.execute(
        select(ReturnRequest).where(ReturnRequest.orderId == order_id)
    ).scalar_one_or_none()
    if existing is not None:
        raise ApiError(409, "Đơn đã có yêu cầu trả hàng")
    dispute_id = db.execute(select(Dispute.id).where(Dispute.orderId == order_id)).scalar_one_or_none()
    if order.status not in ("DELIVERED", "COMPLETED") or dispute_id is not None:
        raise ApiError(409, "Đơn không đủ điều kiện trả hàng hoặc đã có tranh chấp")
    check_return_window(db, order_id)

    escrow = db.execute(select(Escrow).where(Escrow.orderId == order_id)).scalar_one_or_none()
    if escrow is None or escrow.status not in ("HELD", "RELEASED"):
        raise ApiError(409, "Không có khoản thanh toán khả dụng để hoàn")

    refund_amount = escrow.amount
    cod_amount = max(0, order.totalAmount - refund_amount) if order.codCollectedAt else 0

    request = ReturnRequest(
        orderId=order_id,
        reference=f"RET-{uuid.uuid4()}",
        originalOrderStatus=order.status,
        reason=payload["reason"],
        evidences=payload.get("evidences") or [],
        refundAmount=refund_amount,
        codAmount=cod_amount,
        updatedAt=now(),
    )
    db.add(request)
    db.flush()
    db.execute(
        update(Order).where(Order.id == order_id).values(status="DISPUTED", updatedAt=now())
    )
    push_timeline(db, order_id, "RETURN_REQUESTED", payload["reason"])
    notify(
        db,
        order.sellerId,
        "RETURN",
        "Có yêu cầu trả hàng",
        order.code,
        {"orderId": order_id, "returnId": request.id},
    )
    db.commit()
    return request


def transition_return(
    db: Session, actor: CurrentUser, request_id: int, payload: dict
) -> ReturnRequest:
    pointer = db.execute(
        select(ReturnRequest.orderId).where(ReturnRequest.id == request_id)
    ).scalar_one_or_none()
    if pointer is None:
        raise ApiError(404, "Không tìm thấy yêu cầu trả hàng")

    order_id = pointer
    lock_order(db, order_id)

    request = db.execute(
        select(ReturnRequest).where(ReturnRequest.id == request_id)
    ).scalar_one_or_none()
    if request is None:
        raise ApiError(404, "Không tìm thấy yêu cầu trả hàng")
    order = db.execute(select(Order).where(Order.id == order_id)).scalar_one()
    escrow = db.execute(select(Escrow).where(Escrow.orderId == order_id)).scalar_one_or_none()

    is_admin = "ADMIN_FINANCE" in actor.roles and actor.id not in (order.buyerId, order.sellerId)
    is_seller = actor.id == order.sellerId
    is_buyer = actor.id == order.buyerId
    action = payload["action"]

    if action in ("APPROVE", "REJECT", "RECEIVE"):
        permitted = is_seller or is_admin
    elif action in ("CANCEL", "SHIP", "COD_CONFIRM"):
        permitted = is_buyer
    elif action == "COD_REFUND":
        permitted = is_seller
    elif action == "REFUND":
        permitted = is_admin
    else:
        permitted = False
    if not permitted:
        raise ApiError(403, "Không có quyền thực hiện bước trả hàng này")
    if request.status != STAGES[action] or order.status != "DISPUTED":
        raise ApiError(409, "Tiến trình đã thay đổi hoặc không thể bỏ qua bước")

    note = payload.get("note")
    changes: dict = {"resolution": note or request.resolution}

    if action == "APPROVE":
        if (
            escrow is None
            or escrow.status not in ("HELD", "RELEASED")
            or escrow.amount != request.refundAmount
        ):
            raise ApiError(409, "Khoản hoàn đã thay đổi, cần đối soát")
        if escrow.status == "RELEASED":
            hold_wallet(db, order.sellerId, request.refundAmount)
        changes.update(
            status="APPROVED",
            approvedAt=now(),
            fundingSource="ESCROW" if escrow.status == "HELD" else "SELLER_WALLET",
        )
    elif action in ("REJECT", "CANCEL"):
        changes["status"] = "REJECTED" if action == "REJECT" else "CANCELLED"
        db.execute(
            update(Order)
            .where(Order.id == order.id)
            .values(status=request.originalOrderStatus, updatedAt=now())
        )
    elif action == "SHIP":
        if not (payload.get("trackingCode") or "").strip():
            raise ApiError(400, "Cần mã vận đơn hoặc thông tin bàn giao")
        changes.update(status="SHIPPED", shippedAt=now(), trackingCode=payload["trackingCode"])
    elif action == "RECEIVE":
        if not (payload.get("note") or "").strip():
            raise ApiError(400, "Cần ghi nhận tình trạng hàng đã nhận lại")
        changes.update(status="RECEIVED", receivedAt=now(), receivedNote=payload["note"])
    elif action == "COD_REFUND":
        if not request.codAmount or request.codRefundedAt or not (payload.get("codReference") or "").strip():
            raise ApiError(409, "Cần khoản COD và chứng từ hoàn thực tế chưa ghi nhận")
        changes.update(codReference=payload["codReference"], codRefundedAt=now())
    elif action == "COD_CONFIRM":
        if not request.codRefundedAt or request.codConfirmedAt:
            raise ApiError(409, "Người bán chưa ghi nhận hoàn COD hoặc đã xác nhận")
        changes["codConfirmedAt"] = now()
    elif action == "REFUND":
        if request.codAmount > 0 and not request.codConfirmedAt:
            raise ApiError(409, "Cần người mua xác nhận đã nhận lại COD ngoài ví")
        if request.fundingSource == "ESCROW":
            claimed = db.execute(
                update(Escrow)
                .where(
                    Escrow.orderId == order.id,
                    Escrow.status == "HELD",
                    Escrow.amount == request.refundAmount,
                )
                .values(status="REFUNDED", releasedAt=now())
            )
            if claimed.rowcount == 0:
                raise ApiError(409, "Khoản ký quỹ đã thay đổi")
        elif request.fundingSource == "SELLER_WALLET":
            wallet = finish_hold(db, order.sellerId, request.refundAmount)
            post_held_ledger(
                db,
                wallet,
                [{"type": "ORDER_INCOME", "amount": -request.refundAmount}],
                request.reference,
                f"Hoàn tiền trả hàng {order.code}",
            )
        else:
            raise ApiError(409, "Chưa giữ đủ tiền cho yêu cầu hoàn")

        apply_wallet(
            db,
            order.buyerId,
            "REFUND",
            request.refundAmount,
            request.reference,
            f"Hoàn trả hàng {order.code}",
        )
        db.execute(
            update(Order)
            .where(Order.id == order.id)
            .values(status="REFUNDED", remainingAmount=0, updatedAt=now())
        )
        db.execute(
            update(Listing)
            .where(Listing.id == order.listingId, Listing.status.in_(("RESERVED", "SOLD_OUT")))
            .values(status="HIDDEN", updatedAt=now())
        )
        changes.update(status="REFUNDED", refundedAt=now())

    db.execute(
        update(ReturnRequest)
        .where(ReturnRequest.id == request_id)
        .values(**changes, updatedAt=now())
    )
    push_timeline(
        db,
        order.id,
        f"RETURN_{action}",
        note or payload.get("trackingCode") or payload.get("codReference") or action,
    )
    if is_admin:
        db.add(
            AuditLog(
                adminId=actor.id,
                action=f"RETURN_{action}",
                target=f"return:{request_id}",
                detail={
                    "refundAmount": request.refundAmount,
                    "codAmount": request.codAmount,
                    "note": note or "",
                },
            )
        )

    target_id = order.sellerId if is_buyer else order.buyerId
    notify(
        db,
        target_id,
        "RETURN",
        "Tiến trình trả hàng cập nhật",
        f"{order.code}: {request.status}",
        {"orderId": order.id, "returnId": request_id},
    )
    db.commit()
    return request
