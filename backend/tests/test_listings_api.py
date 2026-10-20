"""Test tích hợp listings.js — đăng tin, duyệt, yêu thích, trả giá, đẩy tin."""
from sqlalchemy import select

from app.db import SessionLocal
from app.models import FeeConfig, Listing, ListingImage, Notification, PriceHistory, SavedSearch, Wallet

PAYLOAD = {
    "categoryId": 1,
    "title": "Tai nghe QA chính hãng còn bảo hành",
    "description": "Mô tả đủ dài cho tin đăng thử nghiệm, vượt qua giới hạn hai mươi ký tự.",
    "price": 500000,
    "condition": "USED_GOOD",
    "city": "TP.HCM",
    "images": ["https://cdn.example.com/qa-1.jpg"],
    "specifications": {"brand": "Sony", "batteryHealth": "90", "warranty": "6 tháng"},
}


def _create_listing(client, seller, **overrides):
    response = client.post("/api/v1/listings", headers=seller["headers"], json={**PAYLOAD, **overrides})
    assert response.status_code == 201, response.text
    return response.json()["listing"]


def test_tao_tin_can_xac_minh_va_role(make_user, client):
    buyer = make_user()
    response = client.post("/api/v1/listings", headers=buyer["headers"], json=PAYLOAD)
    assert response.status_code == 403
    assert response.json() == {"message": "Bạn không có quyền thực hiện thao tác này"}

    seller = make_user(roles=["SELLER"])  # chưa xác nhận email/danh tính
    response = client.post("/api/v1/listings", headers=seller["headers"], json=PAYLOAD)
    assert response.status_code == 403
    assert response.json() == {"message": "Hãy xác nhận email hoặc danh tính trước khi đặt hàng/đăng tin."}


def test_tao_tin_va_khoi_tao_anh_lich_su_gia(make_user, client):
    seller = make_user(roles=["SELLER"], verified=True)
    listing = _create_listing(client, seller)

    assert listing["status"] == "PENDING_REVIEW"
    assert listing["sellerId"] == seller["id"]
    assert listing["price"] == 500000
    assert [image["url"] for image in listing["images"]] == ["https://cdn.example.com/qa-1.jpg"]
    assert listing["category"]["id"] == 1
    assert listing["seller"]["id"] == seller["id"]
    assert listing["_count"] == {"favorites": 0}

    with SessionLocal() as db:
        images = db.execute(
            select(ListingImage).where(ListingImage.listingId == listing["id"])
        ).scalars().all()
        assert [(image.url, image.sortOrder) for image in images] == [("https://cdn.example.com/qa-1.jpg", 0)]
        history = db.execute(
            select(PriceHistory).where(PriceHistory.listingId == listing["id"])
        ).scalars().all()
        assert [row.price for row in history] == [500000]


def test_thong_so_khong_hop_le(make_user, client):
    seller = make_user(roles=["SELLER"], verified=True)
    unknown = client.post(
        "/api/v1/listings",
        headers=seller["headers"],
        json={**PAYLOAD, "specifications": {"khongCo": "x"}},
    )
    assert unknown.status_code == 400
    assert unknown.json() == {"message": "Thông số sản phẩm không hợp lệ"}

    bad_number = client.post(
        "/api/v1/listings",
        headers=seller["headers"],
        json={**PAYLOAD, "specifications": {"batteryHealth": "120"}},
    )
    assert bad_number.status_code == 400
    assert bad_number.json() == {"message": "Thông số số học không hợp lệ"}

    missing_image = client.post(
        "/api/v1/listings", headers=seller["headers"], json={**PAYLOAD, "images": []}
    )
    assert missing_image.status_code == 400
    assert missing_image.json()["details"][0]["message"] == "Cần ít nhất 1 hình ảnh"


