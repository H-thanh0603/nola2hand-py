"""Test tích hợp nhóm 4: trả hàng, tranh chấp, báo cáo vi phạm, đánh giá."""
from datetime import datetime, timedelta

from sqlalchemy import select, update

from app.db import SessionLocal
from app.models import (
    Listing,
    Notification,
    Order,
    OrderTimeline,
    Report,
    SellerProfile,
    User,
)

LISTING = {
    "categoryId": 1,
    "title": "Laptop QA còn bảo hành",
    "description": "Mô tả đủ dài cho tin đăng thử nghiệm, vượt qua giới hạn hai mươi ký tự.",
    "price": 500_000,
    "condition": "USED_GOOD",
    "city": "TP.HCM",
    "images": ["https://cdn.example.com/qa-1.jpg"],
    "specifications": {"brand": "Dell", "warranty": "6 tháng"},
}

SHIP = {
    "shipName": "Người nhận QA",
    "shipPhone": "0987654321",
    "shipAddress": "123 Đường QA, Phường 1, TP.HCM",
}


def _seller(make_user, client):
    seller = make_user(verified=True)
    response = client.post(
        "/api/v1/users/me/become-seller", headers=seller["headers"], json={"shopName": "Shop QA"}
    )
    assert response.status_code == 201, response.text
    return seller


def _listing(client, seller):
    response = client.post("/api/v1/listings", headers=seller["headers"], json=LISTING)
    assert response.status_code == 201, response.text
    listing = response.json()["listing"]
    with SessionLocal() as db:
        db.execute(update(Listing).where(Listing.id == listing["id"]).values(status="ACTIVE"))
        db.commit()
    return listing


def _order(client, buyer, listing_id):
    response = client.post(
        "/api/v1/orders", headers=buyer["headers"], json={"listingId": listing_id, **SHIP}
    )
    assert response.status_code == 201, response.text
    return response.json()


def _topup(client, user, amount=1_000_000):
    response = client.post("/api/v1/wallet/topup", headers=user["headers"], json={"amount": amount})
    assert response.status_code == 200, response.text


def _wallet(client, user):
    return client.get("/api/v1/wallet", headers=user["headers"]).json()["balance"]


def _deposit(client, buyer, order_id):
    response = client.post(
        f"/api/v1/escrow/orders/{order_id}/deposit", headers=buyer["headers"], json={}
    )
    assert response.status_code == 201, response.text


def _move(client, seller, order_id, status, **extra):
    response = client.patch(
        f"/api/v1/orders/{order_id}/status",
        headers=seller["headers"],
        json={"to": status, **extra},
    )
    assert response.status_code == 200, response.text


def _delivered_order(client, make_user):
    seller = _seller(make_user, client)
    buyer = make_user(verified=True)
    listing = _listing(client, seller)
    order = _order(client, buyer, listing["id"])
    _topup(client, buyer)
    _deposit(client, buyer, order["id"])
    _move(client, seller, order["id"], "CONFIRMED")
    _move(client, seller, order["id"], "SHIPPING", trackingCode="GHN-QA-1")
    _move(client, seller, order["id"], "DELIVERED")
    return seller, buyer, listing, order


