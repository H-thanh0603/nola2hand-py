"""Tin đăng — port src/routes/listings.js."""
import math
from datetime import timedelta
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import CurrentUser, bearer_token, current_user, require_role, verified_account
from ..errors import ApiError
from ..models import (
    AuditLog,
    Category,
    Favorite,
    FeeConfig,
    Listing,
    ListingImage,
    PriceHistory,
    PriceOffer,
    SellerProfile,
    User,
)
from ..pagination import paged_result, paginate
from ..quota import account_limit
from ..security import TokenError, decode_access_token
from ..serialize import to_dict
from ..services.catalog import ListingFilters, listing_conditions, validate_specifications
from ..services.saved_searches import notify_matching_searches
from ..utils import apply_wallet, notify, now, vnd
from ..validators import http_url

router = APIRouter()

OFFER_TTL = timedelta(hours=24)
EDITABLE_STATUSES = ("ACTIVE", "HIDDEN", "DRAFT", "PENDING_REVIEW", "REJECTED")
Condition = Literal["NEW", "LIKE_NEW", "USED_GOOD", "USED_FAIR", "FOR_PARTS"]


# ------------------------------------------------------------------ serialize


def serialize_listings(db: Session, listings: list[Listing], with_price_history: bool = False) -> list[dict]:
    """Ghép ảnh / danh mục / người bán / số lượt thích như `include` của Prisma."""
    if not listings:
        return []
    ids = [listing.id for listing in listings]

    images: dict[int, list[dict]] = {listing_id: [] for listing_id in ids}
    for image in db.execute(
        select(ListingImage).where(ListingImage.listingId.in_(ids)).order_by(ListingImage.sortOrder)
    ).scalars():
        images[image.listingId].append(to_dict(image))

    categories = {
        category.id: to_dict(category)
        for category in db.execute(
            select(Category).where(Category.id.in_({listing.categoryId for listing in listings}))
        ).scalars()
    }

    seller_ids = {listing.sellerId for listing in listings}
    sellers = {
        user.id: user for user in db.execute(select(User).where(User.id.in_(seller_ids))).scalars()
    }
    profiles = {
        profile.userId: profile
        for profile in db.execute(
            select(SellerProfile).where(SellerProfile.userId.in_(seller_ids))
        ).scalars()
    }
    favorites = dict(
        db.execute(
            select(Favorite.listingId, func.count())
            .where(Favorite.listingId.in_(ids))
            .group_by(Favorite.listingId)
        ).all()
    )

    history: dict[int, list[dict]] = {}
    if with_price_history:
        for row in db.execute(
            select(PriceHistory)
            .where(PriceHistory.listingId.in_(ids))
            .order_by(PriceHistory.createdAt.desc(), PriceHistory.id.desc())
        ).scalars():
            bucket = history.setdefault(row.listingId, [])
            if len(bucket) < 300:  # take: 300 tính riêng cho từng tin
                bucket.append(to_dict(row))
        for bucket in history.values():
            bucket.reverse()  # Node đảo lại thành cũ → mới

    items = []
    for listing in listings:
        item = to_dict(listing)
        item["images"] = images[listing.id]
        item["category"] = categories.get(listing.categoryId)
        seller = sellers.get(listing.sellerId)
        profile = profiles.get(listing.sellerId)
        item["seller"] = (
            {
                "id": seller.id,
                "fullName": seller.fullName,
                "avatarUrl": seller.avatarUrl,
                "isVerified": seller.isVerified,
                "emailVerifiedAt": seller.emailVerifiedAt,
                "idVerified": seller.idVerified,
                "sellerProfile": to_dict(profile) if profile else None,
            }
            if seller
            else None
        )
        item["_count"] = {"favorites": favorites.get(listing.id, 0)}
        if with_price_history:
            item["priceHistory"] = history.get(listing.id, [])
        items.append(item)
    return items


def serialize_listing(db: Session, listing: Listing) -> dict:
    return serialize_listings(db, [listing])[0]


