"""Bộ dọn đơn giữ món hết hạn — port setInterval 60 giây của bản Node."""
from datetime import timedelta

from sqlalchemy import select, update

from app.db import SessionLocal
from app.models import Listing, Notification, Order, OrderTimeline
from app.services.reservations import expire_reservations
from app.utils import now

LISTING = {
    "categoryId": 1,
    "title": "Máy ảnh QA còn bảo hành",
    "description": "Mô tả đủ dài cho tin đăng thử nghiệm, vượt qua giới hạn hai mươi ký tự.",
    "price": 500_000,
    "condition": "USED_GOOD",
    "city": "TP.HCM",
    "images": ["https://cdn.example.com/qa-1.jpg"],
    "specifications": {"brand": "Canon", "warranty": "6 tháng"},
}

SHIP = {
    "shipName": "Người nhận QA",
    "shipPhone": "0987654321",
    "shipAddress": "123 Đường QA, Phường 1, TP.HCM",
}


def test_don_het_han_giu_mon_bi_huy(make_user, client):
    seller = make_user(["SELLER"], verified=True)
    buyer = make_user(verified=True)

    created = client.post("/api/v1/listings", headers=seller["headers"], json=LISTING)
    assert created.status_code == 201, created.text
    listing_id = created.json()["listing"]["id"]
    with SessionLocal() as db:
        db.execute(update(Listing).where(Listing.id == listing_id).values(status="ACTIVE"))
        db.commit()

    order = client.post(
        "/api/v1/orders", headers=buyer["headers"], json={"listingId": listing_id, **SHIP}
    )
    assert order.status_code == 201, order.text
    order_id = order.json()["id"]

    with SessionLocal() as db:
        assert db.get(Order, order_id).status == "PENDING_DEPOSIT"
        assert db.get(Listing, listing_id).status == "RESERVED"
        db.execute(
            update(Order)
            .where(Order.id == order_id)
            .values(reservationExpiresAt=now() - timedelta(minutes=1))
        )
        db.commit()

    with SessionLocal() as db:
        assert expire_reservations(db) == 1

    with SessionLocal() as db:
        expired = db.get(Order, order_id)
        assert expired.status == "CANCELLED"
        assert expired.cancelReason == "Hết thời hạn đặt cọc"
        assert db.get(Listing, listing_id).status == "ACTIVE"

        timeline = db.execute(
            select(OrderTimeline.status).where(OrderTimeline.orderId == order_id)
        ).scalars().all()
        assert "CANCELLED" in timeline

        notice = db.execute(
            select(Notification).where(
                Notification.userId == buyer["id"], Notification.title == "Đơn hết thời hạn giữ món"
            )
        ).scalar_one()
        assert notice.body == order.json()["code"]

        # Chạy lại không còn gì để dọn.
        assert expire_reservations(db) == 0