def test_tra_hang_day_du_den_khi_hoan_tien(make_user, client):
    seller, buyer, listing, order = _delivered_order(client, make_user)
    admin = make_user(["ADMIN_FINANCE"])

    created = client.post(
        f"/api/v1/returns/orders/{order['id']}",
        headers=buyer["headers"],
        json={"reason": "Sản phẩm bị lỗi nguồn, không lên hình", "evidences": []},
    )
    assert created.status_code == 201, created.text
    request_id = created.json()["id"]
    assert created.json()["status"] == "REQUESTED"
    assert created.json()["refundAmount"] == 103_000
    assert created.json()["originalOrderStatus"] == "DELIVERED"

    with SessionLocal() as db:
        assert db.get(Order, order["id"]).status == "DISPUTED"

    again = client.post(
        f"/api/v1/returns/orders/{order['id']}",
        headers=buyer["headers"],
        json={"reason": "Gửi lại yêu cầu lần hai", "evidences": []},
    )
    assert again.status_code == 409

    listed = client.get("/api/v1/returns", headers=buyer["headers"]).json()
    assert listed["data"][0]["order"]["listing"]["images"][0]["url"] == LISTING["images"][0]
    assert listed["data"][0]["order"]["seller"]["fullName"] == "Tài khoản QA"

    missing_note = client.patch(
        f"/api/v1/returns/{request_id}", headers=seller["headers"], json={"action": "APPROVE"}
    )
    assert missing_note.status_code == 400
    assert missing_note.json()["message"] == "Cần lý do hoặc ghi chú cho bước xử lý"

    approved = client.patch(
        f"/api/v1/returns/{request_id}",
        headers=seller["headers"],
        json={"action": "APPROVE", "note": "Đồng ý nhận lại hàng"},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "APPROVED"
    assert approved.json()["fundingSource"] == "ESCROW"

    shipped = client.patch(
        f"/api/v1/returns/{request_id}",
        headers=buyer["headers"],
        json={"action": "SHIP", "trackingCode": "GHN-RETURN-1"},
    )
    assert shipped.status_code == 200, shipped.text
    assert shipped.json()["status"] == "SHIPPED"

    received = client.patch(
        f"/api/v1/returns/{request_id}",
        headers=seller["headers"],
        json={"action": "RECEIVE", "note": "Đã nhận lại máy, đúng serial"},
    )
    assert received.status_code == 200, received.text
    assert received.json()["status"] == "RECEIVED"

    not_admin = client.patch(
        f"/api/v1/returns/{request_id}",
        headers=seller["headers"],
        json={"action": "REFUND", "note": "Tự hoàn"},
    )
    assert not_admin.status_code == 403

    refunded = client.patch(
        f"/api/v1/returns/{request_id}",
        headers=admin["headers"],
        json={"action": "REFUND", "note": "Đã kiểm tra, hoàn tiền"},
    )
    assert refunded.status_code == 200, refunded.text
    assert refunded.json()["status"] == "REFUNDED"
    assert refunded.json()["refundedAt"].endswith("Z")

    assert _wallet(client, buyer) == 1_000_000
    with SessionLocal() as db:
        assert db.get(Order, order["id"]).status == "REFUNDED"
        assert db.get(Listing, listing["id"]).status == "HIDDEN"

    admin_list = client.get("/api/v1/returns/admin", headers=admin["headers"]).json()
    assert admin_list["data"][0]["id"] == request_id


def test_tra_hang_bi_tu_choi_va_het_han(make_user, client):
    seller, buyer, _listing_row, order = _delivered_order(client, make_user)

    created = client.post(
        f"/api/v1/returns/orders/{order['id']}",
        headers=buyer["headers"],
        json={"reason": "Hàng không đúng mô tả như đăng bán"},
    )
    assert created.status_code == 201
    request_id = created.json()["id"]

    rejected = client.patch(
        f"/api/v1/returns/{request_id}",
        headers=seller["headers"],
        json={"action": "REJECT", "note": "Máy vẫn hoạt động bình thường"},
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["status"] == "REJECTED"
    with SessionLocal() as db:
        assert db.get(Order, order["id"]).status == "DELIVERED"

    second_seller, second_buyer, _second_listing, second_order = _delivered_order(client, make_user)
    with SessionLocal() as db:
        db.execute(
            update(OrderTimeline)
            .where(
                OrderTimeline.orderId == second_order["id"],
                OrderTimeline.status == "DELIVERED",
            )
            .values(createdAt=datetime.utcnow() - timedelta(days=8))
        )
        db.commit()

    expired = client.post(
        f"/api/v1/returns/orders/{second_order['id']}",
        headers=second_buyer["headers"],
        json={"reason": "Đã quá hạn bảy ngày kể từ khi nhận"},
    )
    assert expired.status_code == 400
    assert expired.json()["message"] == "Hết thời hạn 7 ngày yêu cầu trả hàng"


def test_mo_tranh_chap_va_cac_ket_cuc(make_user, client):
    admin = make_user(["ADMIN_FINANCE"])

    # BUYER_WINS
    seller, buyer, listing, order = _delivered_order(client, make_user)
    opened = client.post(
        f"/api/v1/disputes/orders/{order['id']}/disputes",
        headers=buyer["headers"],
        json={
            "reason": "Hàng giả",
            "description": "Máy nhận được không đúng mô tả và không bật được nguồn.",
        },
    )
    assert opened.status_code == 201, opened.text
    dispute = opened.json()["dispute"]
    assert dispute["amount"] == 103_000
    assert opened.json()["message"].startswith("Đã mở tranh chấp")

    duplicate = client.post(
        f"/api/v1/disputes/orders/{order['id']}/disputes",
        headers=buyer["headers"],
        json={"reason": "Mở lại", "description": "Tranh chấp thứ hai cho cùng một đơn."},
    )
    assert duplicate.status_code in (400, 409)

    mine = client.get("/api/v1/disputes/mine", headers=buyer["headers"]).json()
    assert mine[0]["order"]["code"] == order["code"]
    assert mine[0]["evidences"] == []

    resolved = client.patch(
        f"/api/v1/disputes/admin/{dispute['id']}/resolve",
        headers=admin["headers"],
        json={"decision": "BUYER_WINS", "resolution": "Ảnh bằng chứng khớp, hoàn toàn bộ"},
    )
    assert resolved.status_code == 200, resolved.text
    assert resolved.json() == {"message": "Đã xử lý tranh chấp"}
    assert _wallet(client, buyer) == 1_000_000
    with SessionLocal() as db:
        assert db.get(Order, order["id"]).status == "REFUNDED"
        assert db.get(Listing, listing["id"]).status == "HIDDEN"

    # SPLIT
    split_seller, split_buyer, _split_listing, split_order = _delivered_order(client, make_user)
    split_dispute = client.post(
        f"/api/v1/disputes/orders/{split_order['id']}/disputes",
        headers=split_buyer["headers"],
        json={"reason": "Trầy xước", "description": "Máy bị trầy nhẹ, hai bên chưa thống nhất."},
    ).json()["dispute"]
    client.patch(
        f"/api/v1/disputes/admin/{split_dispute['id']}/resolve",
        headers=admin["headers"],
        json={"decision": "SPLIT", "resolution": "Mỗi bên chịu một nửa"},
    )
    assert _wallet(client, split_buyer) == 897_000 + 51_500
    assert _wallet(client, split_seller) == 51_500 - 12_500

    # SELLER_WINS
    win_seller, win_buyer, _win_listing, win_order = _delivered_order(client, make_user)
    win_dispute = client.post(
        f"/api/v1/disputes/orders/{win_order['id']}/disputes",
        headers=win_buyer["headers"],
        json={"reason": "Đổi ý", "description": "Người mua đổi ý sau khi đã nhận hàng."},
    ).json()["dispute"]
    client.patch(
        f"/api/v1/disputes/admin/{win_dispute['id']}/resolve",
        headers=admin["headers"],
        json={"decision": "SELLER_WINS", "resolution": "Hàng đúng mô tả"},
    )
    assert _wallet(client, win_seller) == 103_000 - 25_000
    with SessionLocal() as db:
        assert db.get(Order, win_order["id"]).status == "COMPLETED"

    # REJECT
    rej_seller, rej_buyer, _rej_listing, rej_order = _delivered_order(client, make_user)
    rej_dispute = client.post(
        f"/api/v1/disputes/orders/{rej_order['id']}/disputes",
        headers=rej_buyer["headers"],
        json={"reason": "Khiếu nại sai", "description": "Người mua khiếu nại không có căn cứ."},
    ).json()["dispute"]
    client.patch(
        f"/api/v1/disputes/admin/{rej_dispute['id']}/resolve",
        headers=admin["headers"],
        json={"decision": "REJECT", "resolution": "Không đủ căn cứ"},
    )
    with SessionLocal() as db:
        assert db.get(Order, rej_order["id"]).status == "SHIPPING"

    admin_list = client.get(
        "/api/v1/disputes/admin/all", headers=admin["headers"], params={"status": "REFUNDED"}
    ).json()
    assert admin_list["meta"]["total"] >= 2
    assert admin_list["data"][0]["buyer"]["fullName"] == "Tài khoản QA"


def test_bao_cao_vi_pham_va_xu_ly(make_user, client):
    admin = make_user(["ADMIN_CONTENT"])
    seller, buyer, listing, _order_row = _delivered_order(client, make_user)

    created = client.post(
        "/api/v1/reports",
        headers=buyer["headers"],
        json={
            "targetType": "LISTING",
            "targetId": listing["id"],
            "targetUserId": seller["id"],
            "reason": "Hàng giả",
            "description": "Tin đăng bán hàng giả, có ảnh chụp màn hình.",
        },
    )
    assert created.status_code == 201, created.text
    report_id = created.json()["report"]["id"]

    invalid = client.get(
        "/api/v1/reports/admin/all", headers=admin["headers"], params={"status": "SAI"}
    )
    assert invalid.status_code == 400

    listed = client.get(
        "/api/v1/reports/admin/all", headers=admin["headers"], params={"status": "NEW"}
    ).json()
    assert listed["data"][0]["reporter"]["fullName"] == "Tài khoản QA"
    assert listed["data"][0]["handler"] is None

    stats = client.get("/api/v1/reports/admin/stats", headers=admin["headers"]).json()
    assert stats["new"] >= 1

    handled = client.patch(
        f"/api/v1/reports/admin/{report_id}",
        headers=admin["headers"],
        json={"status": "RESOLVED", "resolution": "Đã xác minh", "action": "WARN_USER"},
    )
    assert handled.status_code == 200, handled.text
    assert handled.json()["status"] == "RESOLVED"
    assert handled.json()["handlerId"] == admin["id"]

    with SessionLocal() as db:
        warned = db.execute(
            select(Notification).where(
                Notification.userId == seller["id"], Notification.type == "REPORT"
            )
        ).scalars().all()
        assert warned

    removed = client.post(
        "/api/v1/reports",
        headers=buyer["headers"],
        json={
            "targetType": "LISTING",
            "targetId": listing["id"],
            "targetUserId": seller["id"],
            "reason": "Ảnh sai sự thật",
        },
    ).json()["report"]["id"]
    client.patch(
        f"/api/v1/reports/admin/{removed}",
        headers=admin["headers"],
        json={"status": "RESOLVED", "action": "REMOVE_CONTENT"},
    )
    with SessionLocal() as db:
        assert db.get(Listing, listing["id"]).status == "HIDDEN"

    offender = make_user()
    banned = client.post(
        "/api/v1/reports",
        headers=buyer["headers"],
        json={
            "targetType": "AVATAR",
            "targetId": 1,
            "targetUserId": offender["id"],
            "reason": "Ảnh phản cảm",
        },
    ).json()["report"]["id"]
    client.patch(
        f"/api/v1/reports/admin/{banned}",
        headers=admin["headers"],
        json={"status": "RESOLVED", "action": "BAN_7_DAYS", "resolution": "Khóa 7 ngày"},
    )
    with SessionLocal() as db:
        row = db.get(User, offender["id"])
        assert row.status == "BANNED"
        assert "khóa 7 ngày" in row.banReason
    assert client.get("/api/v1/auth/me", headers=offender["headers"]).status_code == 401


def test_danh_gia_va_thong_ke(make_user, client):
    seller, buyer, listing, order = _delivered_order(client, make_user)
    with SessionLocal() as db:
        db.execute(
            update(Order).where(Order.id == order["id"]).values(status="COMPLETED")
        )
        db.commit()

    pending = client.get("/api/v1/reviews/mine/pending", headers=buyer["headers"]).json()
    assert [row["id"] for row in pending] == [order["id"]]
    assert pending[0]["listing"]["images"][0]["url"] == LISTING["images"][0]

    wrong_listing = client.post(
        f"/api/v1/reviews/orders/{order['id']}/reviews",
        headers=buyer["headers"],
        json={"rating": 5, "listingId": 999_999},
    )
    assert wrong_listing.status_code == 400

    created = client.post(
        f"/api/v1/reviews/orders/{order['id']}/reviews",
        headers=buyer["headers"],
        json={"rating": 5, "comment": "Rất tốt, giao nhanh như mô tả", "type": "SELLER"},
    )
    assert created.status_code == 201, created.text
    review = created.json()["review"]
    assert review["sentiment"] == "POSITIVE"
    assert review["sentimentSource"] == "LOCAL"
    assert review["listingId"] is None

    with SessionLocal() as db:
        profile = db.execute(
            select(SellerProfile).where(SellerProfile.userId == seller["id"])
        ).scalar_one()
        assert profile.rating == 5
        assert profile.totalReviews == 1

    assert client.post(
        f"/api/v1/reviews/orders/{order['id']}/reviews",
        headers=buyer["headers"],
        json={"rating": 4},
    ).status_code == 400

    assert client.get("/api/v1/reviews/mine/pending", headers=buyer["headers"]).json() == []

    replies = client.post(
        f"/api/v1/reviews/{review['id']}/reply",
        headers=seller["headers"],
        json={"reply": "Cảm ơn bạn đã ủng hộ shop"},
    )
    assert replies.status_code == 200, replies.text
    assert replies.json()["sellerReply"] == "Cảm ơn bạn đã ủng hộ shop"

    listed = client.get(f"/api/v1/reviews/users/{seller['id']}").json()
    assert listed["meta"]["total"] == 1
    assert listed["data"][0]["reviewer"]["id"] == buyer["id"]
    assert listed["ratingStats"] == [{"rating": 5, "_count": 1}]

    insights = client.get("/api/v1/reviews/insights", headers=seller["headers"]).json()
    assert insights["sampleSize"] == 1
    assert insights["averageRating"] == 5
    assert insights["sources"] == {"ai": 0, "local": 1}
    assert [row["sentiment"] for row in insights["sentiments"]] == [
        "POSITIVE",
        "NEUTRAL",
        "NEGATIVE",
    ]

    admin = make_user(["ADMIN_CONTENT"])
    all_insights = client.get("/api/v1/reviews/insights", headers=admin["headers"]).json()
    assert all_insights["sampleSize"] >= 1
    bad = client.get(
        "/api/v1/reviews/insights", headers=admin["headers"], params={"userId": "abc"}
    )
    assert bad.status_code == 400


def test_chua_hoan_tat_thi_khong_danh_gia_duoc(make_user, client):
    seller = _seller(make_user, client)
    buyer = make_user(verified=True)
    listing = _listing(client, seller)
    order = _order(client, buyer, listing["id"])

    blocked = client.post(
        f"/api/v1/reviews/orders/{order['id']}/reviews",
        headers=buyer["headers"],
        json={"rating": 5},
    )
    assert blocked.status_code == 400
    assert blocked.json()["message"] == "Chỉ đánh giá khi đơn đã hoàn tất"

    other = make_user(verified=True)
    wrong = client.post(
        f"/api/v1/reviews/orders/{order['id']}/reviews",
        headers=other["headers"],
        json={"rating": 5},
    )
    assert wrong.status_code == 403
