"""Test tích hợp nhóm tiền: trả giá, đơn hàng, giỏ, cọc SafePay, ví, rút tiền, tài chính."""
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import select, update

from app.db import SessionLocal
from app.models import Escrow, Listing, Promo, PromoUsage

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
    response = client.post("/api/v1/listings", headers=seller["headers"], json={**LISTING, **overrides})
    assert response.status_code == 201, response.text
    listing = response.json()["listing"]
    # Tin mới chờ duyệt; test cần tin đang bán nên bật thẳng trong DB.
    with SessionLocal() as db:
        db.execute(update(Listing).where(Listing.id == listing["id"]).values(status="ACTIVE"))
        db.commit()
    listing["status"] = "ACTIVE"
    return listing


def _order(client, buyer, listing_id, **overrides):
    response = client.post(
        "/api/v1/orders", headers=buyer["headers"], json={"listingId": listing_id, **SHIP, **overrides}
    )
    assert response.status_code == 201, response.text
    return response.json()


def _topup(client, user, amount=1_000_000):
    response = client.post("/api/v1/wallet/topup", headers=user["headers"], json={"amount": amount})
    assert response.status_code == 200, response.text
    return response.json()


def _wallet(client, user):
    return client.get("/api/v1/wallet", headers=user["headers"]).json()


