"""Users: hồ sơ cá nhân, sổ địa chỉ, lên người bán, trang cá nhân — port src/routes/users.js."""
from datetime import datetime, timezone
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, field_validator
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import CurrentUser, current_user
from ..errors import ApiError
from ..models import Address, Listing, Review, Role, SellerProfile, User, UserRole
from ..pagination import paged_result, paginate
from ..serialize import to_dict
from ..utils import now
from ..validators import phone_vn

router = APIRouter()

# Prisma không trả các cột này ra JSON (src/routes/users.js:19).
SECRET_FIELDS = (
    "passwordHash",
    "passwordResetTokenHash",
    "passwordResetExpiresAt",
    "emailVerificationTokenHash",
    "emailVerificationExpiresAt",
)


def _safe_user(row: User) -> dict:
    return to_dict(row, exclude=SECRET_FIELDS)


def _avatar_url(value: str) -> str:
    value = value.strip()
    if value == "":
        return value
    parsed = urlparse(value)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError("Ảnh đại diện chưa đúng")
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Chỉ nhận URL HTTP/HTTPS")
    return value


def _js_date(value: str) -> datetime:
    """new Date(value) của JS nhưng chặt hơn: chỉ nhận ISO 8601."""
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ApiError(400, "Ngày sinh không hợp lệ") from exc
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


