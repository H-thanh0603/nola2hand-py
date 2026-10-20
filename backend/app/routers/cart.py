"""Giỏ hàng — port src/routes/cart.js."""
from typing import Literal

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import CurrentUser, current_user, verified_account
from ..errors import ApiError
from ..models import CartItem, Category, Listing, ListingImage, User
from ..quota import account_limit
from ..serialize import to_dict
from ..services.orders import create_single_order
from ..validators import phone_vn

router = APIRouter()


class CartIn(BaseModel):
    listingId: int


class CheckoutIn(BaseModel):
    listingIds: list[int] = Field(min_length=1, max_length=20)
    shipName: str
    shipPhone: str
    shipAddress: str
    note: str | None = None
    paymentMethod: Literal["MOMO_QR", "SAFEPAY_WALLET", "BANK_TRANSFER", "NAPAS", "COD"] = "MOMO_QR"

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


def _items_with_listing(db: Session, user_id: int) -> list[dict]:
    items = db.execute(
        select(CartItem).where(CartItem.userId == user_id).order_by(CartItem.createdAt.desc())
    ).scalars().all()
    if not items:
        return []

    listing_ids = [item.listingId for item in items]
    listings = {
        listing.id: listing
        for listing in db.execute(select(Listing).where(Listing.id.in_(listing_ids))).scalars()
    }
    first_images: dict[int, ListingImage] = {}
    for image in db.execute(
        select(ListingImage).where(ListingImage.listingId.in_(listing_ids)).order_by(ListingImage.sortOrder)
    ).scalars():
        first_images.setdefault(image.listingId, image)
    categories = {
        category.id: category
        for category in db.execute(
            select(Category).where(Category.id.in_({listing.categoryId for listing in listings.values()}))
        ).scalars()
    }
    sellers = {
        seller.id: seller
        for seller in db.execute(
            select(User).where(User.id.in_({listing.sellerId for listing in listings.values()}))
        ).scalars()
    }

    payload = []
    for item in items:
        row = to_dict(item)
        listing = listings.get(item.listingId)
        if listing is not None:
            listing_payload = to_dict(listing)
            image = first_images.get(listing.id)
            listing_payload["images"] = [to_dict(image)] if image is not None else []
            category = categories.get(listing.categoryId)
            listing_payload["category"] = (
                {"id": category.id, "name": category.name} if category else None
            )
            seller = sellers.get(listing.sellerId)
            listing_payload["seller"] = (
                {"id": seller.id, "fullName": seller.fullName} if seller else None
            )
            row["listing"] = listing_payload
        else:
            row["listing"] = None
        payload.append(row)
    return payload


def _count(db: Session, user_id: int) -> int:
    return db.execute(
        select(func.count()).select_from(CartItem).where(CartItem.userId == user_id)
    ).scalar_one()


@router.get("")
def my_cart(user: CurrentUser = Depends(current_user), db: Session = Depends(get_db)):
    items = _items_with_listing(db, user.id)
    total = sum(
        0 if not item["listing"] or item["listing"]["isFree"] else item["listing"]["price"]
        for item in items
    )
    return {"items": items, "total": total, "count": len(items)}


@router.post("", status_code=201)
def add_to_cart(
    payload: CartIn,
    user: CurrentUser = Depends(current_user),
    db: Session = Depends(get_db),
):
    listing = db.execute(select(Listing).where(Listing.id == payload.listingId)).scalar_one_or_none()
    if listing is None or listing.status != "ACTIVE":
        raise ApiError(404, "Sản phẩm không khả dụng")
    if listing.sellerId == user.id:
        raise ApiError(400, "Không thể thêm tin của chính mình vào giỏ")

    db.execute(
        insert(CartItem)
        .values(userId=user.id, listingId=payload.listingId)
        .on_conflict_do_nothing(index_elements=["userId", "listingId"])
    )
    db.commit()

    item = next(
        row for row in _items_with_listing(db, user.id) if row["listingId"] == payload.listingId
    )
    return {"item": item, "count": _count(db, user.id), "message": "Đã thêm vào giỏ hàng"}


@router.delete("/{listing_id}")
def remove_from_cart(
    listing_id: int,
    user: CurrentUser = Depends(current_user),
    db: Session = Depends(get_db),
):
    db.execute(
        delete(CartItem).where(CartItem.userId == user.id, CartItem.listingId == listing_id)
    )
    db.commit()
    return {"count": _count(db, user.id), "message": "Đã xoá khỏi giỏ hàng"}


@router.delete("")
def clear_cart(user: CurrentUser = Depends(current_user), db: Session = Depends(get_db)):
    db.execute(delete(CartItem).where(CartItem.userId == user.id))
    db.commit()
    return {"count": 0, "message": "Đã xoá toàn bộ giỏ hàng"}


@router.post("/checkout", status_code=201)
def checkout(
    payload: CheckoutIn,
    user: CurrentUser = Depends(verified_account),
    _quota: CurrentUser = Depends(account_limit("CHECKOUT", 10, 86_400_000)),
    db: Session = Depends(get_db),
):
    ship = {
        "shipName": payload.shipName,
        "shipPhone": payload.shipPhone,
        "shipAddress": payload.shipAddress,
        "note": payload.note,
        "paymentMethod": payload.paymentMethod,
    }

    orders = []
    errors = []
    for listing_id in payload.listingIds:
        try:
            order = create_single_order(db, user.id, listing_id=listing_id, ship=ship)
        except ApiError as exc:
            db.rollback()
            errors.append({"listingId": listing_id, "message": exc.message})
            continue

        db.execute(
            delete(CartItem).where(CartItem.userId == user.id, CartItem.listingId == listing_id)
        )
        db.commit()
        orders.append(to_dict(order))

    if not orders:
        return JSONResponse(status_code=400, content={"message": "Không tạo được đơn nào", "errors": errors})

    return {"orders": orders, "errors": errors, "message": f"Đã tạo {len(orders)} đơn hàng"}
