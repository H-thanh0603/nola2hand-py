"""Gian hàng: tìm kiếm + trang shop công khai — port src/routes/shops.js."""
from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..errors import ApiError
from ..models import Category, Listing, ListingImage, Review, Role, SellerProfile, User, UserRole
from ..pagination import paged_result, paginate
from ..serialize import to_dict
from ..services.reputation import shop_reputation

router = APIRouter()


def _seller_ids(db: Session):
    return select(UserRole.userId).join(Role, Role.id == UserRole.roleId).where(Role.name == "SELLER")


@router.get("/search")
def search_shops(request: Request, db: Session = Depends(get_db)):
    query = dict(request.query_params)
    page = paginate(query)
    q = (query.get("q") or "").strip()

    conditions = [User.id.in_(_seller_ids(db)), User.status == "ACTIVE"]
    if q:
        like = f"%{q}%"
        conditions.append(
            or_(
                User.id.in_(
                    select(SellerProfile.userId).where(SellerProfile.shopName.ilike(like))
                ),
                User.fullName.ilike(like),
            )
        )

    rating = SellerProfile.rating
    rows = db.execute(
        select(User, SellerProfile, rating)
        .outerjoin(SellerProfile, SellerProfile.userId == User.id)
        .where(*conditions)
        .order_by(rating.desc())
        .offset(page["skip"])
        .limit(page["limit"])
    ).all()
    total = db.execute(select(func.count()).select_from(User).where(*conditions)).scalar_one()

    ids = [row[0].id for row in rows]
    counts = {}
    if ids:
        counts = dict(
            db.execute(
                select(Listing.sellerId, func.count())
                .where(Listing.sellerId.in_(ids), Listing.status == "ACTIVE")
                .group_by(Listing.sellerId)
            ).all()
        )

    data = [
        {
            "id": user.id,
            "shopName": (profile.shopName if profile else None) or user.fullName,
            "fullName": user.fullName,
            "avatarUrl": user.avatarUrl,
            "rating": profile.rating if profile else 0,
            "totalReviews": profile.totalReviews if profile else 0,
            "totalOrders": profile.totalOrders if profile else 0,
            "responseRate": None,
            "emailVerified": bool(user.emailVerifiedAt),
            "identityVerified": user.idVerified is True,
            "productsCount": counts.get(user.id, 0),
            "joinedAt": user.createdAt,
        }
        for user, profile, _ in rows
    ]
    return paged_result(data, total, page["page"], page["limit"])


@router.get("/{shop_id}")
def shop_detail(shop_id: int, request: Request, db: Session = Depends(get_db)):
    page = paginate(dict(request.query_params))

    user = db.execute(
        select(User).where(
            User.id == shop_id,
            User.status == "ACTIVE",
            User.id.in_(_seller_ids(db)),
        )
    ).scalar_one_or_none()
    if user is None:
        raise ApiError(404, "Không tìm thấy gian hàng")

    profile = db.execute(
        select(SellerProfile).where(SellerProfile.userId == user.id)
    ).scalar_one_or_none()
    reputation = shop_reputation(db, user)

    conditions = [Listing.sellerId == user.id, Listing.status == "ACTIVE"]
    listings = db.execute(
        select(Listing)
        .where(*conditions)
        .order_by(Listing.boostedUntil.desc(), Listing.createdAt.desc())
        .offset(page["skip"])
        .limit(page["limit"])
    ).scalars().all()
    total_listings = db.execute(
        select(func.count()).select_from(Listing).where(*conditions)
    ).scalar_one()

    listing_ids = [listing.id for listing in listings]
    first_images = {}
    categories = {}
    if listing_ids:
        for image in db.execute(
            select(ListingImage).where(ListingImage.listingId.in_(listing_ids)).order_by(ListingImage.sortOrder)
        ).scalars():
            first_images.setdefault(image.listingId, image)  # take 1
        categories = {
            category.id: category
            for category in db.execute(
                select(Category).where(
                    Category.id.in_({listing.categoryId for listing in listings})
                )
            ).scalars()
        }

    listing_items = []
    for listing in listings:
        item = to_dict(listing)
        image = first_images.get(listing.id)
        item["images"] = [{"id": image.id, "listingId": image.listingId, "url": image.url, "sortOrder": image.sortOrder}] if image else []
        category = categories.get(listing.categoryId)
        item["category"] = {"id": category.id, "name": category.name} if category else None
        listing_items.append(item)

    reviews = db.execute(
        select(Review).where(Review.revieweeId == user.id).order_by(Review.createdAt.desc()).limit(5)
    ).scalars().all()
    reviewer_ids = {review.reviewerId for review in reviews}
    reviewers = (
        {
            reviewer.id: reviewer
            for reviewer in db.execute(select(User).where(User.id.in_(reviewer_ids))).scalars()
        }
        if reviewer_ids
        else {}
    )
    review_items = []
    for review in reviews:
        item = to_dict(review)
        reviewer = reviewers.get(review.reviewerId)
        item["reviewer"] = (
            {"fullName": reviewer.fullName, "avatarUrl": reviewer.avatarUrl} if reviewer else None
        )
        review_items.append(item)

    return {
        "id": user.id,
        "shopName": (profile.shopName if profile else None) or user.fullName,
        "fullName": user.fullName,
        "avatarUrl": user.avatarUrl,
        "rating": reputation["rating"],
        "totalReviews": reputation["totalReviews"],
        "totalOrders": reputation["completedOrders"],
        "responseRate": reputation["responseRate"],
        "reputation": reputation,
        "joinedAt": user.createdAt,
        "listings": paged_result(listing_items, total_listings, page["page"], page["limit"]),
        "recentReviews": review_items,
    }
