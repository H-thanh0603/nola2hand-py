"""Kênh người bán — port src/routes/seller.js."""
from datetime import timedelta

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import CurrentUser, require_role
from ..errors import ApiError
from ..models import (
    Category,
    Escrow,
    Listing,
    ListingImage,
    Order,
    OrderTimeline,
    User,
    Wallet,
    WalletTransaction,
)
from ..pagination import paged_result, paginate
from ..serialize import to_dict
from ..services.revenue import daily_revenue
from ..utils import now

router = APIRouter()


@router.get("/listings/{listing_id}")
def seller_listing(
    listing_id: int,
    user: CurrentUser = Depends(require_role("SELLER")),
    db: Session = Depends(get_db),
):
    listing = db.execute(
        select(Listing).where(Listing.id == listing_id, Listing.sellerId == user.id)
    ).scalar_one_or_none()
    if listing is None:
        raise ApiError(404, "Không tìm thấy tin đăng của bạn")

    payload = to_dict(listing)
    payload["images"] = [
        to_dict(image)
        for image in db.execute(
            select(ListingImage)
            .where(ListingImage.listingId == listing.id)
            .order_by(ListingImage.sortOrder.asc())
        ).scalars()
    ]
    category = db.execute(
        select(Category).where(Category.id == listing.categoryId)
    ).scalar_one_or_none()
    payload["category"] = to_dict(category) if category is not None else None
    return payload


@router.get("/dashboard")
def dashboard(user: CurrentUser = Depends(require_role("SELLER")), db: Session = Depends(get_db)):
    seller_id = user.id
    week_ago = now() - timedelta(days=7)

    active_listings = db.execute(
        select(func.count())
        .select_from(Listing)
        .where(Listing.sellerId == seller_id, Listing.status == "ACTIVE")
    ).scalar_one()
    pending_orders = db.execute(
        select(func.count())
        .select_from(Order)
        .where(Order.sellerId == seller_id, Order.status.in_(("DEPOSITED", "CONFIRMED")))
    ).scalar_one()
    total_views = db.execute(
        select(func.coalesce(func.sum(Listing.views), 0)).where(Listing.sellerId == seller_id)
    ).scalar_one()

    listing_status = [
        {"status": status, "_count": count}
        for status, count in db.execute(
            select(Listing.status, func.count())
            .where(Listing.sellerId == seller_id)
            .group_by(Listing.status)
        ).all()
    ]

    order_rows = db.execute(
        select(Order)
        .where(Order.sellerId == seller_id)
        .order_by(Order.createdAt.desc())
        .limit(5)
    ).scalars().all()
    buyer_names = {
        user_id: full_name
        for user_id, full_name in db.execute(
            select(User.id, User.fullName).where(
                User.id.in_({order.buyerId for order in order_rows})
            )
        ).all()
    }
    listing_titles = {
        listing_id: title
        for listing_id, title in db.execute(
            select(Listing.id, Listing.title).where(
                Listing.id.in_({order.listingId for order in order_rows})
            )
        ).all()
    }
    recent_orders = []
    for order in order_rows:
        item = to_dict(order)
        item["buyer"] = {"fullName": buyer_names.get(order.buyerId)}
        item["listing"] = {"title": listing_titles.get(order.listingId)}
        recent_orders.append(item)

    timeline_rows = db.execute(
        select(OrderTimeline)
        .join(Order, Order.id == OrderTimeline.orderId)
        .where(Order.sellerId == seller_id)
        .order_by(OrderTimeline.createdAt.desc())
        .limit(8)
    ).scalars().all()
    codes = {
        order_id: code
        for order_id, code in db.execute(
            select(Order.id, Order.code).where(
                Order.id.in_({row.orderId for row in timeline_rows})
            )
        ).all()
    }
    recent_activities = []
    for row in timeline_rows:
        item = to_dict(row)
        item["order"] = {"code": codes.get(row.orderId)}
        recent_activities.append(item)

    weekly_revenue = db.execute(
        select(func.coalesce(func.sum(WalletTransaction.amount), 0))
        .join(Wallet, Wallet.id == WalletTransaction.walletId)
        .where(
            Wallet.userId == seller_id,
            WalletTransaction.type.in_(("ORDER_INCOME", "PLATFORM_FEE")),
            WalletTransaction.status == "SUCCESS",
            WalletTransaction.createdAt >= week_ago,
        )
    ).scalar_one()
    escrow_held = db.execute(
        select(func.coalesce(func.sum(Escrow.amount), 0))
        .join(Order, Order.id == Escrow.orderId)
        .where(Order.sellerId == seller_id, Escrow.status == "HELD")
    ).scalar_one()
    order_value = db.execute(
        select(func.coalesce(func.sum(Order.totalAmount), 0)).where(
            Order.sellerId == seller_id,
            Order.status.not_in(("CANCELLED", "REFUNDED")),
        )
    ).scalar_one()

    top_rows = db.execute(
        select(Listing)
        .where(Listing.sellerId == seller_id, Listing.status.in_(("ACTIVE", "SOLD_OUT")))
        .order_by(Listing.views.desc())
        .limit(5)
    ).scalars().all()
    top_ids = [listing.id for listing in top_rows]
    first_images: dict[int, str] = {}
    if top_ids:
        for image in db.execute(
            select(ListingImage)
            .where(ListingImage.listingId.in_(top_ids))
            .order_by(ListingImage.sortOrder)
        ).scalars():
            first_images.setdefault(image.listingId, image.url)
    order_counts = dict(
        db.execute(
            select(Order.listingId, func.count())
            .where(Order.listingId.in_(top_ids))
            .group_by(Order.listingId)
        ).all()
    ) if top_ids else {}

    return {
        "kpis": {
            "activeListings": active_listings,
            "pendingOrders": pending_orders,
            "totalViews": total_views,
            "weeklyRevenue": weekly_revenue,
            "escrowHeld": escrow_held,
            "orderValue": order_value,
        },
        "listingStatus": listing_status,
        "recentOrders": recent_orders,
        "recentActivities": recent_activities,
        "topProducts": [
            {
                "id": listing.id,
                "title": listing.title,
                "price": listing.price,
                "views": listing.views,
                "orders": order_counts.get(listing.id, 0),
                "image": first_images.get(listing.id),
            }
            for listing in top_rows
        ],
    }


