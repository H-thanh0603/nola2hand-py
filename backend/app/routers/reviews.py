"""Đánh giá sau mua — port src/routes/reviews.js."""
import re
from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, field_validator
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import CurrentUser, current_user, require_role
from ..errors import ApiError
from ..models import Listing, ListingImage, Order, Review, SellerProfile, User
from ..pagination import js_parse_int, paged_result, paginate
from ..serialize import to_dict
from ..services.ai import analyze_sentiment, local_sentiment
from ..utils import notify

router = APIRouter()

TOPICS = (
    ("Giao hàng chậm", re.compile(r"giao.*chậm|chậm.*giao", re.IGNORECASE)),
    ("Không đúng mô tả", re.compile(r"không đúng|sai mô tả", re.IGNORECASE)),
    ("Lỗi / hỏng", re.compile(r"hỏng|bị lỗi|không hoạt động", re.IGNORECASE)),
    ("Thái độ / phản hồi", re.compile(r"thái độ|không phản hồi|không trả lời", re.IGNORECASE)),
)

class ReviewIn(BaseModel):
    rating: int
    comment: str | None = None
    type: Literal["SELLER", "PRODUCT"] = "SELLER"
    listingId: int | None = None

    @field_validator("rating")
    @classmethod
    def _rating(cls, value: int) -> int:
        if not 1 <= value <= 5:
            raise ValueError("Number must be less than or equal to 5" if value > 5 else "Number must be greater than or equal to 1")
        return value

    @field_validator("comment")
    @classmethod
    def _comment(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if len(value) > 1000:
            raise ValueError("String must contain at most 1000 character(s)")
        return value

class ReplyIn(BaseModel):
    reply: str

    @field_validator("reply")
    @classmethod
    def _reply(cls, value: str) -> str:
        value = value.strip()
        if not 1 <= len(value) <= 1000:
            raise ValueError("String must contain at least 1 character(s)" if not value else "String must contain at most 1000 character(s)")
        return value


def _generate_review_summary(reviews_list: list[dict]) -> str:
    """Tạo câu tóm tắt tự nhiên dựa trên từ khóa trong đánh giá."""
    positives, negatives = [], []
    positive_keywords = {"tốt", "nhanh", "uy tín", "đẹp", "xịn", "chất lượng", "hài lòng"}
    negative_keywords = {"lỗi", "chậm", "tệ", "kém", "hỏng", "lừa đảo", "thất vọng"}

    for r in reviews_list:
        comment = (r.get("comment") or "").lower()
        for kw in positive_keywords:
            if kw in comment and kw not in positives: positives.append(kw)
        for kw in negative_keywords:
            if kw in comment and kw not in negatives: negatives.append(kw)

    pos_text = ", ".join(positives[:3])
    neg_text = ", ".join(negatives[:3])

    if pos_text and neg_text:
        return f"Người mua khen ngợi về {pos_text}, nhưng cũng có ý kiến phàn nàn về {neg_text}."
    elif pos_text:
        return f"Đa số người mua rất hài lòng, đặc biệt khen ngợi về {pos_text}."
    elif neg_text:
        return f"Cần lưu ý: Người mua phản ánh khá nhiều về {neg_text}."
    else:
        return "Chưa có đủ đánh giá chi tiết để tóm tắt."


@router.post("/orders/{order_id}/reviews", status_code=201)
def create_review(
    order_id: int,
    payload: ReviewIn,
    user: CurrentUser = Depends(current_user),
    db: Session = Depends(get_db),
):
    order = db.execute(select(Order).where(Order.id == order_id)).scalar_one_or_none()
    if order is None:
        raise ApiError(404, "Không tìm thấy đơn hàng")
    if order.buyerId != user.id:
        raise ApiError(403, "Chỉ người mua mới đánh giá được")
    if order.status != "COMPLETED":
        raise ApiError(400, "Chỉ đánh giá khi đơn đã hoàn tất")
    exists = db.execute(select(Review.id).where(Review.orderId == order.id)).scalar_one_or_none()
    if exists is not None:
        raise ApiError(400, "Đơn này đã được đánh giá")
    if payload.listingId is not None and payload.listingId != order.listingId:
        raise ApiError(400, "Sản phẩm đánh giá phải thuộc đơn đã mua")

    sentiment = analyze_sentiment(payload.comment, payload.rating)
    review = Review(
        orderId=order.id,
        reviewerId=user.id,
        revieweeId=order.sellerId,
        listingId=order.listingId if payload.type == "PRODUCT" else None,
        rating=payload.rating,
        comment=payload.comment,
        type=payload.type,
        sentiment=sentiment["sentiment"],
        sentimentSource=sentiment["sentimentSource"],
    )
    db.add(review)
    db.flush()

    average, total = db.execute(
        select(func.avg(Review.rating), func.count())
        .select_from(Review)
        .where(Review.revieweeId == order.sellerId)
    ).one()
    profile = db.execute(
        update(SellerProfile)
        .where(SellerProfile.userId == order.sellerId)
        .values(rating=average or 0, totalReviews=total)
    )
    if profile.rowcount == 0:
        raise ApiError(404, "Không tìm thấy hồ sơ người bán")

    notify(
        db,
        order.sellerId,
        "SYSTEM",
        "Bạn có đánh giá mới",
        f"Đơn {order.code} được đánh giá {payload.rating}★",
        {"orderId": order.id},
    )
    db.commit()
    return {"message": "Cảm ơn bạn đã đánh giá", "review": to_dict(review)}


@router.post("/{review_id}/reply")
def reply_review(
    review_id: int,
    payload: ReplyIn,
    user: CurrentUser = Depends(require_role("SELLER")),
    db: Session = Depends(get_db),
):
    review = db.execute(select(Review).where(Review.id == review_id)).scalar_one_or_none()
    if review is None or review.revieweeId != user.id:
        raise ApiError(404, "Không tìm thấy đánh giá")
    review.sellerReply = payload.reply
    db.commit()
    return to_dict(review)


@router.get("/users/{user_id}")
def user_reviews(user_id: int, request: Request, db: Session = Depends(get_db)):
    page = paginate(dict(request.query_params))
    conditions = [Review.revieweeId == user_id]
    type_filter = request.query_params.get("type")
    if type_filter:
        conditions.append(Review.type == type_filter)

    rows = db.execute(
        select(Review)
        .where(*conditions)
        .order_by(Review.createdAt.desc())
        .offset(page["skip"])
        .limit(page["limit"])
    ).scalars().all()
    total = db.execute(
        select(func.count()).select_from(Review).where(*conditions)
    ).scalar_one()

    reviews = list(rows)
    reviewer_ids = {review.reviewerId for review in reviews}
    reviewers = {
        row.id: row
        for row in db.execute(select(User).where(User.id.in_(reviewer_ids))).scalars()
    }
    listing_ids = {review.listingId for review in reviews if review.listingId is not None}
    listings = {
        listing.id: listing
        for listing in db.execute(select(Listing).where(Listing.id.in_(listing_ids))).scalars()
    } if listing_ids else {}

    items = []
    for review in reviews:
        item = to_dict(review)
        reviewer = reviewers.get(review.reviewerId)
        item["reviewer"] = (
            {"id": reviewer.id, "fullName": reviewer.fullName, "avatarUrl": reviewer.avatarUrl}
            if reviewer
            else None
        )
        listing = listings.get(review.listingId)
        item["listing"] = {"id": listing.id, "title": listing.title} if listing else None
        items.append(item)

    stats = db.execute(
        select(Review.rating, func.count())
        .where(Review.revieweeId == user_id)
        .group_by(Review.rating)
    ).all()
    return {
        **paged_result(items, total, page["page"], page["limit"]),
        "ratingStats": [{"rating": rating, "_count": count} for rating, count in stats],
    }


@router.get("/mine/pending")
def pending_reviews(user: CurrentUser = Depends(current_user), db: Session = Depends(get_db)):
    orders = db.execute(
        select(Order)
        .where(
            Order.buyerId == user.id,
            Order.status == "COMPLETED",
            Order.id.not_in(select(Review.orderId)),
        )
        .order_by(Order.updatedAt.desc())
    ).scalars().all()

    order_ids = [order.id for order in orders]
    listing_ids = {order.listingId for order in orders}
    listings = {
        listing.id: listing
        for listing in db.execute(select(Listing).where(Listing.id.in_(listing_ids))).scalars()
    } if listing_ids else {}
    first_images: dict[int, ListingImage] = {}
    if listing_ids:
        for image in db.execute(
            select(ListingImage)
            .where(ListingImage.listingId.in_(listing_ids))
            .order_by(ListingImage.sortOrder)
        ).scalars():
            first_images.setdefault(image.listingId, image)
    seller_ids = {order.sellerId for order in orders}
    names = {
        user_id: full_name
        for user_id, full_name in db.execute(
            select(User.id, User.fullName).where(User.id.in_(seller_ids))
        ).all()
    }

    items = []
    for order in orders:
        item = to_dict(order)
        listing = listings.get(order.listingId)
        if listing is not None:
            listing_payload = to_dict(listing)
            image = first_images.get(listing.id)
            listing_payload["images"] = [to_dict(image)] if image is not None else []
            item["listing"] = listing_payload
        else:
            item["listing"] = None
        item["seller"] = {"fullName": names.get(order.sellerId)}
        items.append(item)
    return items


@router.get("/insights")
def review_insights(
    request: Request,
    user: CurrentUser = Depends(require_role("SELLER", "ADMIN_CONTENT", "ADMIN_FINANCE")),
    db: Session = Depends(get_db),
):
    is_admin = any(role.startswith("ADMIN") for role in user.roles)
    raw_user_id = request.query_params.get("userId")
    seller_id = None
    if raw_user_id:
        seller_id = js_parse_int(raw_user_id)
        if seller_id is None or seller_id <= 0:
            raise ApiError(400, "Người bán không hợp lệ")

    conditions = []
    if not (is_admin and seller_id is None):
        conditions.append(Review.revieweeId == seller_id if is_admin else Review.revieweeId == user.id)

    rows = db.execute(
        select(Review.comment, Review.rating, Review.sentiment, Review.sentimentSource)
        .where(*conditions)
        .order_by(Review.createdAt.desc())
        .limit(500)
    ).all()
    reviews = [
        {
            "comment": comment,
            "rating": rating,
            "sentiment": sentiment,
            "sentimentSource": source,
        }
        if source == "AI"
        else {
            "comment": comment,
            "rating": rating,
            **local_sentiment(comment, rating),
        }
        for comment, rating, sentiment, source in rows
    ]

    ai_summary = _generate_review_summary(reviews)

    return {
        "sampleSize": len(reviews),
        "averageRating": sum(review["rating"] for review in reviews) / len(reviews) if reviews else 0,
        "sentiments": [
            {"sentiment": name, "count": sum(1 for review in reviews if review["sentiment"] == name)}
            for name in ("POSITIVE", "NEUTRAL", "NEGATIVE")
        ],
        "sources": {
            "ai": sum(1 for review in reviews if review["sentimentSource"] == "AI"),
            "local": sum(1 for review in reviews if review["sentimentSource"] != "AI"),
        },
        "issues": [
            {
                "name": name,
                "count": sum(1 for review in reviews if pattern.search(review["comment"] or "")),
            }
            for name, pattern in TOPICS
        ],
        "aiSummary": ai_summary, # <--- NEW
    }


@router.get("/listings/{listing_id}/summary")
def listing_review_summary(listing_id: int, db: Session = Depends(get_db)):
    reviews = db.execute(
        select(Review.sentiment, Review.sentimentSource, Review.rating, Review.comment)
        .where(Review.listingId == listing_id)
    ).all()

    if not reviews:
        return {
            "totalReviews": 0,
            "averageRating": 0,
            "distribution": {"POSITIVE": 0, "NEUTRAL": 0, "NEGATIVE": 0},
            "aiReasons": [],
            "aiSummary": ""
        }

    sentiments = {"POSITIVE": 0, "NEUTRAL": 0, "NEGATIVE": 0}
    total_rating = 0
    reasons = []

    for sentiment, source, rating, comment in reviews:
        total_rating += rating
        # Re-run local AI to get the reason (in case it wasn't stored)
        analysis = local_sentiment(comment, rating)
        final_sentiment = analysis["sentiment"]
        
        if final_sentiment in sentiments:
            sentiments[final_sentiment] += 1
            
        # If the reason is interesting (has keywords), save it for the UI
        if analysis.get("reason") and analysis["reason"] != "Không có từ khóa":
            reasons.append(f"\"{comment[:30]}...\" → {analysis['reason']}")

    ai_summary = _generate_review_summary([
        {"comment": comment, "sentiment": sentiment} 
        for sentiment, source, rating, comment in reviews
    ])

    return {
        "totalReviews": len(reviews),
        "averageRating": round(total_rating / len(reviews), 1),
        "distribution": sentiments,
        "aiReasons": reasons[:3],
        "aiSummary": ai_summary,
    }