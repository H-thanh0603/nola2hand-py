"""Tạo đơn hàng + ghép dữ liệu đơn — port src/routes/orders.js (createSingleOrder, orderInclude)."""
from datetime import timedelta

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ..errors import ApiError
from ..models import (
    Escrow,
    Listing,
    ListingImage,
    Order,
    OrderTimeline,
    PriceOffer,
    Promo,
    PromoUsage,
    ReturnRequest,
    Review,
    User,
)
from ..serialize import to_dict
from ..utils import calc_platform_fee, gen_order_code, js_round, notify, now, push_timeline, vnd
from .locks import lock_user
from .reservations import expire_reservations

MAX_PENDING_DEPOSITS = 3
SHIPPING_FEE = 15000
RESERVATION_MINUTES = 30


def serialize_orders(db: Session, orders: list[Order], with_review: bool = False) -> list[dict]:
    if not orders:
        return []
    ids = [order.id for order in orders]

    listings = {
        listing.id: listing
        for listing in db.execute(
            select(Listing).where(Listing.id.in_({order.listingId for order in orders}))
        ).scalars()
    }
    first_image: dict[int, ListingImage] = {}
    for image in db.execute(
        select(ListingImage)
        .where(ListingImage.listingId.in_(list(listings)))
        .order_by(ListingImage.sortOrder)
    ).scalars():
        first_image.setdefault(image.listingId, image)

    user_ids = {order.buyerId for order in orders} | {order.sellerId for order in orders}
    users = {user.id: user for user in db.execute(select(User).where(User.id.in_(user_ids))).scalars()}

    escrows = {
        escrow.orderId: escrow
        for escrow in db.execute(select(Escrow).where(Escrow.orderId.in_(ids))).scalars()
    }
    returns = {
        row.orderId: row
        for row in db.execute(select(ReturnRequest).where(ReturnRequest.orderId.in_(ids))).scalars()
    }

    timeline: dict[int, list[dict]] = {order_id: [] for order_id in ids}
    for row in db.execute(
        select(OrderTimeline).where(OrderTimeline.orderId.in_(ids)).order_by(OrderTimeline.createdAt.asc())
    ).scalars():
        timeline[row.orderId].append(to_dict(row))

    reviews = {}
    if with_review:
        reviews = {
            row.orderId: row
            for row in db.execute(select(Review).where(Review.orderId.in_(ids))).scalars()
        }

    items = []
    for order in orders:
        item = to_dict(order)
        listing = listings.get(order.listingId)
        if listing is not None:
            listing_payload = to_dict(listing)
            image = first_image.get(listing.id)
            listing_payload["images"] = [to_dict(image)] if image is not None else []
            item["listing"] = listing_payload
        else:
            item["listing"] = None

        for side, user_id in (("buyer", order.buyerId), ("seller", order.sellerId)):
            user = users.get(user_id)
            item[side] = (
                {
                    "id": user.id,
                    "fullName": user.fullName,
                    "avatarUrl": user.avatarUrl,
                    "phone": user.phone,
                }
                if user
                else None
            )
        item["escrow"] = to_dict(escrows.get(order.id)) if order.id in escrows else None
        item["returnRequest"] = to_dict(returns.get(order.id)) if order.id in returns else None
        item["timeline"] = timeline[order.id]
        if with_review:
            item["review"] = to_dict(reviews.get(order.id)) if order.id in reviews else None
        items.append(item)
    return items


def serialize_order(db: Session, order: Order, with_review: bool = False) -> dict:
    return serialize_orders(db, [order], with_review=with_review)[0]


