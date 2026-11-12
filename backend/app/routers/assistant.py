"""Trợ lý tìm đồ — Fuzzy Search & Ranking."""
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..limits import MemoryLimiter
from ..models import Category, Listing, ListingImage
from ..serialize import to_dict
from ..services.assistant_search import local_search
from ..services.search_engine import smart_match

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
    query_text = filters.get("q", "")

    # Lấy tất cả tin ACTIVE
    all_listings = db.execute(
        select(Listing).where(Listing.status == "ACTIVE").order_by(Listing.createdAt.desc()).limit(500)
    ).scalars().all()

    def get_top_matches(use_filters=True):
        scored = []
        for listing in all_listings:
            if use_filters:
                if filters.get("minPrice") and listing.price < filters["minPrice"]: continue
                if filters.get("maxPrice") and listing.price > filters["maxPrice"]: continue
                if filters.get("city") and filters["city"].lower() not in (listing.city or "").lower(): continue

            score = smart_match(query_text, listing.title, listing.description or "")
            
            # Chỉ lấy những tin có điểm >= 40
            if score >= 40:
                scored.append({"listing": listing, "score": score})
        
        scored.sort(key=lambda x: x["score"], reverse=True)
        return [item["listing"] for item in scored[:8]]

    # 1. Tìm kiếm chính xác
    top_listings = get_top_matches(use_filters=True)
    is_fallback = False

    # 2. Nếu không tìm thấy, thử bỏ bộ lọc Giá / Khu vực
    if not top_listings and query_text:
        is_fallback = True
        top_listings = get_top_matches(use_filters=False)
        filters.pop("minPrice", None)
        filters.pop("maxPrice", None)
        filters.pop("city", None)

    # 3. Lấy ảnh và danh mục
    images: dict[int, ListingImage] = {}
    if top_listings:
        for image in db.execute(
            select(ListingImage).where(ListingImage.listingId.in_([l.id for l in top_listings])).order_by(ListingImage.sortOrder)
        ).scalars():
            images.setdefault(image.listingId, image)
            
    categories = {
        c_id: {"id": c_id, "name": n, "slug": s}
        for c_id, n, s in db.execute(select(Category.id, Category.name, Category.slug)).all()
    }

    items = []
    for listing in top_listings:
        item = to_dict(listing)
        item["images"] = [to_dict(images[listing.id])] if listing.id in images else []
        item["category"] = categories.get(listing.categoryId)
        items.append(item)

    # 4. Tạo câu trả lời
    parts = []
    if query_text: parts.append(f"món **{query_text}**")
    if filters.get("maxPrice"): parts.append(f"dưới **{filters['maxPrice']:,}đ**".replace(",", "."))
    if filters.get("minPrice"): parts.append(f"trên **{filters['minPrice']:,}đ**".replace(",", "."))
    if filters.get("city"): parts.append(f"tại **{filters['city']}**")

    understood = ", ".join(parts) if parts else "đồ cũ"

    if items:
        if is_fallback:
            message = f"Dạ, em **không tìm thấy chính xác** {understood}. Nhưng em gợi ý cho bạn **{len(items)} sản phẩm tương tự** đang bán:"
        else:
            message = f"Dạ, em hiểu bạn đang tìm {understood}. Em tìm thấy **{len(items)} kết quả** phù hợp nhất:"
    else:
        message = f"Dạ, em đã tìm {understood} nhưng hiện tại **chưa có ai đăng bán** món này."

    return {
        "mode": "NLP",
        "filters": filters,
        "items": items,
        "message": message,
        "note": "Kết quả được xếp hạng bằng thuật toán Fuzzy Search thông minh.",
    }