"""Test tích hợp: dashboard, tin đăng và biểu đồ doanh thu của người bán."""
from sqlalchemy import update

from app.db import SessionLocal
from app.models import Listing

LISTING = {
    "categoryId": 1,
    "title": "Máy ảnh QA còn bảo hành",
    "description": "Mô tả đủ dài cho tin đăng thử nghiệm, vượt qua giới hạn hai mươi ký tự.",
    "price": 500_000,
    "condition": "USED_GOOD",
    "city": "TP.HCM",
    "images": ["https://cdn.example.com/qa-1.jpg", "https://cdn.example.com/qa-2.jpg"],
    "specifications": {"brand": "Canon", "warranty": "6 tháng"},
}

SHIP = {
    "shipName": "Người nhận QA",
    "shipPhone": "0987654321",
    "shipAddress": "123 Đường QA, Phường 1, TP.HCM",
}


def _listing(client, seller, **overrides):
    response = client.post(
        "/api/v1/listings", headers=seller["headers"], json={**LISTING, **overrides}
    )
    assert response.status_code == 201, response.text
    listing = response.json()["listing"]
    with SessionLocal() as db:
        db.execute(
            update(Listing)
            .where(Listing.id == listing["id"])
            .values(status="ACTIVE", views=7)
        )
        db.commit()
    return listing


def _deposited_order(client, buyer, listing_id):
    order = client.post(
        "/api/v1/orders", headers=buyer["headers"], json={"listingId": listing_id, **SHIP}
    )
    assert order.status_code == 201, order.text
    order_id = order.json()["id"]
    client.post("/api/v1/wallet/topup", headers=buyer["headers"], json={"amount": 1_000_000})
    deposit = client.post(
        f"/api/v1/escrow/orders/{order_id}/deposit", headers=buyer["headers"], json={}
    )
    assert deposit.status_code == 201, deposit.text
    with SessionLocal() as db:
        # Đặt cọc giữ tin ở RESERVED; trả về ACTIVE để kiểm tra thống kê tin đang bán.
        db.execute(update(Listing).where(Listing.id == listing_id).values(status="ACTIVE"))
        db.commit()
    return client.get(f"/api/v1/orders/{order_id}", headers=buyer["headers"]).json()


def test_dashboard_nguoi_ban(make_user, client):
    seller = make_user(["SELLER"], verified=True)
    buyer = make_user(verified=True)
    listing = _listing(client, seller)
    order = _deposited_order(client, buyer, listing["id"])

    dashboard = client.get("/api/v1/seller/dashboard", headers=seller["headers"])
    assert dashboard.status_code == 200, dashboard.text
    payload = dashboard.json()

    assert payload["kpis"] == {
        "activeListings": 1,
        "pendingOrders": 1,
        "totalViews": 7,
        "weeklyRevenue": 0,
        "escrowHeld": order["escrow"]["amount"],
        "orderValue": order["totalAmount"],
    }
    assert {"status": "ACTIVE", "_count": 1} in payload["listingStatus"]

    assert payload["recentOrders"][0]["id"] == order["id"]
    assert payload["recentOrders"][0]["buyer"]["fullName"] == "Tài khoản QA"
    assert payload["recentOrders"][0]["listing"]["title"] == LISTING["title"]
    assert isinstance(payload["recentActivities"], list)

    top = payload["topProducts"][0]
    assert top == {
        "id": listing["id"],
        "title": LISTING["title"],
        "price": 500_000,
        "views": 7,
        "orders": 1,
        "image": LISTING["images"][0],
    }


def test_tin_dang_va_bieu_do_cua_nguoi_ban(make_user, client):
    seller = make_user(["SELLER"], verified=True)
    other_seller = make_user(["SELLER"], verified=True)
    buyer = make_user(verified=True)
    listing = _listing(client, seller)
    _deposited_order(client, buyer, listing["id"])

    listed = client.get("/api/v1/seller/listings", headers=seller["headers"]).json()
    assert listed["meta"]["total"] == 1
    item = listed["data"][0]
    assert item["id"] == listing["id"]
    assert item["images"][0]["url"] == LISTING["images"][0]
    assert item["category"] == {"name": "Điện tử cũ"}
    assert item["_count"] == {"orders": 1}

    filtered = client.get(
        "/api/v1/seller/listings",
        headers=seller["headers"],
        params={"status": "ACTIVE", "q": "Máy ảnh"},
    ).json()
    assert filtered["meta"]["total"] == 1
    assert client.get(
        "/api/v1/seller/listings", headers=seller["headers"], params={"q": "không có"}
    ).json()["meta"]["total"] == 0

    detail = client.get(f"/api/v1/seller/listings/{listing['id']}", headers=seller["headers"])
    assert detail.status_code == 200
    assert [image["url"] for image in detail.json()["images"]] == LISTING["images"]
    assert detail.json()["category"]["slug"] == "dien-tu-cu"

    assert client.get(
        f"/api/v1/seller/listings/{listing['id']}", headers=other_seller["headers"]
    ).status_code == 404

    chart = client.get("/api/v1/seller/charts/revenue", headers=seller["headers"]).json()
    assert chart["basis"] == "NET_WALLET_INCOME"
    assert chart["data"][-1]["orders"] == 1

    assert client.get("/api/v1/seller/dashboard", headers=buyer["headers"]).status_code == 403