def _listing_order(sort: str | None):
    if sort == "price_asc":
        return [Listing.price.asc()]
    if sort == "price_desc":
        return [Listing.price.desc()]
    if sort == "newest":
        return [Listing.createdAt.desc()]
    return [Listing.boostedUntil.desc(), Listing.createdAt.desc()]


def _active_page(request: Request) -> dict:
    return paginate(dict(request.query_params))


# ---------------------------------------------------------------- kiểu dữ liệu


class OfferIn(BaseModel):
    offeredPrice: int = Field(ge=1000, le=10_000_000_000)
    message: str | None = None
    shipMethod: Literal["NOLA_SHIP", "MEETUP"] = "NOLA_SHIP"

    @field_validator("message")
    @classmethod
    def _message(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if len(v) > 500:
            raise ValueError("String must contain at most 500 character(s)")
        return v


def _title(value: str) -> str:
    value = value.strip()
    if len(value) < 10:
        raise ValueError("Tiêu đề tối thiểu 10 ký tự")
    if len(value) > 150:
        raise ValueError("String must contain at most 150 character(s)")
    return value


def _description(value: str) -> str:
    value = value.strip()
    if len(value) < 20:
        raise ValueError("Mô tả tối thiểu 20 ký tự")
    if len(value) > 5000:
        raise ValueError("String must contain at most 5000 character(s)")
    return value


def _city(value: str) -> str:
    value = value.strip()
    if len(value) > 100:
        raise ValueError("String must contain at most 100 character(s)")
    return value


def _specifications(values: dict[str, str]) -> dict[str, str]:
    cleaned = {}
    for key, value in values.items():
        if not isinstance(value, str):
            raise ValueError("Expected string, received " + type(value).__name__)
        value = value.strip()
        if len(value) > 250:
            raise ValueError("String must contain at most 250 character(s)")
        cleaned[key] = value
    return cleaned


def _images(urls: list[str]) -> list[str]:
    if not urls:
        raise ValueError("Cần ít nhất 1 hình ảnh")
    if len(urls) > 10:
        raise ValueError("Array must contain at most 10 element(s)")
    return [http_url(url, "Ảnh") for url in urls]


class ListingIn(BaseModel):
    categoryId: int
    title: str
    description: str
    price: int = Field(ge=0, le=10_000_000_000)
    originalPrice: int | None = Field(None, ge=0, le=10_000_000_000)
    condition: Condition = "USED_GOOD"
    isFree: bool = False
    city: str = ""
    deliveryMethod: Literal["ANY", "MEETUP", "DELIVERY"] = "ANY"
    specifications: dict[str, str] = Field(default_factory=dict)
    images: list[str]

    @field_validator("title")
    @classmethod
    def _v_title(cls, v: str) -> str:
        return _title(v)

    @field_validator("description")
    @classmethod
    def _v_description(cls, v: str) -> str:
        return _description(v)

    @field_validator("price")
    @classmethod
    def _v_price(cls, v: int) -> int:
        if v > 10_000_000_000:
            raise ValueError("Giá tối đa 10 tỷ")
        return v

    @field_validator("city")
    @classmethod
    def _v_city(cls, v: str) -> str:
        return _city(v)

    @field_validator("specifications")
    @classmethod
    def _v_specs(cls, v: dict[str, str]) -> dict[str, str]:
        return _specifications(v)

    @field_validator("images")
    @classmethod
    def _v_images(cls, v: list[str]) -> list[str]:
        return _images(v)


class ListingPatch(BaseModel):
    categoryId: int | None = None
    title: str | None = None
    description: str | None = None
    price: int | None = Field(None, ge=0, le=10_000_000_000)
    originalPrice: int | None = Field(None, ge=0, le=10_000_000_000)
    condition: Condition | None = None
    isFree: bool | None = None
    city: str | None = None
    deliveryMethod: Literal["ANY", "MEETUP", "DELIVERY"] | None = None
    specifications: dict[str, str] | None = None
    images: list[str] | None = None

    @field_validator("title")
    @classmethod
    def _v_title(cls, v: str | None) -> str | None:
        return None if v is None else _title(v)

    @field_validator("description")
    @classmethod
    def _v_description(cls, v: str | None) -> str | None:
        return None if v is None else _description(v)

    @field_validator("city")
    @classmethod
    def _v_city(cls, v: str | None) -> str | None:
        return None if v is None else _city(v)

    @field_validator("specifications")
    @classmethod
    def _v_specs(cls, v: dict[str, str] | None) -> dict[str, str] | None:
        return None if v is None else _specifications(v)

    @field_validator("images")
    @classmethod
    def _v_images(cls, v: list[str] | None) -> list[str] | None:
        return None if v is None else _images(v)


class VisibilityIn(BaseModel):
    status: Literal["ACTIVE", "HIDDEN"]


class ModerateIn(BaseModel):
    action: Literal["APPROVE", "REJECT"]
    reason: str | None = None


# -------------------------------------------------------------------- endpoint


@router.get("/compare")
def compare_listings(ids: str = "", db: Session = Depends(get_db)):
    try:
        parsed = [int(part.strip()) for part in ids.split(",")]
    except ValueError:
        parsed = [0]
    if not parsed or len(parsed) > 3 or any(value <= 0 for value in parsed):
        raise ApiError(400, "Dữ liệu không hợp lệ", details=[{"field": "ids", "message": "Invalid input"}])
    if len(set(parsed)) != len(parsed):
        raise ApiError(400, "Không chọn trùng sản phẩm")

    found = db.execute(
        select(Listing).where(
            Listing.id.in_(parsed),
            Listing.status == "ACTIVE",
            Listing.sellerId.in_(select(User.id).where(User.status == "ACTIVE")),
        )
    ).scalars().all()
    serialized = {item["id"]: item for item in serialize_listings(db, found, with_price_history=True)}

    return {
        "items": [serialized[listing_id] for listing_id in parsed if listing_id in serialized],
        "unavailable": [listing_id for listing_id in parsed if listing_id not in serialized],
    }


@router.get("")
def list_listings(
    filters: Annotated[ListingFilters, Query()],
    db: Session = Depends(get_db),
):
    filters.check_range()
    page = paginate({"page": filters.page, "limit": filters.limit})
    conditions = listing_conditions(filters)

    listings = db.execute(
        select(Listing)
        .where(*conditions)
        .order_by(*_listing_order(filters.sort))
        .offset(page["skip"])
        .limit(page["limit"])
    ).scalars().all()
    total = db.execute(select(func.count()).select_from(Listing).where(*conditions)).scalar_one()
    return paged_result(serialize_listings(db, listings), total, page["page"], page["limit"])


@router.get("/recommended")
def recommended(request: Request, db: Session = Depends(get_db)):
    raw_limit = request.query_params.get("limit") or "8"
    try:
        limit = min(int(float(raw_limit)), 20)
    except ValueError:
        limit = 8

    category_ids: list[int] = []
    token = bearer_token(request)
    if token:
        try:
            payload = decode_access_token(token)
            if payload.get("purpose") != "access":
                raise TokenError("wrong_purpose")
            user = db.execute(
                select(User).where(User.id == int(payload["sub"]))
            ).scalar_one_or_none()
            if (
                user is None
                or user.status != "ACTIVE"
                or (payload.get("sessionVersion") or 0) != (user.sessionVersion or 0)
            ):
                raise TokenError("revoked")

            counts: dict[int, int] = {}
            for category_id in db.execute(
                select(Listing.categoryId)
                .join(Favorite, Favorite.listingId == Listing.id)
                .where(Favorite.userId == user.id)
                .limit(20)
            ).scalars():
                counts[category_id] = counts.get(category_id, 0) + 1
            category_ids = [
                category_id
                for category_id, _ in sorted(counts.items(), key=lambda item: -item[1])[:3]
            ]
        except (TokenError, ValueError):
            category_ids = []  # token hỏng thì bỏ qua, vẫn trả tin xem nhiều

    conditions = [Listing.status == "ACTIVE"]
    if category_ids:
        conditions.append(Listing.categoryId.in_(category_ids))

    listings = db.execute(
        select(Listing)
        .where(*conditions)
        .order_by(Listing.boostedUntil.desc(), Listing.views.desc())
        .limit(limit)
    ).scalars().all()
    return {
        "items": serialize_listings(db, listings),
        "basedOn": "favorites" if category_ids else "popular",
    }


@router.get("/me/favorites")
def my_favorites(
    request: Request,
    user: CurrentUser = Depends(current_user),
    db: Session = Depends(get_db),
):
    page = _active_page(request)
    favorites = db.execute(
        select(Favorite)
        .where(Favorite.userId == user.id)
        .order_by(Favorite.createdAt.desc())
        .offset(page["skip"])
        .limit(page["limit"])
    ).scalars().all()
    total = db.execute(
        select(func.count()).select_from(Favorite).where(Favorite.userId == user.id)
    ).scalar_one()

    listings = {
        listing.id: listing
        for listing in db.execute(
            select(Listing).where(Listing.id.in_({favorite.listingId for favorite in favorites}))
        ).scalars()
    } if favorites else {}
    serialized = {
        item["id"]: item for item in serialize_listings(db, list(listings.values()))
    }

    data = []
    for favorite in favorites:
        item = to_dict(favorite)
        item["listing"] = serialized.get(favorite.listingId)
        data.append(item)
    return paged_result(data, total, page["page"], page["limit"])


@router.get("/admin/pending", dependencies=[Depends(require_role("ADMIN_CONTENT"))])
def pending_listings(request: Request, db: Session = Depends(get_db)):
    page = _active_page(request)
    query = dict(request.query_params)

    conditions = [Listing.status == "PENDING_REVIEW"]
    if query.get("q"):
        like = f"%{query['q']}%"
        conditions.append(
            Listing.title.ilike(like)
            | Listing.sellerId.in_(select(User.id).where(User.fullName.ilike(like)))
        )

    listings = db.execute(
        select(Listing)
        .where(*conditions)
        .order_by(Listing.createdAt.asc())
        .offset(page["skip"])
        .limit(page["limit"])
    ).scalars().all()
    total = db.execute(select(func.count()).select_from(Listing).where(*conditions)).scalar_one()
    return paged_result(serialize_listings(db, listings), total, page["page"], page["limit"])


@router.patch("/admin/{listing_id}/moderate", dependencies=[Depends(require_role("ADMIN_CONTENT"))])
def moderate_listing(
    listing_id: int,
    payload: ModerateIn,
    admin: CurrentUser = Depends(current_user),
    db: Session = Depends(get_db),
):
    listing = db.execute(select(Listing).where(Listing.id == listing_id)).scalar_one_or_none()
    if listing is None:
        raise ApiError(404, "Không tìm thấy tin đăng")

    reason = payload.reason
    values: dict[str, Any] = (
        {"status": "ACTIVE", "rejectReason": None}
        if payload.action == "APPROVE"
        else {"status": "REJECTED", "rejectReason": reason or "Vi phạm quy định đăng tin"}
    )
    values["updatedAt"] = now()

    changed = db.execute(
        update(Listing)
        .where(Listing.id == listing.id, Listing.status == "PENDING_REVIEW")
        .values(**values)
    )
    if changed.rowcount == 0:
        raise ApiError(409, "Chỉ duyệt tin đang chờ kiểm duyệt")

    db.add(
        AuditLog(
            adminId=admin.id,
            action="MODERATE_LISTING",
            target=f"listing:{listing.id}",
            detail={"action": payload.action, "reason": reason or ""},
        )
    )

    db.flush()  # để notify_matching_searches thấy trạng thái ACTIVE mới
    if payload.action == "APPROVE":
        notify_matching_searches(db, listing.id)

    approved = payload.action == "APPROVE"
    notify(
        db,
        listing.sellerId,
        "SYSTEM",
        "Tin đăng đã được duyệt" if approved else "Tin đăng bị từ chối",
        f'Tin "{listing.title}" '
        + ("đã được duyệt và hiển thị." if approved else f"bị từ chối: {reason or ''}"),
    )
    db.commit()

    updated = db.execute(select(Listing).where(Listing.id == listing.id)).scalar_one()
    return to_dict(updated)


@router.post("/{listing_id}/offers", status_code=201)
def create_offer(
    listing_id: int,
    payload: OfferIn,
    user: CurrentUser = Depends(verified_account),
    _quota: CurrentUser = Depends(account_limit("CREATE_OFFER", 20, 3_600_000)),
    db: Session = Depends(get_db),
):
    listing = db.execute(select(Listing).where(Listing.id == listing_id)).scalar_one_or_none()
    if listing is None or listing.status != "ACTIVE":
        raise ApiError(404, "Tin đăng không khả dụng")
    if listing.sellerId == user.id:
        raise ApiError(400, "Không thể trả giá tin của chính mình")
    if payload.offeredPrice >= listing.price:
        raise ApiError(400, "Giá đề xuất phải thấp hơn giá niêm yết")

    offer = PriceOffer(
        listingId=listing.id,
        buyerId=user.id,
        offeredPrice=payload.offeredPrice,
        message=payload.message,
        shipMethod=payload.shipMethod,
        expiresAt=now() + OFFER_TTL,
    )
    db.add(offer)
    db.flush()

    buyer = db.execute(select(User).where(User.id == user.id)).scalar_one()
    notify(
        db,
        listing.sellerId,
        "OFFER",
        "Có yêu cầu trả giá mới",
        f'{buyer.fullName} trả giá {vnd(payload.offeredPrice)}đ cho "{listing.title}"',
        {"offerId": offer.id},
    )
    db.commit()

    offer_payload = to_dict(offer)
    offer_payload["listing"] = {"title": listing.title}
    offer_payload["buyer"] = {"fullName": buyer.fullName}
    return {"message": "Đã gửi yêu cầu, hiệu lực 24 giờ", "offer": offer_payload}


@router.get("/{listing_id}/related")
def related_listings(listing_id: int, request: Request, db: Session = Depends(get_db)):
    raw_limit = request.query_params.get("limit") or "8"
    try:
        limit = min(int(float(raw_limit)), 20)
    except ValueError:
        limit = 8

    current = db.execute(select(Listing).where(Listing.id == listing_id)).scalar_one_or_none()
    if current is None:
        raise ApiError(404, "Tin đăng không tồn tại")

    low = math.floor(current.price * 0.5)
    high = math.ceil(current.price * 1.5) or 1_000_000_000
    listings = db.execute(
        select(Listing)
        .where(
            Listing.status == "ACTIVE",
            Listing.id != current.id,
            Listing.categoryId == current.categoryId,
            Listing.price >= (0 if current.isFree else low),
            Listing.price <= (0 if current.isFree else high),
        )
        .order_by(Listing.views.desc())
        .limit(limit)
    ).scalars().all()
    return {"items": serialize_listings(db, listings)}


@router.get("/{listing_id}")
def listing_detail(listing_id: int, db: Session = Depends(get_db)):
    listing = db.execute(select(Listing).where(Listing.id == listing_id)).scalar_one_or_none()
    if listing is None or listing.status != "ACTIVE":
        raise ApiError(404, "Tin đăng không tồn tại")

    payload = serialize_listing(db, listing)
    db.execute(
        update(Listing)
        .where(Listing.id == listing.id)
        .values(views=Listing.views + 1, updatedAt=now())
    )
    db.commit()
    payload["views"] = listing.views + 1
    return payload


@router.post("", status_code=201)
def create_listing(
    payload: ListingIn,
    user: CurrentUser = Depends(require_role("SELLER")),
    _verified: CurrentUser = Depends(verified_account),
    _quota: CurrentUser = Depends(account_limit("CREATE_LISTING", 10, 86_400_000)),
    db: Session = Depends(get_db),
):
    data = payload.model_dump()
    images = data.pop("images")
    if data["isFree"]:
        data["price"] = 0

    category = db.execute(select(Category).where(Category.id == data["categoryId"])).scalar_one_or_none()
    if category is None:
        raise ApiError(400, "Danh mục không tồn tại")
    validate_specifications(category.slug, data["specifications"])

    listing = Listing(**data, sellerId=user.id, status="PENDING_REVIEW", updatedAt=now())
    db.add(listing)
    db.flush()
    db.add_all(
        [ListingImage(listingId=listing.id, url=url, sortOrder=index) for index, url in enumerate(images)]
    )
    db.add(PriceHistory(listingId=listing.id, price=data["price"]))
    db.commit()

    return {
        "message": "Đăng tin thành công, đang chờ kiểm duyệt",
        "listing": serialize_listing(db, listing),
    }


@router.patch("/{listing_id}", dependencies=[Depends(require_role("SELLER"))])
def update_listing(
    listing_id: int,
    payload: ListingPatch,
    user: CurrentUser = Depends(current_user),
    db: Session = Depends(get_db),
):
    listing = db.execute(select(Listing).where(Listing.id == listing_id)).scalar_one_or_none()
    if listing is None or listing.sellerId != user.id:
        raise ApiError(404, "Không tìm thấy tin đăng")
    original_price = listing.price  # update() bên dưới đồng bộ luôn object trong session

    data = payload.model_dump(exclude_unset=True)
    images = data.pop("images", None)
    if data.get("isFree"):
        data["price"] = 0

    category_id = data.get("categoryId") or listing.categoryId
    category = db.execute(select(Category).where(Category.id == category_id)).scalar_one_or_none()
    if category is None:
        raise ApiError(400, "Danh mục không tồn tại")

    category_changed = data.get("categoryId") is not None and data["categoryId"] != listing.categoryId
    specs = data.get("specifications")
    if specs is None:
        specs = {} if category_changed else listing.specifications
    validate_specifications(category.slug, specs)
    if category_changed and "specifications" not in payload.model_fields_set:
        data["specifications"] = {}

    changed = db.execute(
        update(Listing)
        .where(
            Listing.id == listing.id,
            Listing.sellerId == user.id,
            Listing.status.in_(EDITABLE_STATUSES),
            Listing.updatedAt == listing.updatedAt,  # chống ghi đè khi tin vừa đổi
        )
        .values(**data, status="PENDING_REVIEW", updatedAt=now())
    )
    if changed.rowcount == 0:
        raise ApiError(409, "Tin đang được giữ/bán hết hoặc vừa thay đổi, không thể sửa")

    if "price" in data and data["price"] != original_price:
        db.add(PriceHistory(listingId=listing.id, price=data["price"]))
    if images is not None:
        db.execute(ListingImage.__table__.delete().where(ListingImage.listingId == listing.id))
        db.add_all(
            [ListingImage(listingId=listing.id, url=url, sortOrder=index) for index, url in enumerate(images)]
        )
    db.commit()

    updated = db.execute(select(Listing).where(Listing.id == listing.id)).scalar_one()
    return serialize_listing(db, updated)


@router.patch("/{listing_id}/visibility", dependencies=[Depends(require_role("SELLER"))])
def set_visibility(
    listing_id: int,
    payload: VisibilityIn,
    user: CurrentUser = Depends(current_user),
    db: Session = Depends(get_db),
):
    listing = db.execute(select(Listing).where(Listing.id == listing_id)).scalar_one_or_none()
    if listing is None or listing.sellerId != user.id:
        raise ApiError(404, "Không tìm thấy tin đăng")
    if listing.status not in ("ACTIVE", "HIDDEN"):
        raise ApiError(400, "Chỉ có thể ẩn hoặc hiện tin đã được duyệt")

    changed = db.execute(
        update(Listing)
        .where(
            Listing.id == listing.id,
            Listing.sellerId == user.id,
            Listing.status.in_(("ACTIVE", "HIDDEN")),
        )
        .values(status=payload.status, updatedAt=now())
    )
    if changed.rowcount == 0:
        raise ApiError(409, "Tin đang được giữ hoặc đã đổi trạng thái")
    db.commit()
    return {"id": listing.id, "status": payload.status}


@router.post("/{listing_id}/boost", dependencies=[Depends(require_role("SELLER"))])
def boost_listing(
    listing_id: int,
    user: CurrentUser = Depends(current_user),
    db: Session = Depends(get_db),
):
    listing = db.execute(select(Listing).where(Listing.id == listing_id)).scalar_one_or_none()
    if listing is None or listing.sellerId != user.id:
        raise ApiError(404, "Không tìm thấy tin đăng")

    fee_config = db.execute(
        select(FeeConfig).where(
            FeeConfig.kind == "PLATFORM_TXN",
            FeeConfig.name == "Phí đẩy tin",
            FeeConfig.isActive.is_(True),
        )
    ).scalars().first()
    fee = fee_config.amount if fee_config is not None and fee_config.amount is not None else 10000

    apply_wallet(db, user.id, "PLATFORM_FEE", -fee, f"BOOST-{listing.id}", "Phí đẩy tin nổi bật 24h")
    db.execute(
        update(Listing)
        .where(Listing.id == listing.id)
        .values(boostedUntil=now() + timedelta(hours=24), updatedAt=now())
    )
    db.commit()
    return {"message": f"Đã đẩy tin 24h (phí {vnd(fee)}đ)"}


@router.delete("/{listing_id}", dependencies=[Depends(require_role("SELLER"))])
def delete_listing(
    listing_id: int,
    user: CurrentUser = Depends(current_user),
    db: Session = Depends(get_db),
):
    listing = db.execute(select(Listing).where(Listing.id == listing_id)).scalar_one_or_none()
    if listing is None or listing.sellerId != user.id:
        raise ApiError(404, "Không tìm thấy tin đăng")

    removed = db.execute(
        update(Listing)
        .where(
            Listing.id == listing.id,
            Listing.sellerId == user.id,
            Listing.status.in_(EDITABLE_STATUSES),
        )
        .values(status="DELETED", updatedAt=now())
    )
    if removed.rowcount == 0:
        raise ApiError(409, "Không thể xóa tin đang được giữ hoặc đã bán")
    db.commit()
    return {"message": "Đã xoá tin đăng"}


@router.post("/{listing_id}/favorite")
def toggle_favorite(
    listing_id: int,
    user: CurrentUser = Depends(current_user),
    db: Session = Depends(get_db),
):
    favorite = db.execute(
        select(Favorite).where(Favorite.userId == user.id, Favorite.listingId == listing_id)
    ).scalar_one_or_none()
    if favorite is not None:
        db.delete(favorite)
        db.commit()
        return {"favorited": False}

    db.add(Favorite(userId=user.id, listingId=listing_id))
    db.commit()
    return {"favorited": True}


@router.get("/{listing_id}/price-history")
def price_history(listing_id: int, db: Session = Depends(get_db)):
    listing = db.execute(
        select(Listing).where(Listing.id == listing_id, Listing.status == "ACTIVE")
    ).scalar_one_or_none()
    if listing is None:
        raise ApiError(404, "Tin không khả dụng")

    rows = db.execute(
        select(PriceHistory)
        .where(PriceHistory.listingId == listing.id)
        .order_by(PriceHistory.createdAt.desc(), PriceHistory.id.desc())
        .limit(300)
    ).scalars().all()
    return [to_dict(row) for row in reversed(rows)]
