"""Tranh chấp — port src/routes/disputes.js."""
from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, field_validator
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import CurrentUser, current_user, require_role
from ..errors import ApiError
from ..models import (
    AuditLog,
    Dispute,
    DisputeEvidence,
    Escrow,
    Listing,
    Order,
    ReturnRequest,
    Role,
    User,
    UserRole,
)
from ..pagination import paged_result, paginate
from ..serialize import to_dict
from ..services.evidence import assert_own_evidence
from ..utils import apply_wallet, gen_dispute_code, notify, now, push_timeline
from ..validators import http_url

router = APIRouter()

DISPUTE_STATUSES = ("OPEN", "REVIEWING", "REFUNDED", "REJECTED", "CLOSED")


class DisputeIn(BaseModel):
    reason: str
    description: str
    evidences: list[str] | None = None

    @field_validator("reason")
    @classmethod
    def _reason(cls, value: str) -> str:
        value = value.strip()
        if not 1 <= len(value) <= 200:
            raise ValueError("String must contain at least 1 character(s)" if not value else "String must contain at most 200 character(s)")
        return value

    @field_validator("description")
    @classmethod
    def _description(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 10:
            raise ValueError("String must contain at least 10 character(s)")
        if len(value) > 2000:
            raise ValueError("String must contain at most 2000 character(s)")
        return value

    @field_validator("evidences")
    @classmethod
    def _evidences(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        if len(value) > 5:
            raise ValueError("Array must contain at most 5 element(s)")
        return [http_url(url, "Ảnh bằng chứng") for url in value]


class ResolveIn(BaseModel):
    decision: Literal["BUYER_WINS", "SELLER_WINS", "SPLIT", "REFUND_BUYER", "REJECT"]
    resolution: str

    @field_validator("resolution")
    @classmethod
    def _resolution(cls, value: str) -> str:
        value = value.strip()
        if not 1 <= len(value) <= 1000:
            raise ValueError("String must contain at least 1 character(s)" if not value else "String must contain at most 1000 character(s)")
        return value


@router.post("/orders/{order_id}/disputes", status_code=201)
def open_dispute(
    order_id: int,
    payload: DisputeIn,
    user: CurrentUser = Depends(current_user),
    db: Session = Depends(get_db),
):
    assert_own_evidence(payload.evidences, user.id)

    order = db.execute(select(Order).where(Order.id == order_id)).scalar_one_or_none()
    if order is None:
        raise ApiError(404, "Không tìm thấy đơn hàng")
    if order.buyerId != user.id:
        raise ApiError(403, "Chỉ người mua mở tranh chấp được")
    if order.status not in ("SHIPPING", "DELIVERED", "DEPOSITED", "CONFIRMED"):
        raise ApiError(400, f"Không thể mở tranh chấp ở trạng thái {order.status}")

    existing = db.execute(select(Dispute.id).where(Dispute.orderId == order.id)).scalar_one_or_none()
    if existing is not None:
        raise ApiError(400, "Đơn này đã có tranh chấp")

    moved = db.execute(
        update(Order)
        .where(Order.id == order.id, Order.status == order.status)
        .values(status="DISPUTED", updatedAt=now())
    )
    if moved.rowcount == 0:
        raise ApiError(409, "Đơn đã đổi trạng thái, hãy tải lại")

    returning = db.execute(
        select(ReturnRequest.status).where(ReturnRequest.orderId == order.id)
    ).scalar_one_or_none()
    if returning is not None and returning not in ("REJECTED", "CANCELLED"):
        raise ApiError(409, "Đơn đang có yêu cầu trả hàng")

    escrow = db.execute(select(Escrow).where(Escrow.orderId == order.id)).scalar_one_or_none()
    dispute = Dispute(
        code=gen_dispute_code(),
        orderId=order.id,
        buyerId=order.buyerId,
        sellerId=order.sellerId,
        reason=payload.reason,
        description=payload.description,
        amount=escrow.amount if escrow is not None and escrow.status == "HELD" else 0,
        updatedAt=now(),
    )
    db.add(dispute)
    db.flush()

    for url in payload.evidences or []:
        db.add(DisputeEvidence(disputeId=dispute.id, url=url))

    push_timeline(db, order.id, "DISPUTED", f"Mở tranh chấp {dispute.code}: {payload.reason}")

    admins = db.execute(
        select(User.id)
        .join(UserRole, UserRole.userId == User.id)
        .join(Role, Role.id == UserRole.roleId)
        .where(Role.name == "ADMIN_FINANCE", User.status == "ACTIVE")
    ).scalars().all()
    for admin_id in admins:
        notify(
            db,
            admin_id,
            "DISPUTE",
            "Tranh chấp mới cần xử lý",
            f"{dispute.code} — đơn {order.code}: {payload.reason}",
            {"disputeId": dispute.id},
        )
    db.commit()
    db.refresh(dispute)

    return {
        "message": "Đã mở tranh chấp, admin sẽ xem xét trong 24h",
        "dispute": to_dict(dispute),
    }


def _evidence_map(db: Session, dispute_ids: list[int]) -> dict[int, list[dict]]:
    evidences: dict[int, list[dict]] = {dispute_id: [] for dispute_id in dispute_ids}
    for row in db.execute(
        select(DisputeEvidence).where(DisputeEvidence.disputeId.in_(dispute_ids))
    ).scalars():
        evidences[row.disputeId].append(to_dict(row))
    return evidences


@router.get("/mine")
def my_disputes(user: CurrentUser = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.execute(
        select(Dispute, Order.code)
        .join(Order, Order.id == Dispute.orderId)
        .where((Dispute.buyerId == user.id) | (Dispute.sellerId == user.id))
        .order_by(Dispute.createdAt.desc())
    ).all()
    evidences = _evidence_map(db, [dispute.id for dispute, _code in rows])
    items = []
    for dispute, code in rows:
        item = to_dict(dispute)
        item["order"] = {"code": code}
        item["evidences"] = evidences[dispute.id]
        items.append(item)
    return items


@router.get("/admin/all")
def all_disputes(
    request: Request,
    _admin: CurrentUser = Depends(require_role("ADMIN_FINANCE")),
    db: Session = Depends(get_db),
):
    page = paginate(dict(request.query_params))
    conditions = []
    status = request.query_params.get("status")
    if status:
        conditions.append(Dispute.status == status)
    query_text = request.query_params.get("q")
    if query_text:
        like = f"%{query_text}%"
        conditions.append(
            Dispute.code.ilike(like)
            | Dispute.reason.ilike(like)
            | Dispute.orderId.in_(select(Order.id).where(Order.code.ilike(like)))
        )

    rows = db.execute(
        select(Dispute)
        .where(*conditions)
        .order_by(Dispute.createdAt.desc())
        .offset(page["skip"])
        .limit(page["limit"])
    ).scalars().all()
    total = db.execute(
        select(func.count()).select_from(Dispute).where(*conditions)
    ).scalar_one()

    disputes = list(rows)
    order_ids = {dispute.orderId for dispute in disputes}
    orders = {
        order.id: order.code
        for order in db.execute(select(Order).where(Order.id.in_(order_ids))).scalars()
    }
    user_ids = {dispute.buyerId for dispute in disputes} | {dispute.sellerId for dispute in disputes}
    names = {
        user_id: full_name
        for user_id, full_name in db.execute(
            select(User.id, User.fullName).where(User.id.in_(user_ids))
        ).all()
    }
    evidences = _evidence_map(db, [dispute.id for dispute in disputes])

    items = []
    for dispute in disputes:
        item = to_dict(dispute)
        item["buyer"] = {"id": dispute.buyerId, "fullName": names.get(dispute.buyerId)}
        item["seller"] = {"id": dispute.sellerId, "fullName": names.get(dispute.sellerId)}
        item["order"] = {"code": orders.get(dispute.orderId)}
        item["evidences"] = evidences[dispute.id]
        items.append(item)
    return paged_result(items, total, page["page"], page["limit"])


@router.patch("/admin/{dispute_id}/resolve")
def resolve_dispute(
    dispute_id: int,
    payload: ResolveIn,
    admin: CurrentUser = Depends(require_role("ADMIN_FINANCE")),
    db: Session = Depends(get_db),
):
    dispute = db.execute(select(Dispute).where(Dispute.id == dispute_id)).scalar_one_or_none()
    if dispute is None:
        raise ApiError(404, "Không tìm thấy tranh chấp")
    if dispute.status not in ("OPEN", "REVIEWING"):
        raise ApiError(400, "Tranh chấp đã được xử lý")

    decision = "BUYER_WINS" if payload.decision == "REFUND_BUYER" else payload.decision
    resolution = payload.resolution
    order = db.execute(select(Order).where(Order.id == dispute.orderId)).scalar_one()
    escrow = db.execute(select(Escrow).where(Escrow.orderId == order.id)).scalar_one_or_none()

    locked = db.execute(
        update(Order)
        .where(Order.id == order.id, Order.status == "DISPUTED")
        .values(status="DISPUTED", updatedAt=now())
    )
    if locked.rowcount == 0:
        raise ApiError(409, "Đơn không còn ở trạng thái tranh chấp")

    next_status = "REJECTED" if decision == "REJECT" else "CLOSED" if decision == "SELLER_WINS" else "REFUNDED"
    claimed = db.execute(
        update(Dispute)
        .where(Dispute.id == dispute.id, Dispute.status.in_(("OPEN", "REVIEWING")))
        .values(status=next_status, resolution=resolution, updatedAt=now())
    )
    if claimed.rowcount == 0:
        raise ApiError(409, "Tranh chấp đã được xử lý")

    if decision == "BUYER_WINS":
        if escrow is not None and escrow.status == "HELD":
            db.execute(
                update(Escrow)
                .where(Escrow.id == escrow.id)
                .values(status="REFUNDED", releasedAt=now())
            )
            apply_wallet(
                db,
                dispute.buyerId,
                "REFUND",
                escrow.amount,
                order.code,
                f"Hoàn tiền tranh chấp {dispute.code}",
            )
        db.execute(
            update(Order).where(Order.id == dispute.orderId).values(status="REFUNDED", updatedAt=now())
        )
        push_timeline(db, dispute.orderId, "REFUNDED", f"Hoàn tiền theo {dispute.code}: {resolution}")
    elif decision == "SELLER_WINS":
        if escrow is not None and escrow.status == "HELD":
            released = db.execute(
                update(Escrow)
                .where(Escrow.id == escrow.id, Escrow.status == "HELD")
                .values(status="RELEASED", releasedAt=now())
            )
            if released.rowcount:
                platform_fee = min(order.platformFee, escrow.amount)
                if escrow.amount:
                    apply_wallet(
                        db,
                        order.sellerId,
                        "ORDER_INCOME",
                        escrow.amount,
                        order.code,
                        f"Tiền cọc đơn {order.code} (thắng tranh chấp)",
                    )
                if platform_fee:
                    apply_wallet(
                        db,
                        order.sellerId,
                        "PLATFORM_FEE",
                        -platform_fee,
                        order.code,
                        f"Phí sàn đơn {order.code}",
                    )
                db.execute(
                    update(Listing)
                    .where(Listing.id == order.listingId)
                    .values(status="SOLD_OUT", updatedAt=now())
                )
        db.execute(
            update(Order).where(Order.id == dispute.orderId).values(status="COMPLETED", updatedAt=now())
        )
        push_timeline(db, dispute.orderId, "COMPLETED", f"Tranh chấp {dispute.code}: xử thắng cho người bán")
    elif decision == "SPLIT":
        if escrow is not None and escrow.status == "HELD":
            db.execute(
                update(Escrow)
                .where(Escrow.id == escrow.id)
                .values(status="REFUNDED", releasedAt=now())
            )
            buyer_half = -(-escrow.amount // 2)  # Math.ceil
            seller_half = escrow.amount - buyer_half
            fee = min(seller_half, order.platformFee // 2)
            apply_wallet(
                db,
                dispute.buyerId,
                "REFUND",
                buyer_half,
                order.code,
                f"Hoàn 50% tranh chấp {dispute.code}",
            )
            if seller_half > 0:
                apply_wallet(
                    db,
                    order.sellerId,
                    "ORDER_INCOME",
                    seller_half,
                    order.code,
                    f"Nhận 50% tranh chấp {dispute.code}",
                )
            if fee:
                apply_wallet(
                    db,
                    order.sellerId,
                    "PLATFORM_FEE",
                    -fee,
                    order.code,
                    f"Phí sàn tranh chấp {dispute.code}",
                )
        db.execute(
            update(Order).where(Order.id == dispute.orderId).values(status="REFUNDED", updatedAt=now())
        )
        push_timeline(db, dispute.orderId, "REFUNDED", f"Chia đôi theo {dispute.code}: {resolution}")
    else:
        db.execute(
            update(Order).where(Order.id == dispute.orderId).values(status="SHIPPING", updatedAt=now())
        )
        push_timeline(db, dispute.orderId, "SHIPPING", f"Từ chối khiếu nại {dispute.code}: {resolution}")

    if decision in ("BUYER_WINS", "SPLIT"):
        db.execute(
            update(Listing)
            .where(Listing.id == order.listingId, Listing.status == "RESERVED")
            .values(status="HIDDEN", updatedAt=now())
        )

    db.add(
        AuditLog(
            adminId=admin.id,
            action="RESOLVE_DISPUTE",
            target=f"dispute:{dispute.code}",
            detail={"decision": decision, "resolution": resolution},
        )
    )

    buyer_messages = {
        "BUYER_WINS": f"Bạn thắng tranh chấp — đã hoàn {dispute.amount:,}đ về ví".replace(",", "."),
        "SELLER_WINS": "Người bán thắng tranh chấp — tiền cọc đã được giải ngân cho shop",
        "SPLIT": "Tranh chấp được chia đôi — bạn nhận lại 50% tiền cọc",
        "REJECT": "Khiếu nại của bạn đã bị từ chối",
    }
    notify(
        db,
        dispute.buyerId,
        "DISPUTE",
        f"Kết quả {dispute.code}",
        buyer_messages[decision],
        {"disputeId": dispute.id},
    )
    notify(
        db,
        dispute.sellerId,
        "DISPUTE",
        f"Kết quả {dispute.code}",
        resolution,
        {"disputeId": dispute.id},
    )
    db.commit()
    return {"message": "Đã xử lý tranh chấp"}
