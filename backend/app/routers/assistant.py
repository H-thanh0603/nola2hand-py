"""Trợ lý tìm đồ — port src/routes/assistant.js."""
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..limits import MemoryLimiter
from ..models import Category, Listing, ListingImage
from ..serialize import to_dict
from ..services.ai import json_answer
from ..services.assistant_search import local_search
from ..services.catalog import ListingFilters, listing_conditions

router = APIRouter()

INSTRUCTIONS = (
    "Extract marketplace search filters: q (short product keywords), categoryId (only IDs supplied), "
    "minPrice/maxPrice (integer VND), city, condition (NEW,LIKE_NEW,USED_GOOD,USED_FAIR,FOR_PARTS), "
    "deliveryMethod (MEETUP,DELIVERY). JSON object of filters only. Do not invent prices or IDs."
)

# express-rate-limit mặc định: 10 lượt/phút/IP, thông báo tiếng Anh.
assistant_limiter = MemoryLimiter(10, 60_000, "Too many requests, please try again later.")


def assistant_rate_limit(request: Request) -> None:
    assistant_limiter.check(request.client.host if request.client else "unknown")


LOCAL_MESSAGE = "Chế độ tìm kiếm từ khóa; AI chưa cấu hình hoặc đang không khả dụng."
AI_MESSAGE = "AI chuyển nhu cầu thành bộ lọc; hãy kiểm tra kỹ tin và trao đổi với người bán."


class AssistantIn(BaseModel):
    message: str

    @field_validator("message")
    @classmethod
    def _message(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("String must contain at least 2 character(s)")
        if len(value) > 500:
            raise ValueError("String must contain at most 500 character(s)")
        return value


@router.post("", dependencies=[Depends(assistant_rate_limit)])
def assistant(payload: AssistantIn, db: Session = Depends(get_db)):
    categories = [
        {"id": category_id, "name": name, "slug": slug}
        for category_id, name, slug in db.execute(
            select(Category.id, Category.name, Category.slug).order_by(Category.id)
        ).all()
    ]

    filters = local_search(payload.message)
    mode = "LOCAL"
    try:
        answer = json_answer(INSTRUCTIONS, {"message": payload.message, "categories": categories})
        if answer:
            parsed = ListingFilters(**answer)
            parsed.check_range()
            if parsed.categoryId and parsed.categoryId not in {row["id"] for row in categories}:
                raise ValueError("Unknown category")
            selected = parsed.model_dump(exclude_none=True, exclude=("page", "limit", "sort"))
            if not selected:
                raise ValueError("Empty AI filters")
            filters = selected
            mode = "AI"
    except Exception:  # AI lỗi/không cấu hình → giữ bộ lọc từ khóa
        mode = "LOCAL"

    listings = db.execute(
        select(Listing)
        .where(*listing_conditions(ListingFilters(**filters)))
        .order_by(Listing.createdAt.desc())
        .limit(8)
    ).scalars().all()

    images: dict[int, ListingImage] = {}
    if listings:
        for image in db.execute(
            select(ListingImage)
            .where(ListingImage.listingId.in_([listing.id for listing in listings]))
            .order_by(ListingImage.sortOrder)
        ).scalars():
            images.setdefault(image.listingId, image)
    category_map = {row["id"]: row for row in categories}

    items = []
    for listing in listings:
        item = to_dict(listing)
        image = images.get(listing.id)
        item["images"] = [to_dict(image)] if image is not None else []
        item["category"] = category_map.get(listing.categoryId)
        items.append(item)

    return {
        "mode": mode,
        "filters": filters,
        "items": items,
        "message": (
            f"Tìm thấy {len(items)} tin đang bán phù hợp. Giá và tình trạng lấy trực tiếp từ tin đăng."
            if items
            else "Chưa tìm thấy tin phù hợp. Thử tên sản phẩm ngắn hơn hoặc điều chỉnh ngân sách."
        ),
        "note": LOCAL_MESSAGE if mode == "LOCAL" else AI_MESSAGE,
    }
