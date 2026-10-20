"""Test tích hợp: tải ảnh sản phẩm, bằng chứng riêng tư, quyền xem bằng chứng."""
import base64

from sqlalchemy import update

from app.db import SessionLocal
from app.models import Listing

PNG = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8AAAwAB/AL+2wAAAABJRU5ErkJggg=="
)

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


def _upload(client, user, mime="image/png", data=PNG, purpose=None):
    body = {"mimeType": mime, "base64": data}
    if purpose:
        body["purpose"] = purpose
    return client.post("/api/v1/upload", headers=user["headers"], json=body)


def _listing(client, seller):
    response = client.post("/api/v1/listings", headers=seller["headers"], json=LISTING)
    assert response.status_code == 201, response.text
    listing = response.json()["listing"]
    with SessionLocal() as db:
        db.execute(update(Listing).where(Listing.id == listing["id"]).values(status="ACTIVE"))
        db.commit()
    return listing


def test_tai_anh_san_pham_va_bang_chung(make_user, client):
    seller = make_user(["SELLER"], verified=True)

    product = _upload(client, seller)
    assert product.status_code == 201, product.text
    url = product.json()["url"]
    assert url.startswith("http://localhost:4000/uploads/")
    assert url.endswith(".png")
    assert product.json()["message"] == "Đã lưu ảnh"

    private = _upload(client, seller, purpose="EVIDENCE")
    assert private.status_code == 201, private.text
    evidence_url = private.json()["url"]
    assert evidence_url.startswith(f"http://localhost:4000/api/v1/upload/evidence/{seller['id']}-")

    assert _upload(client, seller, mime="image/jpeg").status_code == 400
    assert _upload(client, seller, data="!!!không-phải-base64!!!").json()["message"] == (
        "Dữ liệu ảnh không hợp lệ"
    )

    too_big = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x00" * (5 * 1024 * 1024)).decode()
    oversize = _upload(client, seller, data=too_big)
    assert oversize.status_code == 400
    assert oversize.json()["message"] == "Ảnh phải hợp lệ và không vượt quá 5MB"


def test_quyen_xem_bang_chung(make_user, client):
    seller = make_user(["SELLER"], verified=True)
    buyer = make_user(verified=True)
    stranger = make_user()
    finance = make_user(["ADMIN_FINANCE"])

    evidence_url = _upload(client, buyer, purpose="EVIDENCE").json()["url"]
    name = evidence_url.rsplit("/", 1)[1]

    mine = client.get(f"/api/v1/upload/evidence/{name}", headers=buyer["headers"])
    assert mine.status_code == 200
    assert mine.headers["content-type"] == "image/png"
    assert mine.headers["cache-control"] == "private, no-store"
    assert base64.b64encode(mine.content).decode() == PNG

    assert client.get(
        f"/api/v1/upload/evidence/{name}", headers=stranger["headers"]
    ).status_code == 403
    assert client.get(
        f"/api/v1/upload/evidence/{name}", headers=finance["headers"]
    ).status_code == 200
    assert client.get(
        "/api/v1/upload/evidence/khong-hop-le.png", headers=buyer["headers"]
    ).status_code == 404

    listing = _listing(client, seller)
    order = client.post(
        "/api/v1/orders", headers=buyer["headers"], json={"listingId": listing["id"], **SHIP}
    ).json()
    client.post("/api/v1/wallet/topup", headers=buyer["headers"], json={"amount": 1_000_000})
    client.post(
        f"/api/v1/escrow/orders/{order['id']}/deposit", headers=buyer["headers"], json={}
    )
    client.patch(
        f"/api/v1/orders/{order['id']}/status",
        headers=seller["headers"],
        json={"to": "CONFIRMED"},
    )

    opened = client.post(
        f"/api/v1/disputes/orders/{order['id']}/disputes",
        headers=buyer["headers"],
        json={
            "reason": "Hàng giả",
            "description": "Máy nhận được không đúng mô tả, kèm ảnh chụp.",
            "evidences": [evidence_url],
        },
    )
    assert opened.status_code == 201, opened.text

    assert client.get(
        f"/api/v1/upload/evidence/{name}", headers=seller["headers"]
    ).status_code == 200
    assert client.get(
        f"/api/v1/upload/evidence/{name}", headers=stranger["headers"]
    ).status_code == 403
