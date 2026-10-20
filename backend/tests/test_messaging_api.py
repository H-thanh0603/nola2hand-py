"""Test tích hợp nhóm 5: chat, thông báo, theo dõi tìm kiếm, trợ lý tìm đồ."""
from sqlalchemy import select, update

from app.db import SessionLocal
from app.models import Listing, SavedSearch, SavedSearchMatch

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


def _listing(client, seller, **overrides):
    response = client.post(
        "/api/v1/listings", headers=seller["headers"], json={**LISTING, **overrides}
    )
    assert response.status_code == 201, response.text
    listing = response.json()["listing"]
    with SessionLocal() as db:
        db.execute(update(Listing).where(Listing.id == listing["id"]).values(status="ACTIVE"))
        db.commit()
    listing["status"] = "ACTIVE"
    return listing


def test_chat_gui_tin_hoi_thoai_va_chan(make_user, client):
    alice = make_user()
    bob = make_user(verified=True)
    seller = make_user(["SELLER"], verified=True)
    listing = _listing(client, seller)

    sent = client.post(
        "/api/v1/chat/messages",
        headers=alice["headers"],
        json={"receiverId": bob["id"], "body": "  Chào bạn, còn hàng không?  "},
    )
    assert sent.status_code == 201, sent.text
    message = sent.json()
    assert message["body"] == "Chào bạn, còn hàng không?"
    assert message["sender"] == {
        "id": alice["id"],
        "fullName": "Tài khoản QA",
        "avatarUrl": None,
    }

    inbox = client.get("/api/v1/notifications", headers=bob["headers"]).json()
    assert inbox["unreadCount"] == 1
    assert inbox["data"][0]["title"] == "Tin nhắn mới từ Tài khoản QA"
    assert inbox["data"][0]["data"] == {"senderId": alice["id"]}

    bob_view = client.get("/api/v1/chat/conversations", headers=bob["headers"]).json()
    assert len(bob_view) == 1
    assert bob_view[0]["user"]["id"] == alice["id"]
    assert bob_view[0]["lastMessage"] == "Chào bạn, còn hàng không?"
    assert bob_view[0]["listingId"] is None
    assert bob_view[0]["unread"] == 1

    alice_view = client.get("/api/v1/chat/conversations", headers=alice["headers"]).json()
    assert alice_view[0]["unread"] == 0

    history = client.get(
        f"/api/v1/chat/with/{alice['id']}", headers=bob["headers"]
    ).json()
    assert [row["id"] for row in history] == [message["id"]]
    assert client.get("/api/v1/chat/conversations", headers=bob["headers"]).json()[0]["unread"] == 0

    with_listing = client.post(
        "/api/v1/chat/messages",
        headers=bob["headers"],
        json={"receiverId": seller["id"], "body": "Tin còn không ạ?", "listingId": listing["id"]},
    )
    assert with_listing.status_code == 201
    filtered = client.get(
        f"/api/v1/chat/with/{bob['id']}",
        headers=seller["headers"],
        params={"listingId": listing["id"]},
    ).json()
    assert [row["body"] for row in filtered] == ["Tin còn không ạ?"]

    assert client.post(
        "/api/v1/chat/messages",
        headers=alice["headers"],
        json={"receiverId": alice["id"], "body": "Tự nhắn"},
    ).status_code == 400
    assert client.post(
        "/api/v1/chat/messages",
        headers=alice["headers"],
        json={"receiverId": 999_999, "body": "Người lạ"},
    ).status_code == 404
    assert client.post(
        "/api/v1/chat/messages",
        headers=alice["headers"],
        json={"receiverId": bob["id"], "body": "   "},
    ).status_code == 400

    order = client.post(
        "/api/v1/orders", headers=bob["headers"], json={"listingId": listing["id"], **SHIP}
    )
    assert order.status_code == 201, order.text
    order_id = order.json()["id"]

    wrong_pair = client.post(
        "/api/v1/chat/messages",
        headers=alice["headers"],
        json={"receiverId": bob["id"], "body": "Hỏi về đơn", "orderId": order_id},
    )
    assert wrong_pair.status_code == 403

    valid_pair = client.post(
        "/api/v1/chat/messages",
        headers=bob["headers"],
        json={"receiverId": seller["id"], "body": "Hỏi về đơn", "orderId": order_id},
    )
    assert valid_pair.status_code == 201

    blocked = client.post(f"/api/v1/chat/blocks/{alice['id']}", headers=bob["headers"])
    assert blocked.status_code == 200, blocked.text
    assert client.post(
        "/api/v1/chat/messages",
        headers=alice["headers"],
        json={"receiverId": bob["id"], "body": "Sau khi bị chặn"},
    ).status_code == 403

    blocks = client.get("/api/v1/chat/blocks", headers=bob["headers"]).json()
    assert [row["id"] for row in blocks] == [alice["id"]]

    assert client.post(f"/api/v1/chat/blocks/{bob['id']}", headers=bob["headers"]).status_code == 400
    assert client.post("/api/v1/chat/blocks/999999", headers=bob["headers"]).status_code == 404

    unblocked = client.delete(f"/api/v1/chat/blocks/{alice['id']}", headers=bob["headers"])
    assert unblocked.json() == {"message": "Đã bỏ chặn"}
    assert client.post(
        "/api/v1/chat/messages",
        headers=alice["headers"],
        json={"receiverId": bob["id"], "body": "Sau khi bỏ chặn"},
    ).status_code == 201


