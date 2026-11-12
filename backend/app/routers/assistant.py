"""Trợ lý tìm đồ — Xử lý ngôn ngữ tự nhiên (NLP) cục bộ."""
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..limits import MemoryLimiter
from ..models import Category, Listing, ListingImage
from ..serialize import to_dict
from ..services.assistant_search import local_search
from ..services.catalog import ListingFilters, listing_conditions

router = APIRouter()

assistant_limiter = MemoryLimiter(10, 60_000, "Too many requests, please try again later.")

def assistant_rate_limit(request: Request) -> None:
    assistant_limiter.check(request.client.host if request.client else "unknown")

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
    filters = local_search(payload.message)

    def search_listings(current_filters):
        return db.execute(
            select(Listing)
            .where(*listing_conditions(ListingFilters(**current_filters)))
            .order_by(Listing.createdAt.desc())
            .limit(8)
        ).scalars().all()

    # 1. Tìm kiếm chính xác (mọi điều kiện)
    listings = search_listings(filters)
    is_fallback = False
    display_q = filters.get("q")

    # 2. Nếu không có, thử nới lỏng điều kiện
    if not listings:
        is_fallback = True
        
        # Thử 1: Bỏ Condition + City, giữ Item + Price
        step1 = {k: v for k, v in filters.items() if k not in ("city", "condition")}
        listings = search_listings(step1)

        # Thử 2: Bỏ Price, giữ Item + City
        if not listings:
            step2 = {k: v for k, v in filters.items() if k not in ("minPrice", "maxPrice", "condition")}
            listings = search_listings(step2)
        
        # Thử 3: Chỉ giữ Price (để gợi ý các món khác cùng tầm giá)
        if not listings and (filters.get("minPrice") or filters.get("maxPrice")):
            step3 = {k: v for k, v in filters.items() if k in ("minPrice", "maxPrice")}
            listings = search_listings(step3)
            display_q = None  # Xóa hiển thị tên món vì món đó không tồn tại
        
        # Thử 4: Chỉ giữ City
        if not listings and filters.get("city"):
            step4 = {"city": filters["city"]}
            listings = search_listings(step4)
            display_q = None
        
        # Nếu tìm thấy ở bước fallback, cập nhật lại filters hiển thị
        if listings:
            filters = {k: v for k, v in filters.items() if k in ("q", "minPrice", "maxPrice")}

    # 3. Lấy ảnh và danh mục
    images: dict[int, ListingImage] = {}
    if listings:
        for image in db.execute(
            select(ListingImage)
            .where(ListingImage.listingId.in_([listing.id for listing in listings]))
            .order_by(ListingImage.sortOrder)
        ).scalars():
            images.setdefault(image.listingId, image)
            
    categories = {
        cat_id: {"id": cat_id, "name": name, "slug": slug}
        for cat_id, name, slug in db.execute(
            select(Category.id, Category.name, Category.slug).order_by(Category.id)
        ).all()
    }

    items = []
    for listing in listings:
        item = to_dict(listing)
        item["images"] = [to_dict(images[listing.id])] if listing.id in images else []
        item["category"] = categories.get(listing.categoryId)
        items.append(item)

    # 4. Tạo câu trả lời
    parts = []
    if display_q and display_q != "đồ cũ":
        parts.append(f"món **{display_q}**")
    if filters.get("maxPrice"):
        parts.append(f"dưới **{filters['maxPrice']:,}đ**".replace(",", "."))
    if filters.get("minPrice"):
        parts.append(f"trên **{filters['minPrice']:,}đ**".replace(",", "."))

    understood = ", ".join(parts) if parts else "đồ cũ"

    if items:
        if is_fallback:
            message = f"Dạ, em **không tìm thấy {understood}** trên sàn. Nhưng em gợi ý cho bạn **{len(items)} sản phẩm liên quan** đang bán:"
        else:
            message = f"Dạ, em hiểu bạn đang tìm {understood}. Em tìm thấy **{len(items)} kết quả** phù hợp nhất:"
    else:
        message = f"Dạ, em đã tìm {understood} nhưng hiện tại **chưa có ai đăng bán**. Bạn thử mở rộng ngân sách hoặc đổi từ khóa nhé!"

    return {
        "mode": "NLP",
        "filters": filters,
        "items": items,
        "message": message,
        "note": "Kết quả được lọc trực tiếp từ cơ sở dữ liệu.",
    }