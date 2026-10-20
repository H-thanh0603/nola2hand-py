"""Danh mục, bộ lọc tin đăng, thông số sản phẩm — port src/services/catalog.js."""
import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import or_, select

from ..errors import ApiError
from ..models import Listing, User


class ListingFilters(BaseModel):
    """filterSchema của zod; FastAPI ép kiểu chuỗi query sang số giống z.coerce."""

    model_config = ConfigDict(str_strip_whitespace=True)

    q: str | None = Field(None, max_length=150)
    categoryId: int | None = Field(None, gt=0)
    condition: Literal["NEW", "LIKE_NEW", "USED_GOOD", "USED_FAIR", "FOR_PARTS"] | None = None
    minPrice: int | None = Field(None, ge=0, le=2_000_000_000)
    maxPrice: int | None = Field(None, ge=0, le=2_000_000_000)
    city: str | None = Field(None, max_length=100)
    deliveryMethod: Literal["MEETUP", "DELIVERY"] | None = None
    verified: Literal["true", "false"] | None = None
    isFree: Literal["true", "false"] | None = None
    sort: Literal["price_asc", "price_desc", "newest"] | None = None
    page: int | None = Field(None, gt=0)
    limit: int | None = Field(None, ge=1, le=100)

    def check_range(self) -> None:
        if self.minPrice is not None and self.maxPrice is not None and self.minPrice > self.maxPrice:
            raise ApiError(
                400,
                "Dữ liệu không hợp lệ",
                details=[{"field": "maxPrice", "message": "Khoảng giá không hợp lệ"}],
            )


def listing_conditions(filters: ListingFilters) -> list:
    """Các điều kiện WHERE tương ứng listingWhere() của bản Node."""
    conditions = [
        Listing.status == "ACTIVE",
        Listing.sellerId.in_(select(User.id).where(User.status == "ACTIVE")),
    ]
    if filters.q:
        like = f"%{filters.q}%"
        conditions.append(or_(Listing.title.ilike(like), Listing.description.ilike(like)))
    if filters.categoryId:
        conditions.append(Listing.categoryId == filters.categoryId)
    if filters.condition:
        conditions.append(Listing.condition == filters.condition)
    if filters.minPrice is not None:
        conditions.append(Listing.price >= filters.minPrice)
    if filters.maxPrice is not None:
        conditions.append(Listing.price <= filters.maxPrice)
    if filters.city:
        conditions.append(Listing.city.ilike(f"%{filters.city}%"))
    if filters.deliveryMethod:
        conditions.append(Listing.deliveryMethod.in_([filters.deliveryMethod, "ANY"]))
    if filters.verified == "true":
        conditions.append(Listing.sellerId.in_(select(User.id).where(User.idVerified.is_(True))))
    if filters.isFree == "true":
        conditions.append(Listing.isFree.is_(True))
    return conditions


SPECIFICATION_FIELDS = {
    "dien-tu-cu": {
        "brand": "Thương hiệu",
        "model": "Model",
        "batteryHealth": "Sức khỏe pin (%)",
        "repairs": "Lịch sử sửa chữa",
        "warranty": "Bảo hành còn lại",
    },
    "noi-that": {
        "width": "Rộng (cm)",
        "depth": "Sâu (cm)",
        "height": "Cao (cm)",
        "material": "Chất liệu",
        "defects": "Vết xước / lỗi",
    },
    "do-gia-dung": {
        "brand": "Thương hiệu",
        "power": "Công suất (W)",
        "warranty": "Bảo hành còn lại",
        "defects": "Lỗi / hao mòn",
    },
}

NUMERIC_SPECS = {"batteryHealth", "width", "depth", "height", "power"}


def validate_specifications(slug: str, values: dict | None) -> None:
    fields = SPECIFICATION_FIELDS.get(slug, {})
    for key, value in (values or {}).items():
        if key not in fields or not isinstance(value, str) or len(value) > 250:
            raise ApiError(400, "Thông số sản phẩm không hợp lệ")
        if key in NUMERIC_SPECS and value:
            try:
                number = float(value)
                invalid = not math.isfinite(number) or number < 0 or (key == "batteryHealth" and number > 100)
            except ValueError:
                invalid = True
            if invalid:
                raise ApiError(400, "Thông số số học không hợp lệ")