def test_thong_bao_doc_tung_cai_va_doc_tat_ca(make_user, client):
    owner = make_user()
    other = make_user()

    for index in range(3):
        client.post(
            "/api/v1/chat/messages",
            headers=other["headers"],
            json={"receiverId": owner["id"], "body": f"Tin số {index}"},
        )

    inbox = client.get("/api/v1/notifications", headers=owner["headers"]).json()
    assert inbox["meta"]["total"] == 3
    assert inbox["unreadCount"] == 3
    newest = inbox["data"][0]
    assert newest["body"] == "Tin số 2"

    unread_only = client.get(
        "/api/v1/notifications", headers=owner["headers"], params={"unread": "true"}
    ).json()
    assert unread_only["meta"]["total"] == 3

    read = client.patch(
        f"/api/v1/notifications/{newest['id']}/read", headers=owner["headers"]
    )
    assert read.status_code == 200
    assert read.json()["isRead"] is True
    assert client.get("/api/v1/notifications", headers=owner["headers"]).json()["unreadCount"] == 2

    assert client.patch(
        f"/api/v1/notifications/{newest['id']}/read", headers=other["headers"]
    ).status_code == 404

    all_read = client.patch("/api/v1/notifications/read-all", headers=owner["headers"])
    assert all_read.json() == {"message": "Đã đánh dấu đọc tất cả"}
    assert client.get("/api/v1/notifications", headers=owner["headers"]).json()["unreadCount"] == 0
    assert client.get(
        "/api/v1/notifications", headers=owner["headers"], params={"unread": "true"}
    ).json()["meta"]["total"] == 0


def test_theo_doi_tim_kiem(make_user, client):
    seller = make_user(["SELLER"], verified=True)
    listing = _listing(client, seller)
    buyer = make_user()

    created = client.post(
        "/api/v1/saved-searches",
        headers=buyer["headers"],
        json={"name": "Máy ảnh dưới 600k", "filters": {"q": "Máy ảnh", "maxPrice": 600_000, "page": 2}},
    )
    assert created.status_code == 201, created.text
    search = created.json()
    assert search["filters"] == {"q": "Máy ảnh", "maxPrice": 600_000}
    assert search["enabled"] is True

    with SessionLocal() as db:
        matches = db.execute(
            select(SavedSearchMatch.listingId).where(SavedSearchMatch.searchId == search["id"])
        ).scalars().all()
        assert matches == [listing["id"]]

    listed = client.get("/api/v1/saved-searches", headers=buyer["headers"]).json()
    assert [row["id"] for row in listed] == [search["id"]]

    toggled = client.patch(
        f"/api/v1/saved-searches/{search['id']}",
        headers=buyer["headers"],
        json={"enabled": False},
    )
    assert toggled.json() == {"message": "Đã cập nhật theo dõi"}
    with SessionLocal() as db:
        assert db.get(SavedSearch, search["id"]).enabled is False

    stranger = make_user()
    assert client.patch(
        f"/api/v1/saved-searches/{search['id']}",
        headers=stranger["headers"],
        json={"enabled": True},
    ).status_code == 404

    bad_range = client.post(
        "/api/v1/saved-searches",
        headers=buyer["headers"],
        json={"name": "Sai khoảng giá", "filters": {"minPrice": 900_000, "maxPrice": 100_000}},
    )
    assert bad_range.status_code == 400
    assert bad_range.json()["details"][0]["field"] == "maxPrice"

    with SessionLocal() as db:
        for index in range(20):
            db.add(SavedSearch(userId=buyer["id"], name=f"Đầy {index}", filters={}))
        db.commit()
    full = client.post(
        "/api/v1/saved-searches",
        headers=buyer["headers"],
        json={"name": "Cái thứ 21", "filters": {"q": "bất kỳ"}},
    )
    assert full.status_code == 400
    assert full.json()["message"] == "Tối đa 20 tìm kiếm theo dõi"

    removed = client.delete(
        f"/api/v1/saved-searches/{search['id']}", headers=buyer["headers"]
    )
    assert removed.json() == {"message": "Đã xóa theo dõi"}
    assert all(
        row["id"] != search["id"]
        for row in client.get("/api/v1/saved-searches", headers=buyer["headers"]).json()
    )


def test_tro_ly_tim_do_loc_tu_khoa(make_user, client):
    seller = make_user(["SELLER"], verified=True)
    listing = _listing(client, seller)

    found = client.post(
        "/api/v1/assistant",
        json={"message": "tôi cần máy ảnh dưới 1 triệu tại TP.HCM"},
    )
    assert found.status_code == 200, found.text
    payload = found.json()
    assert payload["mode"] == "LOCAL"
    assert payload["filters"] == {"q": "máy ảnh", "maxPrice": 1_000_000, "city": "TP.HCM"}
    assert [row["id"] for row in payload["items"]][0] == listing["id"]
    assert payload["items"][0]["images"][0]["url"] == LISTING["images"][0]
    assert payload["items"][0]["category"]["id"] == 1
    assert payload["message"].startswith("Tìm thấy 1 tin đang bán")
    assert payload["note"].startswith("Chế độ tìm kiếm từ khóa")

    no_budget = client.post("/api/v1/assistant", json={"message": "tìm laptop"})
    assert no_budget.json()["filters"] == {"q": "laptop"}

    assert client.post("/api/v1/assistant", json={"message": "a"}).status_code == 400


def test_tro_ly_gioi_han_10_luot_moi_phut(client):
    for _ in range(10):
        assert client.post("/api/v1/assistant", json={"message": "tìm đồ cũ"}).status_code == 200

    blocked = client.post("/api/v1/assistant", json={"message": "tìm đồ cũ"})
    assert blocked.status_code == 429
    assert blocked.json()["message"] == "Too many requests, please try again later."
