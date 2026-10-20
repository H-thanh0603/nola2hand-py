"""Trả hàng — port src/routes/returns.js."""
from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import CurrentUser, current_user, require_role
from ..errors import ApiError
from ..models import Listing, ListingImage, Order, ReturnRequest, User
from ..pagination import paged_result, paginate
from ..quota import account_limit
from ..serialize import to_dict
from ..services.evidence import assert_own_evidence
from ..services.returns import request_return, transition_return
from ..validators import http_url

router = APIRouter()

RETURN_STATUSES = (
    "REQUESTED",
    "APPROVED",
    "SHIPPED",
    "RECEIVED",
    "REFUNDED",
    "REJECTED",
    "CANCELLED",
)


class ReturnIn(BaseModel):
    reason: str
    evidences: list[str] = []

    @field_validator("reason")
    @classmethod
    def _reason(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 10:
            raise ValueError("String must contain at least 10 character(s)")
        if len(value) > 1000:
            raise ValueError("String must contain at most 1000 character(s)")
        return value

    @field_validator("evidences")
    @classmethod
    def _evidences(cls, value: list[str]) -> list[str]:
        if len(value) > 5:
            raise ValueError("Array must contain at most 5 element(s)")
        return [http_url(url, "Ảnh bằng chứng") for url in value]


class ReturnActionIn(BaseModel):
    action: Literal["APPROVE", "REJECT", "CANCEL", "SHIP", "RECEIVE", "REFUND", "COD_REFUND", "COD_CONFIRM"]
    note: str | None = None
    trackingCode: str | None = None
    codReference: str | None = None

    @field_validator("note")
    @classmethod
    def _note(cls, value: str | None) -> str | None:
        return _text(value, 3, 1000)

    @field_validator("trackingCode")
    @classmethod
    def _tracking(cls, value: str | None) -> str | None:
        return _text(value, 3, 150)

    @field_validator("codReference")
    @classmethod
    def _cod(cls, value: str | None) -> str | None:
        return _text(value, 3, 150)


def _text(value: str | None, minimum: int, maximum: int) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if len(value) < minimum:
        raise ValueError(f"String must contain at least {minimum} character(s)")
    if len(value) > maximum:
        raise ValueError(f"String must contain at most {maximum} character(s)")
    return value


def _serialize(db: Session, rows: list[ReturnRequest]) -> list[dict]:
    if not rows:
        return []
    order_ids = {row.orderId for row in rows}
    orders = {
        order.id: order
        for order in db.execute(select(Order).where(Order.id.in_(order_ids))).scalars()
    }
    listing_ids = {order.listingId for order in orders.values()}
    listings = {
        listing.id: listing
        for listing in db.execute(select(Listing).where(Listing.id.in_(listing_ids))).scalars()
    }
    first_images: dict[int, ListingImage] = {}
    for image in db.execute(
        select(ListingImage).where(ListingImage.listingId.in_(listing_ids)).order_by(ListingImage.sortOrder)
    ).scalars():
        first_images.setdefault(image.listingId, image)
    user_ids = {
        user_id
        for order in orders.values()
        for user_id in (order.buyerId, order.sellerId)
    }
    names = {
        user_id: full_name
        for user_id, full_name in db.execute(
            select(User.id, User.fullName).where(User.id.in_(user_ids))
        ).all()
    }

    payload = []
    for row in rows:
        item = to_dict(row)
        order = orders.get(row.orderId)
        if order is not None:
            order_payload = to_dict(order)
            listing = listings.get(order.listingId)
            if listing is not None:
                listing_payload = to_dict(listing)
                image = first_images.get(listing.id)
                listing_payload["images"] = [to_dict(image)] if image is not None else []
                order_payload["listing"] = listing_payload
            else:
                order_payload["listing"] = None
            order_payload["buyer"] = {"fullName": names.get(order.buyerId)}
            order_payload["seller"] = {"fullName": names.get(order.sellerId)}
            item["order"] = order_payload
        else:
            item["order"] = None
        payload.append(item)
    return payload


@router.post("/orders/{order_id}", status_code=201)
def create_return(
    order_id: int,
    payload: ReturnIn,
    user: CurrentUser = Depends(account_limit("RETURN_REQUEST", 5, 86_400_000)),
    db: Session = Depends(get_db),
):
    assert_own_evidence(payload.evidences, user.id)
    request = request_return(db, user.id, order_id, payload.model_dump())
    return to_dict(request)


def _list_returns(request: Request, db: Session, user_id: int | None, admin: bool) -> dict:
    page = paginate(dict(request.query_params))
    conditions = []
    if not admin:
        conditions.append(
            ReturnRequest.orderId.in_(
                select(Order.id).where((Order.buyerId == user_id) | (Order.sellerId == user_id))
            )
        )
    status = request.query_params.get("status")
    if status:
        if status not in RETURN_STATUSES:
            raise ApiError(
                400,
                "Dữ liệu không hợp lệ",
                details=[
                    {
                        "field": "status",
                        "message": f"Invalid enum value. Expected {' | '.join(RETURN_STATUSES)}",
                    }
                ],
            )
        conditions.append(ReturnRequest.status == status)

    rows = db.execute(
        select(ReturnRequest)
        .where(*conditions)
        .order_by(ReturnRequest.requestedAt.desc())
        .offset(page["skip"])
        .limit(page["limit"])
    ).scalars().all()
    total = db.execute(
        select(func.count()).select_from(ReturnRequest).where(*conditions)
    ).scalar_one()
    return paged_result(_serialize(db, list(rows)), total, page["page"], page["limit"])


@router.get("")
def my_returns(
    request: Request,
    user: CurrentUser = Depends(current_user),
    db: Session = Depends(get_db),
):
    return _list_returns(request, db, user.id, admin=False)


@router.get("/admin")
def all_returns(
    request: Request,
    user: CurrentUser = Depends(require_role("ADMIN_FINANCE")),
    db: Session = Depends(get_db),
):
    return _list_returns(request, db, user.id, admin=True)


@router.patch("/{return_id}")
def act_on_return(
    return_id: int,
    payload: ReturnActionIn,
    user: CurrentUser = Depends(account_limit("RETURN_ACTION", 30, 3_600_000)),
    db: Session = Depends(get_db),
):
    if payload.action in ("APPROVE", "REJECT", "RECEIVE", "REFUND") and not payload.note:
        raise ApiError(400, "Cần lý do hoặc ghi chú cho bước xử lý")
    updated = transition_return(db, user, return_id, payload.model_dump())
    return to_dict(updated)