def _bank(client, user):
    response = client.post(
        "/api/v1/wallet/banks",
        headers=user["headers"],
        json={
            "bankName": "Vietcombank",
            "accountNumber": "0123456789",
            "accountName": "NGUYEN VAN QA",
            "isDefault": True,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_tra_gia_va_mua_theo_gia_da_thuong_luong(make_user, client):
    seller = make_user(["SELLER"], verified=True)
    buyer = make_user(verified=True)
    listing = _listing(client, seller)

    made = client.post(
        f"/api/v1/listings/{listing['id']}/offers",
        headers=buyer["headers"],
        json={"offeredPrice": 400_000, "message": "Bớt chút nhé"},
    )
    assert made.status_code == 201, made.text
    offer = made.json()["offer"]

    mine = client.get("/api/v1/offers/mine", headers=buyer["headers"]).json()
    assert mine["meta"]["total"] == 1
    assert mine["data"][0]["listing"]["seller"]["fullName"] == "Tài khoản QA"

    inbox = client.get("/api/v1/offers/inbox", headers=seller["headers"]).json()
    assert inbox["data"][0]["listing"] == {"title": LISTING["title"], "price": 500_000}
    assert inbox["data"][0]["buyer"]["id"] == buyer["id"]

    accepted = client.patch(
        f"/api/v1/offers/{offer['id']}", headers=seller["headers"], json={"action": "ACCEPT"}
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["offer"]["status"] == "ACCEPTED"

    again = client.patch(
        f"/api/v1/offers/{offer['id']}", headers=seller["headers"], json={"action": "REJECT"}
    )
    assert again.status_code == 400
    assert again.json()["message"] == "Yêu cầu đã ở trạng thái ACCEPTED"

    order = _order(client, buyer, listing["id"], offerId=offer["id"])
    assert order["priceAgreed"] == 400_000
    assert order["shippingFee"] == 15_000
    assert order["platformFee"] == 20_000
    assert order["totalAmount"] == 415_000
    assert order["status"] == "PENDING_DEPOSIT"


def test_tao_don_giu_mon_va_kiem_tra_quyen(make_user, client):
    seller = make_user(["SELLER"], verified=True)
    buyer = make_user(verified=True)
    listing = _listing(client, seller)

    unverified = make_user()
    blocked = client.post(
        "/api/v1/orders", headers=unverified["headers"], json={"listingId": listing["id"], **SHIP}
    )
    assert blocked.status_code == 403

    own = client.post(
        "/api/v1/orders", headers=seller["headers"], json={"listingId": listing["id"], **SHIP}
    )
    assert own.status_code == 400
    assert own.json()["message"] == "Không thể mua tin của chính mình"

    _order(client, buyer, listing["id"])
    with SessionLocal() as db:
        assert db.get(Listing, listing["id"]).status == "RESERVED"

    second = client.post(
        "/api/v1/orders", headers=buyer["headers"], json={"listingId": listing["id"], **SHIP}
    )
    assert second.status_code == 404
    assert second.json()["message"] == "Sản phẩm không khả dụng"


def test_ma_giam_gia_va_han_muc_don_cho_coc(make_user, client):
    seller = make_user(["SELLER"], verified=True)
    buyer = make_user(verified=True)
    listing = _listing(client, seller)
    code = f"qa-promo-{uuid4().hex[:8]}"

    with SessionLocal() as db:
        db.add(
            Promo(
                name="Giảm giá QA",
                type="VOUCHER",
                code=code,
                discountType="PERCENT",
                discountValue=10,
                maxDiscount=20_000,
                minOrder=0,
                startsAt=datetime.utcnow() - timedelta(hours=1),
                endsAt=datetime.utcnow() + timedelta(hours=1),
                status="ACTIVE",
            )
        )
        db.commit()

    order = _order(client, buyer, listing["id"], promoCode=code)
    assert order["discountAmount"] == 20_000
    assert order["totalAmount"] == 500_000 - 20_000 + 15_000

    with SessionLocal() as db:
        promo = db.execute(select(Promo).where(Promo.code == code)).scalar_one()
        assert promo.usedCount == 1
        usage = db.execute(select(PromoUsage).where(PromoUsage.orderId == order["id"])).scalar_one()
        assert usage.userId == buyer["id"]

    bad = client.post(
        "/api/v1/orders",
        headers=buyer["headers"],
        json={"listingId": listing["id"], "promoCode": "khong-ton-tai", **SHIP},
    )
    assert bad.status_code in (400, 404)


def test_dat_coc_hoan_tat_va_chia_tien(make_user, client):
    seller = make_user(["SELLER"], verified=True)
    buyer = make_user(verified=True)
    listing = _listing(client, seller)
    order = _order(client, buyer, listing["id"])
    _topup(client, buyer)

    too_little = client.post(
        f"/api/v1/escrow/orders/{order['id']}/deposit",
        headers=buyer["headers"],
        json={"amount": 1_000},
    )
    assert too_little.status_code == 400
    assert "tối thiểu" in too_little.json()["message"]

    outside = client.post(
        f"/api/v1/escrow/orders/{order['id']}/deposit",
        headers=buyer["headers"],
        json={"paymentMethod": "BANK_TRANSFER"},
    )
    assert outside.status_code == 400

    deposited = client.post(
        f"/api/v1/escrow/orders/{order['id']}/deposit", headers=buyer["headers"], json={}
    )
    assert deposited.status_code == 201, deposited.text
    body = deposited.json()
    assert body["order"]["status"] == "DEPOSITED"
    assert body["order"]["depositAmount"] == 103_000
    assert body["order"]["remainingAmount"] == 412_000
    assert body["escrow"]["status"] == "HELD"
    assert _wallet(client, buyer)["balance"] == 897_000

    txns = client.get(
        "/api/v1/wallet/transactions", headers=buyer["headers"], params={"type": "ORDER_PAYMENT"}
    ).json()
    assert txns["data"][0]["amount"] == -103_000

    wallet_after_deposit = _wallet(client, buyer)["balance"]
    resend = client.post(
        f"/api/v1/escrow/orders/{order['id']}/deposit", headers=buyer["headers"], json={}
    )
    assert resend.status_code == 400
    assert _wallet(client, buyer)["balance"] == wallet_after_deposit

    blocked = client.patch(
        f"/api/v1/orders/{order['id']}/status", headers=buyer["headers"], json={"to": "CONFIRMED"}
    )
    assert blocked.status_code == 403

    for step, extra in (
        ("CONFIRMED", {}),
        ("SHIPPING", {"trackingCode": "GHN-123"}),
        ("DELIVERED", {}),
    ):
        moved = client.patch(
            f"/api/v1/orders/{order['id']}/status",
            headers=seller["headers"],
            json={"to": step, **extra},
        )
        assert moved.status_code == 200, moved.text

    early = client.patch(
        f"/api/v1/orders/{order['id']}/status", headers=buyer["headers"], json={"to": "COMPLETED"}
    )
    assert early.status_code == 400

    paid = client.post(
        f"/api/v1/escrow/orders/{order['id']}/pay-remainder", headers=buyer["headers"]
    )
    assert paid.status_code == 200, paid.text
    assert _wallet(client, buyer)["balance"] == 897_000 - 412_000

    done = client.patch(
        f"/api/v1/orders/{order['id']}/status", headers=buyer["headers"], json={"to": "COMPLETED"}
    )
    assert done.status_code == 200, done.text
    assert done.json()["status"] == "COMPLETED"

    assert _wallet(client, seller)["balance"] == 515_000 - 25_000
    with SessionLocal() as db:
        assert db.get(Listing, listing["id"]).status == "SOLD_OUT"
        escrow = db.execute(select(Escrow).where(Escrow.orderId == order["id"])).scalar_one()
        assert escrow.status == "RELEASED"

    detail = client.get(f"/api/v1/orders/{order['id']}", headers=buyer["headers"]).json()
    statuses = [row["status"] for row in detail["timeline"]]
    assert statuses[-2:] == ["FULLY_PAID", "COMPLETED"]
    assert detail["review"] is None
    assert detail["escrow"]["status"] == "RELEASED"

    escrows = client.get("/api/v1/escrow/mine", headers=seller["headers"]).json()
    assert escrows[0]["order"]["code"] == order["code"]


def test_huy_don_hoan_coc_va_mo_lai_tin(make_user, client):
    seller = make_user(["SELLER"], verified=True)
    buyer = make_user(verified=True)
    listing = _listing(client, seller)
    order = _order(client, buyer, listing["id"])
    _topup(client, buyer)
    client.post(f"/api/v1/escrow/orders/{order['id']}/deposit", headers=buyer["headers"], json={})

    cancelled = client.patch(
        f"/api/v1/orders/{order['id']}/status",
        headers=seller["headers"],
        json={"to": "CANCELLED", "note": "Hết hàng"},
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "CANCELLED"
    assert cancelled.json()["cancelReason"] == "Hết hàng"
    assert _wallet(client, buyer)["balance"] == 1_000_000

    with SessionLocal() as db:
        assert db.get(Listing, listing["id"]).status == "ACTIVE"
        escrow = db.execute(select(Escrow).where(Escrow.orderId == order["id"])).scalar_one()
        assert escrow.status == "REFUNDED"

    refund_txns = client.get(
        "/api/v1/wallet/transactions", headers=buyer["headers"], params={"type": "REFUND"}
    ).json()
    assert refund_txns["data"][0]["amount"] == 103_000


def test_gio_hang_them_xoa_va_checkout(make_user, client):
    seller = make_user(["SELLER"], verified=True)
    buyer = make_user(verified=True)
    listing = _listing(client, seller)

    own = client.post("/api/v1/cart", headers=seller["headers"], json={"listingId": listing["id"]})
    assert own.status_code == 400

    added = client.post("/api/v1/cart", headers=buyer["headers"], json={"listingId": listing["id"]})
    assert added.status_code == 201, added.text
    assert added.json()["count"] == 1
    item = added.json()["item"]
    assert item["listing"]["category"] == {"id": 1, "name": "Điện tử cũ"}
    assert len(item["listing"]["images"]) == 1

    client.post("/api/v1/cart", headers=buyer["headers"], json={"listingId": listing["id"]})
    cart = client.get("/api/v1/cart", headers=buyer["headers"]).json()
    assert cart["count"] == 1
    assert cart["total"] == 500_000

    failed = client.post(
        "/api/v1/cart/checkout",
        headers=buyer["headers"],
        json={"listingIds": [999_999], **SHIP},
    )
    assert failed.status_code == 400
    assert failed.json()["errors"][0]["listingId"] == 999_999

    done = client.post(
        "/api/v1/cart/checkout",
        headers=buyer["headers"],
        json={"listingIds": [listing["id"]], **SHIP},
    )
    assert done.status_code == 201, done.text
    assert done.json()["orders"][0]["listingId"] == listing["id"]
    assert done.json()["errors"] == []
    assert client.get("/api/v1/cart", headers=buyer["headers"]).json()["count"] == 0


def test_vi_nap_rut_tien_va_huy(make_user, client):
    user = make_user()
    empty = client.get("/api/v1/wallet", headers=user["headers"]).json()
    assert empty["balance"] == 0
    assert empty["pendingBalance"] == 0

    _topup(client, user, 100_000)
    assert _wallet(client, user)["balance"] == 100_000

    bank = _bank(client, user)
    assert bank["isDefault"] is True
    assert [row["id"] for row in client.get("/api/v1/wallet/banks", headers=user["headers"]).json()] == [
        bank["id"]
    ]

    key = str(uuid4())
    made = client.post(
        "/api/v1/wallet/withdraw",
        headers=user["headers"],
        json={"amount": 50_000, "bankAccountId": bank["id"], "requestKey": key},
    )
    assert made.status_code == 201, made.text
    assert made.json()["balance"] == 50_000
    assert made.json()["request"]["status"] == "PENDING"
    assert made.json()["request"]["fee"] == 0

    replay = client.post(
        "/api/v1/wallet/withdraw",
        headers=user["headers"],
        json={"amount": 50_000, "bankAccountId": bank["id"], "requestKey": key},
    )
    assert replay.status_code == 201
    assert replay.json()["request"]["id"] == made.json()["request"]["id"]
    assert _wallet(client, user)["balance"] == 50_000

    conflict = client.post(
        "/api/v1/wallet/withdraw",
        headers=user["headers"],
        json={"amount": 60_000, "bankAccountId": bank["id"], "requestKey": key},
    )
    assert conflict.status_code == 409

    too_much = client.post(
        "/api/v1/wallet/withdraw",
        headers=user["headers"],
        json={"amount": 200_000, "bankAccountId": bank["id"], "requestKey": str(uuid4())},
    )
    assert too_much.status_code == 400
    assert "khả dụng" in too_much.json()["message"]

    listed = client.get("/api/v1/wallet/withdrawals", headers=user["headers"]).json()
    assert listed["meta"]["total"] == 1

    cancelled = client.patch(
        f"/api/v1/wallet/withdrawals/{listed['data'][0]['id']}/cancel", headers=user["headers"]
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "CANCELLED"
    assert _wallet(client, user)["balance"] == 100_000

    assert client.delete(f"/api/v1/wallet/banks/{bank['id']}", headers=user["headers"]).status_code == 200
    assert client.get("/api/v1/wallet/banks", headers=user["headers"]).json() == []


def test_admin_tai_chinh_duyet_va_chi_tra(make_user, client):
    admin = make_user(["ADMIN_FINANCE"])
    user = make_user()
    _topup(client, user, 500_000)
    bank = _bank(client, user)
    made = client.post(
        "/api/v1/wallet/withdraw",
        headers=user["headers"],
        json={"amount": 200_000, "bankAccountId": bank["id"], "requestKey": str(uuid4())},
    ).json()
    request_id = made["request"]["id"]

    listed = client.get(
        "/api/v1/admin/finance/withdrawals",
        headers=admin["headers"],
        params={"status": "PENDING", "q": "WD-"},
    ).json()
    assert any(row["id"] == request_id for row in listed["data"])

    approved = client.patch(
        f"/api/v1/admin/finance/withdrawals/{request_id}",
        headers=admin["headers"],
        json={"action": "APPROVE", "resolution": "Hồ sơ hợp lệ"},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "APPROVED"

    missing_ref = client.patch(
        f"/api/v1/admin/finance/withdrawals/{request_id}",
        headers=admin["headers"],
        json={"action": "PAY", "resolution": "Chuyển khoản"},
    )
    assert missing_ref.status_code == 400

    paid = client.patch(
        f"/api/v1/admin/finance/withdrawals/{request_id}",
        headers=admin["headers"],
        json={"action": "PAY", "resolution": "Đã chuyển", "transferReference": "VCB-2026-001"},
    )
    assert paid.status_code == 200, paid.text
    assert paid.json()["status"] == "PAID"
    assert paid.json()["paidAt"].endswith("Z")

    wallet = _wallet(client, user)
    assert wallet["balance"] == 300_000
    assert wallet["pendingBalance"] == 0
    txns = client.get(
        "/api/v1/wallet/transactions", headers=user["headers"], params={"type": "WITHDRAW"}
    ).json()
    assert txns["data"][0]["amount"] == -200_000
    assert txns["data"][0]["status"] == "SUCCESS"

    late = client.patch(
        f"/api/v1/admin/finance/withdrawals/{request_id}",
        headers=admin["headers"],
        json={"action": "REJECT", "resolution": "Muộn rồi"},
    )
    assert late.status_code == 409


def test_admin_khong_tu_duyet_yeu_cau_cua_minh(make_user, client):
    admin = make_user(["ADMIN_FINANCE"])
    _topup(client, admin, 100_000)
    bank = _bank(client, admin)
    made = client.post(
        "/api/v1/wallet/withdraw",
        headers=admin["headers"],
        json={"amount": 50_000, "bankAccountId": bank["id"], "requestKey": str(uuid4())},
    )
    assert made.status_code == 201
    blocked = client.patch(
        f"/api/v1/admin/finance/withdrawals/{made.json()['request']['id']}",
        headers=admin["headers"],
        json={"action": "APPROVE", "resolution": "Tự duyệt"},
    )
    assert blocked.status_code == 403

    normal = make_user()
    forbidden = client.patch(
        f"/api/v1/admin/finance/withdrawals/{made.json()['request']['id']}",
        headers=normal["headers"],
        json={"action": "APPROVE", "resolution": "Không có quyền"},
    )
    assert forbidden.status_code == 403


def test_tai_chinh_tong_quan_giao_dich_va_phi(make_user, client):
    admin = make_user(["ADMIN_FINANCE"])
    _topup(client, admin, 200_000)

    overview = client.get("/api/v1/admin/finance/overview", headers=admin["headers"])
    assert overview.status_code == 200
    assert set(overview.json()["kpis"]) == {
        "monthlyRevenue",
        "totalTransactions",
        "pendingRefunds",
        "openDisputes",
    }

    txns = client.get(
        "/api/v1/admin/finance/transactions",
        headers=admin["headers"],
        params={"type": "TOPUP", "q": "Tài khoản QA"},
    ).json()
    assert txns["meta"]["total"] >= 1
    assert txns["data"][0]["wallet"]["user"]["fullName"] == "Tài khoản QA"

    today = datetime.utcnow().strftime("%Y-%m-%d")
    chart = client.get(
        "/api/v1/admin/finance/charts/revenue",
        headers=admin["headers"],
        params={"from": today, "to": today},
    ).json()
    assert chart["basis"] == "COLLECTED_PLATFORM_FEES"
    assert len(chart["data"]) == 1
    assert chart["data"][0]["date"] == today

    status_chart = client.get("/api/v1/admin/finance/charts/order-status", headers=admin["headers"])
    assert status_chart.status_code == 200
    assert all({"status", "count"} <= set(row) for row in status_chart.json())

    report = client.get(
        "/api/v1/admin/finance/revenue", headers=admin["headers"], params={"months": 3}
    ).json()
    assert len(report["labels"]) == 3
    assert len(report["monthly"]) == 3

    created = client.post(
        "/api/v1/admin/finance/fees",
        headers=admin["headers"],
        json={"kind": "PENALTY", "name": "qa-fee-phat-thu", "amount": 5_000, "isActive": True},
    )
    assert created.status_code == 201, created.text
    fee_id = created.json()["id"]
    assert created.json()["updatedAt"].endswith("Z")

    updated = client.patch(
        f"/api/v1/admin/finance/fees/{fee_id}",
        headers=admin["headers"],
        json={"amount": 7_000},
    )
    assert updated.status_code == 200
    assert updated.json()["amount"] == 7_000

    fees = client.get(
        "/api/v1/admin/finance/fees", headers=admin["headers"], params={"kind": "PENALTY"}
    ).json()
    assert any(row["id"] == fee_id for row in fees)

    assert client.delete(
        f"/api/v1/admin/finance/fees/{fee_id}", headers=admin["headers"]
    ).status_code == 200


def test_don_hang_cua_toi_va_admin_xem_tat_ca(make_user, client):
    seller = make_user(["SELLER"], verified=True)
    buyer = make_user(verified=True)
    admin = make_user(["ADMIN_CONTENT"])
    listing = _listing(client, seller)
    order = _order(client, buyer, listing["id"])

    mine = client.get("/api/v1/orders/mine", headers=buyer["headers"]).json()
    assert mine["meta"]["total"] == 1
    assert mine["data"][0]["code"] == order["code"]
    assert mine["data"][0]["seller"]["fullName"] == "Tài khoản QA"

    sales = client.get("/api/v1/orders/sales", headers=seller["headers"]).json()
    assert sales["data"][0]["buyer"]["id"] == buyer["id"]

    all_orders = client.get(
        "/api/v1/orders/admin/all", headers=admin["headers"], params={"q": order["code"][:7]}
    ).json()
    assert any(row["id"] == order["id"] for row in all_orders["data"])

    hidden = client.get(f"/api/v1/orders/{order['id']}", headers=make_user()["headers"])
    assert hidden.status_code == 403
