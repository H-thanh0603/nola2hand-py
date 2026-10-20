"""Trả giá — port src/routes/offers.js."""
from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import CurrentUser, current_user, require_role
from ..errors import ApiError
from ..models import Listing, ListingImage, PriceOffer, User
from ..pagination import paged_result, paginate
from ..serialize import to_dict
from ..utils import notify, now, vnd

router = APIRouter()


class OfferActionIn(BaseModel):
    action: Literal["ACCEPT", "REJECT", "CANCEL"]


@router.get("/mine")
def my_offers(
    request: Request,
    user: CurrentUser = Depends(current_user),
    db: Session = Depends(get_db),
):
    page = paginate(dict(request.query_params))
    conditions = [PriceOffer.buyerId == user.id]
    status = request.query_params.get("status")
    if status:
        conditions.append(PriceOffer.status == status)

    offers = db.execute(
        select(PriceOffer)
        .where(*conditions)
        .order_by(PriceOffer.createdAt.desc())
        .offset(page["skip"])
        .limit(page["limit"])
    ).scalars().all()
    total = db.execute(select(func.count()).select_from(PriceOffer).where(*conditions)).scalar_one()

    listing_ids = {offer.listingId for offer in offers}
    listings = {
        listing.id: listing
        for listing in db.execute(select(Listing).where(Listing.id.in_(listing_ids))).scalars()
    } if listing_ids else {}
    first_images: dict[int, ListingImage] = {}
    if listing_ids:
        for image in db.execute(
            select(ListingImage).where(ListingImage.listingId.in_(listing_ids)).order_by(ListingImage.sortOrder)
        ).scalars():
            first_images.setdefault(image.listingId, image)
    sellers = {
        seller.id: seller
        for seller in db.execute(
            select(User).where(User.id.in_({listing.sellerId for listing in listings.values()}))
        ).scalars()
    } if listings else {}

    items = []
    for offer in offers:
        item = to_dict(offer)
        listing = listings.get(offer.listingId)
        if listing is not None:
            payload = to_dict(listing)
            image = first_images.get(listing.id)
            payload["images"] = [to_dict(image)] if image is not None else []
            seller = sellers.get(listing.sellerId)
            payload["seller"] = {"fullName": seller.fullName} if seller else None
            item["listing"] = payload
        else:
            item["listing"] = None
        items.append(item)
    return paged_result(items, total, page["page"], page["limit"])


@router.get("/inbox", dependencies=[Depends(require_role("SELLER"))])
def offer_inbox(
    request: Request,
    user: CurrentUser = Depends(current_user),
    db: Session = Depends(get_db),
):
    page = paginate(dict(request.query_params))
    conditions = [Listing.sellerId == user.id]
    status = request.query_params.get("status")
    if status:
        conditions.append(PriceOffer.status == status)

    base = (
        select(PriceOffer, Listing.title, Listing.price, User.id, User.fullName, User.avatarUrl)
        .join(Listing, Listing.id == PriceOffer.listingId)
        .join(User, User.id == PriceOffer.buyerId)
        .where(*conditions)
    )
    rows = db.execute(
        base.order_by(PriceOffer.createdAt.desc()).offset(page["skip"]).limit(page["limit"])
    ).all()
    total = db.execute(
        select(func.count())
        .select_from(PriceOffer)
        .join(Listing, Listing.id == PriceOffer.listingId)
        .where(*conditions)
    ).scalar_one()

    items = []
    for offer, title, price, buyer_id, buyer_name, buyer_avatar in rows:
        item = to_dict(offer)
        item["listing"] = {"title": title, "price": price}
        item["buyer"] = {"id": buyer_id, "fullName": buyer_name, "avatarUrl": buyer_avatar}
        items.append(item)
    return paged_result(items, total, page["page"], page["limit"])


@router.patch("/{offer_id}")
def act_on_offer(
    offer_id: int,
    payload: OfferActionIn,
    user: CurrentUser = Depends(current_user),
    db: Session = Depends(get_db),
):
    offer = db.execute(select(PriceOffer).where(PriceOffer.id == offer_id)).scalar_one_or_none()
    if offer is None:
        raise ApiError(404, "Không tìm thấy yêu cầu")
    if offer.status != "PENDING":
        raise ApiError(400, f"Yêu cầu đã ở trạng thái {offer.status}")

    listing = db.execute(select(Listing).where(Listing.id == offer.listingId)).scalar_one()
    action = payload.action
    is_seller = listing.sellerId == user.id
    is_buyer = offer.buyerId == user.id

    if action in ("ACCEPT", "REJECT"):
        if not is_seller:
            raise ApiError(403, "Chỉ người bán mới duyệt được")
    elif not is_buyer:
        raise ApiError(403, "Chỉ người mua mới huỷ được")

    status = {"ACCEPT": "ACCEPTED", "REJECT": "REJECTED", "CANCEL": "CANCELLED"}[action]
    if offer.expiresAt <= now():
        raise ApiError(400, "Yêu cầu trả giá đã hết hạn")
    if action == "ACCEPT" and listing.status != "ACTIVE":
        raise ApiError(409, "Tin không còn khả dụng")

    moved = db.execute(
        update(PriceOffer)
        .where(
            PriceOffer.id == offer.id,
            PriceOffer.status == "PENDING",
            PriceOffer.expiresAt > now(),
        )
        .values(status=status)
    )
    if moved.rowcount == 0:
        raise ApiError(409, "Yêu cầu đã thay đổi hoặc hết hạn")

    updated = db.execute(select(PriceOffer).where(PriceOffer.id == offer.id)).scalar_one()
    titles = {
        "ACCEPT": "Người bán đã đồng ý mức giá",
        "REJECT": "Người bán đã từ chối",
        "CANCEL": "Người mua đã huỷ yêu cầu",
    }
    target_id = offer.buyerId if is_seller else listing.sellerId
    notify(
        db,
        target_id,
        "OFFER",
        titles[action],
        f'Yêu cầu trả giá {vnd(offer.offeredPrice)}đ cho "{listing.title}": {status}',
        {"offerId": offer.id},
    )
    db.commit()
    return {"message": titles[action], "offer": to_dict(updated)}