def create_single_order(
    db: Session,
    buyer_id: int,
    *,
    listing_id: int,
    ship: dict,
    offer_id: int | None = None,
    promo_code: str | None = None,
) -> Order:
    """Tạo một đơn (mua ngay hoặc từ giỏ). Tự commit; lỗi thì ném ApiError."""
    expire_reservations(db)

    listing = db.execute(select(Listing).where(Listing.id == listing_id)).scalar_one_or_none()
    if listing is None or listing.status != "ACTIVE":
        raise ApiError(404, "Sản phẩm không khả dụng")
    if listing.sellerId == buyer_id:
        raise ApiError(400, "Không thể mua tin của chính mình")

    price_agreed = listing.price
    if offer_id:
        offer = db.execute(select(PriceOffer).where(PriceOffer.id == offer_id)).scalar_one_or_none()
        if (
            offer is None
            or offer.buyerId != buyer_id
            or offer.listingId != listing.id
            or offer.status != "ACCEPTED"
            or offer.expiresAt <= now()
        ):
            raise ApiError(400, "Yêu cầu trả giá không hợp lệ")
        price_agreed = offer.offeredPrice

    discount = 0
    promo = None
    if promo_code:
        promo = db.execute(select(Promo).where(Promo.code == promo_code)).scalar_one_or_none()
        moment = now()
        if (
            promo is None
            or promo.status != "ACTIVE"
            or promo.startsAt > moment
            or promo.endsAt < moment
        ):
            raise ApiError(400, "Mã khuyến mãi không hợp lệ")
        if promo.usageLimit and promo.usedCount >= promo.usageLimit:
            raise ApiError(400, "Mã đã hết lượt sử dụng")
        if price_agreed < promo.minOrder:
            raise ApiError(400, f"Đơn tối thiểu {vnd(promo.minOrder)}đ")
        if promo.discountType == "PERCENT":
            # Math.round((priceAgreed * value) / 100) rồi chặn bởi maxDiscount
            raw = js_round((price_agreed * promo.discountValue) / 100)
            discount = min(raw, promo.maxDiscount) if promo.maxDiscount else raw
        else:
            discount = promo.discountValue
        discount = min(discount, price_agreed)

    platform_fee, _percent = calc_platform_fee(db, listing.categoryId, price_agreed)
    total_amount = price_agreed - discount + SHIPPING_FEE

    lock_user(db, buyer_id)
    pending = db.execute(
        select(func.count())
        .select_from(Order)
        .where(Order.buyerId == buyer_id, Order.status == "PENDING_DEPOSIT")
    ).scalar_one()
    if pending >= MAX_PENDING_DEPOSITS:
        raise ApiError(429, "Tối đa 3 đơn đang chờ đặt cọc. Hãy thanh toán hoặc hủy đơn cũ.")

    reserved = db.execute(
        update(Listing)
        .where(Listing.id == listing.id, Listing.status == "ACTIVE")
        .values(status="RESERVED", updatedAt=now())
    )
    if reserved.rowcount == 0:
        raise ApiError(409, "Sản phẩm vừa được người khác đặt, vui lòng chọn tin khác")

    order = Order(
        code=gen_order_code(),
        buyerId=buyer_id,
        sellerId=listing.sellerId,
        listingId=listing.id,
        priceAgreed=price_agreed,
        remainingAmount=total_amount,
        reservationExpiresAt=now() + timedelta(minutes=RESERVATION_MINUTES),
        shippingFee=SHIPPING_FEE,
        discountAmount=discount,
        totalAmount=total_amount,
        platformFee=platform_fee,
        updatedAt=now(),
        **ship,
    )
    db.add(order)
    db.flush()
    push_timeline(db, order.id, "PENDING_DEPOSIT", "Đơn hàng được tạo, chờ đặt cọc")

    if promo is not None:
        conditions = [
            Promo.id == promo.id,
            Promo.status == "ACTIVE",
            Promo.startsAt <= now(),
            Promo.endsAt >= now(),
        ]
        if promo.usageLimit:
            conditions.append(Promo.usedCount < promo.usageLimit)
        claimed = db.execute(
            update(Promo).where(*conditions).values(usedCount=Promo.usedCount + 1)
        )
        if claimed.rowcount == 0:
            raise ApiError(400, "Mã đã hết lượt sử dụng")
        db.add(PromoUsage(promoId=promo.id, userId=buyer_id, orderId=order.id))

    db.commit()

    notify(
        db,
        listing.sellerId,
        "ORDER",
        "Có đơn hàng mới",
        f'Đơn {order.code}: "{listing.title}" — {vnd(price_agreed)}đ',
        {"orderId": order.id},
    )
    db.commit()
    return order