@router.get("/listings")
def my_listings(
    request: Request,
    user: CurrentUser = Depends(require_role("SELLER")),
    db: Session = Depends(get_db),
):
    page = paginate(dict(request.query_params))
    conditions = [Listing.sellerId == user.id]
    status = request.query_params.get("status")
    if status:
        conditions.append(Listing.status == status)
    query_text = request.query_params.get("q")
    if query_text:
        conditions.append(Listing.title.ilike(f"%{query_text}%"))

    rows = db.execute(
        select(Listing)
        .where(*conditions)
        .order_by(Listing.updatedAt.desc())
        .offset(page["skip"])
        .limit(page["limit"])
    ).scalars().all()
    total = db.execute(
        select(func.count()).select_from(Listing).where(*conditions)
    ).scalar_one()

    listings = list(rows)
    listing_ids = [listing.id for listing in listings]
    images: dict[int, dict] = {}
    if listing_ids:
        for image in db.execute(
            select(ListingImage)
            .where(ListingImage.listingId.in_(listing_ids))
            .order_by(ListingImage.sortOrder)
        ).scalars():
            images.setdefault(image.listingId, to_dict(image))
    categories = {
        category.id: category.name
        for category in db.execute(
            select(Category).where(
                Category.id.in_({listing.categoryId for listing in listings})
            )
        ).scalars()
    } if listings else {}
    order_counts = dict(
        db.execute(
            select(Order.listingId, func.count())
            .where(Order.listingId.in_(listing_ids))
            .group_by(Order.listingId)
        ).all()
    ) if listing_ids else {}

    items = []
    for listing in listings:
        item = to_dict(listing)
        image = images.get(listing.id)
        item["images"] = [image] if image is not None else []
        item["category"] = {"name": categories.get(listing.categoryId)}
        item["_count"] = {"orders": order_counts.get(listing.id, 0)}
        items.append(item)
    return paged_result(items, total, page["page"], page["limit"])


@router.get("/charts/revenue")
def revenue_chart(
    request: Request,
    user: CurrentUser = Depends(require_role("SELLER")),
    db: Session = Depends(get_db),
):
    return daily_revenue(db, dict(request.query_params), user.id)