class ProfileIn(BaseModel):
    fullName: str | None = None
    phone: str | None = None
    avatarUrl: str | None = None
    dateOfBirth: str | None = None
    gender: str | None = None
    bio: str | None = None

    @field_validator("fullName")
    @classmethod
    def _full_name(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if len(v) < 2:
            raise ValueError("String must contain at least 2 character(s)")
        if len(v) > 100:
            raise ValueError("String must contain at most 100 character(s)")
        return v

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str | None) -> str | None:
        return None if v is None else phone_vn(v)

    @field_validator("avatarUrl")
    @classmethod
    def _avatar(cls, v: str | None) -> str | None:
        return None if v is None else _avatar_url(v)

    @field_validator("bio")
    @classmethod
    def _bio(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if len(v) > 500:
            raise ValueError("String must contain at most 500 character(s)")
        return v


class BecomeSellerIn(BaseModel):
    shopName: str
    phone: str | None = None
    city: str | None = None
    street: str | None = None

    @field_validator("shopName")
    @classmethod
    def _shop_name(cls, v: str) -> str:
        v = v.strip()
        if not 2 <= len(v) <= 100:
            raise ValueError("String must contain at least 2 character(s)" if len(v) < 2 else "String must contain at most 100 character(s)")
        return v

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str | None) -> str | None:
        return None if v is None else phone_vn(v)

    @field_validator("city")
    @classmethod
    def _city(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if not 1 <= len(v) <= 100:
            raise ValueError("String must contain at least 1 character(s)" if not v else "String must contain at most 100 character(s)")
        return v

    @field_validator("street")
    @classmethod
    def _street(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if not 1 <= len(v) <= 255:
            raise ValueError("String must contain at least 1 character(s)" if not v else "String must contain at most 255 character(s)")
        return v


class AddressIn(BaseModel):
    label: str
    receiver: str
    phone: str
    street: str
    ward: str | None = None
    district: str | None = None
    city: str
    isDefault: bool | None = None

    @field_validator("label", "receiver", "street", "city")
    @classmethod
    def _required_text(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("String must contain at least 1 character(s)")
        return v

    @field_validator("label")
    @classmethod
    def _label_length(cls, v: str) -> str:
        if len(v) > 50:
            raise ValueError("String must contain at most 50 character(s)")
        return v

    @field_validator("receiver")
    @classmethod
    def _receiver_length(cls, v: str) -> str:
        if len(v) > 100:
            raise ValueError("String must contain at most 100 character(s)")
        return v

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str) -> str:
        return phone_vn(v)

    @field_validator("ward", "district")
    @classmethod
    def _optional_text(cls, v: str | None) -> str | None:
        return None if v is None else v.strip()


@router.get("/me/profile")
def my_profile(user: CurrentUser = Depends(current_user), db: Session = Depends(get_db)):
    row = db.execute(select(User).where(User.id == user.id)).scalar_one()
    roles = db.execute(
        select(Role.name).join(UserRole, UserRole.roleId == Role.id).where(UserRole.userId == user.id)
    ).scalars().all()
    profile = db.execute(select(SellerProfile).where(SellerProfile.userId == user.id)).scalar_one_or_none()
    addresses = db.execute(
        select(Address).where(Address.userId == user.id).order_by(Address.id)
    ).scalars().all()

    payload = _safe_user(row)
    payload["roles"] = list(roles)
    payload["sellerProfile"] = to_dict(profile) if profile else None
    payload["addresses"] = [to_dict(a) for a in addresses]
    return payload


@router.patch("/me")
def update_me(
    payload: ProfileIn,
    user: CurrentUser = Depends(current_user),
    db: Session = Depends(get_db),
):
    row = db.execute(select(User).where(User.id == user.id)).scalar_one()
    changes = payload.model_dump(exclude_unset=True)
    if changes.get("dateOfBirth"):
        changes["dateOfBirth"] = _js_date(changes["dateOfBirth"])

    for field, value in changes.items():
        setattr(row, field, value)
    row.updatedAt = now()
    db.commit()
    return _safe_user(row)


@router.post("/me/become-seller", status_code=201)
def become_seller(
    payload: BecomeSellerIn,
    user: CurrentUser = Depends(current_user),
    db: Session = Depends(get_db),
):
    if "SELLER" in user.roles:
        raise ApiError(400, "Bạn đã là người bán")

    seller_role_id = db.execute(select(Role.id).where(Role.name == "SELLER")).scalar_one_or_none()
    me = db.execute(select(User).where(User.id == user.id)).scalar_one()

    if seller_role_id is not None:
        db.add(UserRole(userId=user.id, roleId=seller_role_id))
    profile = SellerProfile(userId=user.id, shopName=payload.shopName)
    db.add(profile)

    if payload.phone:
        me.phone = payload.phone
        me.updatedAt = now()
    if payload.city and payload.street:
        count = db.execute(
            select(func.count()).select_from(Address).where(Address.userId == user.id)
        ).scalar_one()
        db.add(
            Address(
                userId=user.id,
                label="Lấy hàng",
                receiver=me.fullName,
                phone=payload.phone or me.phone or "",
                street=payload.street,
                city=payload.city,
                isDefault=count == 0,
            )
        )

    db.commit()
    return {"message": "Mở kênh người bán thành công", "profile": to_dict(profile)}


@router.get("/me/addresses")
def list_addresses(user: CurrentUser = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.execute(
        select(Address).where(Address.userId == user.id).order_by(Address.isDefault.desc())
    ).scalars().all()
    return [to_dict(row) for row in rows]


@router.post("/me/addresses", status_code=201)
def create_address(
    payload: AddressIn,
    user: CurrentUser = Depends(current_user),
    db: Session = Depends(get_db),
):
    if payload.isDefault:
        db.execute(update(Address).where(Address.userId == user.id).values(isDefault=False))
    address = Address(userId=user.id, **payload.model_dump(exclude_none=True))
    db.add(address)
    db.commit()
    return to_dict(address)


@router.delete("/me/addresses/{address_id}")
def delete_address(
    address_id: int,
    user: CurrentUser = Depends(current_user),
    db: Session = Depends(get_db),
):
    address = db.execute(
        select(Address).where(Address.id == address_id, Address.userId == user.id)
    ).scalar_one_or_none()
    if address is None:
        raise ApiError(404, "Không tìm thấy địa chỉ")
    db.delete(address)
    db.commit()
    return {"message": "Đã xoá địa chỉ"}


@router.get("/{user_id}")
def public_profile(user_id: int, request: Request, db: Session = Depends(get_db)):
    row = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    if row is None:
        raise ApiError(404, "Không tìm thấy người dùng")

    profile = db.execute(select(SellerProfile).where(SellerProfile.userId == user_id)).scalar_one_or_none()
    listings = db.execute(
        select(func.count()).select_from(Listing).where(Listing.sellerId == user_id)
    ).scalar_one()

    page = paginate(dict(request.query_params), default_limit=5)
    reviews = db.execute(
        select(Review)
        .where(Review.revieweeId == user_id)
        .order_by(Review.createdAt.desc())
        .offset(page["skip"])
        .limit(page["limit"])
    ).scalars().all()
    total = db.execute(
        select(func.count()).select_from(Review).where(Review.revieweeId == user_id)
    ).scalar_one()

    reviewer_ids = {review.reviewerId for review in reviews}
    reviewers = {
        reviewer.id: reviewer
        for reviewer in db.execute(select(User).where(User.id.in_(reviewer_ids))).scalars()
    } if reviewer_ids else {}

    items = []
    for review in reviews:
        item = to_dict(review)
        reviewer = reviewers.get(review.reviewerId)
        item["reviewer"] = (
            {"id": reviewer.id, "fullName": reviewer.fullName, "avatarUrl": reviewer.avatarUrl}
            if reviewer
            else None
        )
        items.append(item)

    return {
        "user": {
            "id": row.id,
            "fullName": row.fullName,
            "avatarUrl": row.avatarUrl,
            "isVerified": row.isVerified,
            "createdAt": row.createdAt,
            "sellerProfile": to_dict(profile) if profile else None,
            "_count": {"listings": listings},
        },
        **paged_result(items, total, page["page"], page["limit"]),
    }