def test_sua_tin_dua_ve_cho_duyet_va_ghi_lich_su_gia(make_user, client):
    seller = make_user(roles=["SELLER"], verified=True)
    listing = _create_listing(client, seller)

    response = client.patch(
        f"/api/v1/listings/{listing['id']}",
        headers=seller["headers"],
        json={"title": "Tai nghe QA đã giảm giá sốc", "price": 450000},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["title"] == "Tai nghe QA đã giảm giá sốc"
    assert body["price"] == 450000
    assert body["status"] == "PENDING_REVIEW"

    with SessionLocal() as db:
        prices = db.execute(
            select(PriceHistory.price)
            .where(PriceHistory.listingId == listing["id"])
            .order_by(PriceHistory.id)
        ).scalars().all()
        assert prices == [500000, 450000]

    # người khác không sửa được
    other = make_user(roles=["SELLER"], verified=True)
    denied = client.patch(
        f"/api/v1/listings/{listing['id']}", headers=other["headers"], json={"price": 1000}
    )
    assert denied.status_code == 404


def test_duyet_tin_va_an_hien_xoa(make_user, client):
    admin = make_user(roles=["ADMIN_CONTENT"])
    seller = make_user(roles=["SELLER"], verified=True)
    listing = _create_listing(client, seller)

    hidden = client.patch(
        f"/api/v1/listings/{listing['id']}/visibility",
        headers=seller["headers"],
        json={"status": "HIDDEN"},
    )
    assert hidden.status_code == 400
    assert hidden.json() == {"message": "Chỉ có thể ẩn hoặc hiện tin đã được duyệt"}

    approved = client.patch(
        f"/api/v1/listings/admin/{listing['id']}/moderate",
        headers=admin["headers"],
        json={"action": "APPROVE"},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "ACTIVE"
    assert client.get(f"/api/v1/listings/{listing['id']}").status_code == 200

    hidden = client.patch(
        f"/api/v1/listings/{listing['id']}/visibility",
        headers=seller["headers"],
        json={"status": "HIDDEN"},
    )
    assert hidden.json() == {"id": listing["id"], "status": "HIDDEN"}
    assert client.get(f"/api/v1/listings/{listing['id']}").status_code == 404

    deleted = client.delete(f"/api/v1/listings/{listing['id']}", headers=seller["headers"])
    assert deleted.json() == {"message": "Đã xoá tin đăng"}
    with SessionLocal() as db:
        assert db.execute(select(Listing.status).where(Listing.id == listing["id"])).scalar_one() == "DELETED"


def test_tu_choi_tin_va_chong_duyet_lai(make_user, client):
    admin = make_user(roles=["ADMIN_CONTENT"])
    seller = make_user(roles=["SELLER"], verified=True)
    listing = _create_listing(client, seller)

    rejected = client.patch(
        f"/api/v1/listings/admin/{listing['id']}/moderate",
        headers=admin["headers"],
        json={"action": "REJECT", "reason": "Ảnh mờ"},
    )
    assert rejected.json()["status"] == "REJECTED"
    assert rejected.json()["rejectReason"] == "Ảnh mờ"

    twice = client.patch(
        f"/api/v1/listings/admin/{listing['id']}/moderate",
        headers=admin["headers"],
        json={"action": "APPROVE"},
    )
    assert twice.status_code == 409
    assert twice.json() == {"message": "Chỉ duyệt tin đang chờ kiểm duyệt"}


def test_duyet_tin_bao_cho_tim_kiem_da_luu(make_user, client):
    admin = make_user(roles=["ADMIN_CONTENT"])
    seller = make_user(roles=["SELLER"], verified=True)
    watcher = make_user()

    with SessionLocal() as db:
        search = SavedSearch(userId=watcher["id"], name="Tai nghe QA", filters={})
        db.add(search)
        db.commit()
        search_id = search.id

    listing = _create_listing(client, seller)
    approved = client.patch(
        f"/api/v1/listings/admin/{listing['id']}/moderate",
        headers=admin["headers"],
        json={"action": "APPROVE"},
    )
    assert approved.status_code == 200

    with SessionLocal() as db:
        notifications = db.execute(
            select(Notification).where(Notification.userId == watcher["id"])
        ).scalars().all()
        assert [(n.type, n.title) for n in notifications] == [
            ("SAVED_SEARCH", "Tin mới cho “Tai nghe QA”")
        ]
        assert notifications[0].data == {"listingId": listing["id"], "searchId": search_id}


def test_loc_tin_va_khoang_gia_sai(client):
    response = client.get("/api/v1/listings", params={"categoryId": 1, "minPrice": 100000, "maxPrice": 900000})
    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["limit"] == 20
    for item in body["data"]:
        assert item["categoryId"] == 1
        assert 100000 <= item["price"] <= 900000
        assert item["status"] == "ACTIVE"

    bad = client.get("/api/v1/listings", params={"minPrice": 900000, "maxPrice": 100000})
    assert bad.status_code == 400
    assert bad.json()["details"] == [{"field": "maxPrice", "message": "Khoảng giá không hợp lệ"}]

    invalid = client.get("/api/v1/listings", params={"categoryId": "abc"})
    assert invalid.status_code == 400
    assert invalid.json()["message"] == "Dữ liệu không hợp lệ"


def test_sap_xep_theo_gia(client):
    body = client.get("/api/v1/listings", params={"sort": "price_asc", "limit": 50}).json()
    prices = [item["price"] for item in body["data"]]
    assert prices == sorted(prices)

    newest = client.get("/api/v1/listings", params={"sort": "newest", "limit": 5}).json()
    created = [item["createdAt"] for item in newest["data"]]
    assert created == sorted(created, reverse=True)


def test_chi_tiet_tang_luot_xem(client):
    listing_id = client.get("/api/v1/listings", params={"limit": 1}).json()["data"][0]["id"]
    first = client.get(f"/api/v1/listings/{listing_id}").json()
    second = client.get(f"/api/v1/listings/{listing_id}").json()
    assert second["views"] == first["views"] + 1
    assert first["images"] is not None


def test_so_sanh_tin(client):
    ids = [item["id"] for item in client.get("/api/v1/listings", params={"limit": 2}).json()["data"]]
    response = client.get("/api/v1/listings/compare", params={"ids": f"{ids[0]},{ids[1]}"}).json()
    assert [item["id"] for item in response["items"]] == ids
    assert response["unavailable"] == []
    assert isinstance(response["items"][0]["priceHistory"], list)

    duplicated = client.get("/api/v1/listings/compare", params={"ids": f"{ids[0]},{ids[0]}"})
    assert duplicated.status_code == 400
    assert duplicated.json() == {"message": "Không chọn trùng sản phẩm"}

    with_missing = client.get("/api/v1/listings/compare", params={"ids": f"{ids[0]},99999999"}).json()
    assert with_missing["unavailable"] == [99999999]


def test_yeu_thich_bat_tat(make_user, client):
    buyer = make_user()
    listing_id = client.get("/api/v1/listings", params={"limit": 1}).json()["data"][0]["id"]

    assert client.post(f"/api/v1/listings/{listing_id}/favorite", headers=buyer["headers"]).json() == {
        "favorited": True
    }
    favorites = client.get("/api/v1/listings/me/favorites", headers=buyer["headers"]).json()
    assert favorites["meta"]["total"] == 1
    assert favorites["data"][0]["listing"]["id"] == listing_id

    assert client.post(f"/api/v1/listings/{listing_id}/favorite", headers=buyer["headers"]).json() == {
        "favorited": False
    }
    assert client.get(
        "/api/v1/listings/me/favorites", headers=buyer["headers"]
    ).json()["meta"]["total"] == 0


def test_tra_gia(make_user, client):
    seller = make_user(roles=["SELLER"], verified=True)
    buyer = make_user(verified=True)
    listing = _create_listing(client, seller)
    client.patch(
        f"/api/v1/listings/admin/{listing['id']}/moderate",
        headers=make_user(roles=["ADMIN_CONTENT"])["headers"],
        json={"action": "APPROVE"},
    )

    own = client.post(
        f"/api/v1/listings/{listing['id']}/offers",
        headers=seller["headers"],
        json={"offeredPrice": 100000},
    )
    assert own.status_code == 400
    assert own.json() == {"message": "Không thể trả giá tin của chính mình"}

    too_high = client.post(
        f"/api/v1/listings/{listing['id']}/offers",
        headers=buyer["headers"],
        json={"offeredPrice": 500000},
    )
    assert too_high.status_code == 400
    assert too_high.json() == {"message": "Giá đề xuất phải thấp hơn giá niêm yết"}

    offer = client.post(
        f"/api/v1/listings/{listing['id']}/offers",
        headers=buyer["headers"],
        json={"offeredPrice": 400000, "message": "Bớt chút nhé"},
    )
    assert offer.status_code == 201, offer.text
    body = offer.json()
    assert body["message"] == "Đã gửi yêu cầu, hiệu lực 24 giờ"
    assert body["offer"]["offeredPrice"] == 400000
    assert body["offer"]["listing"] == {"title": listing["title"]}
    assert body["offer"]["buyer"] == {"fullName": "Tài khoản QA"}

    with SessionLocal() as db:
        offers = db.execute(
            select(Notification).where(
                Notification.userId == seller["id"], Notification.type == "OFFER"
            )
        ).scalars().all()
        assert offers[0].body == f'Tài khoản QA trả giá 400.000đ cho "{listing["title"]}"'


def test_day_tin_tru_phi_vi(make_user, client):
    seller = make_user(roles=["SELLER"], verified=True)
    listing = _create_listing(client, seller)

    with SessionLocal() as db:
        wallet = db.execute(select(Wallet).where(Wallet.userId == seller["id"])).scalar_one()
        wallet.balance = 50000
        fee = db.execute(
            select(FeeConfig.amount).where(
                FeeConfig.name == "Phí đẩy tin", FeeConfig.isActive.is_(True)
            )
        ).scalars().first()
        db.commit()

    response = client.post(f"/api/v1/listings/{listing['id']}/boost", headers=seller["headers"])
    assert response.status_code == 200
    assert response.json() == {"message": "Đã đẩy tin 24h (phí 10.000đ)"}

    with SessionLocal() as db:
        wallet = db.execute(select(Wallet).where(Wallet.userId == seller["id"])).scalar_one()
        assert wallet.balance == 50000 - fee
        boosted = db.execute(select(Listing.boostedUntil).where(Listing.id == listing["id"])).scalar_one()
        assert boosted is not None


def test_day_tin_khi_vi_khong_du(make_user, client):
    seller = make_user(roles=["SELLER"], verified=True)
    listing = _create_listing(client, seller)
    response = client.post(f"/api/v1/listings/{listing['id']}/boost", headers=seller["headers"])
    assert response.status_code == 400
    assert response.json() == {"message": "Số dư ví không đủ"}


def test_danh_sach_cho_duyet_can_quyen_noi_dung(make_user, client):
    seller = make_user(roles=["SELLER"], verified=True)
    listing = _create_listing(client, seller)

    assert client.get(
        "/api/v1/listings/admin/pending", headers=seller["headers"]
    ).status_code == 403

    admin = make_user(roles=["ADMIN_CONTENT"])
    body = client.get(
        "/api/v1/listings/admin/pending", headers=admin["headers"], params={"q": "Tai nghe QA"}
    ).json()
    assert any(item["id"] == listing["id"] for item in body["data"])
    assert all(item["status"] == "PENDING_REVIEW" for item in body["data"])
