"""Tin đăng mới hiện ngay, nhưng tin bị từ chối không được tự đăng lại."""
from sqlalchemy import select, update

from app.db import SessionLocal
from app.models import Listing

PAYLOAD = {
    "categoryId": 1,
    "title": "Tai nghe QA duyệt tin",
    "description": "Mô tả đủ dài cho tin đăng thử nghiệm, vượt qua giới hạn hai mươi ký tự.",
    "price": 500000,
    "condition": "USED_GOOD",
    "city": "TP.HCM",
    "images": ["https://cdn.example.com/qa-duyet-1.jpg"],
}

def _make_listing(client, seller) -> int:
    response = client.post("/api/v1/listings", headers=seller["headers"], json=PAYLOAD)
    assert response.status_code == 201, response.text
    return response.json()["listing"]["id"]

def _force(listing_id: int, **values) -> None:
    with SessionLocal() as db:
        db.execute(update(Listing).where(Listing.id == listing_id).values(**values))
        db.commit()

def _status(listing_id: int) -> str:
    with SessionLocal() as db:
        return db.execute(select(Listing.status).where(Listing.id == listing_id)).scalar_one()

def test_tin_bi_tu_choi_khong_tu_dang_lai(client, make_user):
    """Lỗ hổng: REJECTED nằm trong EDITABLE_STATUSES nên PATCH đẩy thẳng về ACTIVE."""
    seller = make_user(roles=["SELLER"], verified=True)
    listing_id = _make_listing(client, seller)
    _force(listing_id, status="REJECTED", rejectReason="Hàng giả")

    response = client.patch(
        f"/api/v1/listings/{listing_id}",
        headers=seller["headers"],
        json={"price": 400000},
    )

    assert response.status_code == 409, response.text
    assert _status(listing_id) == "REJECTED"

def test_tin_bi_tu_choi_van_xem_duoc_trong_kenh_seller(client, make_user):
    seller = make_user(roles=["SELLER"], verified=True)
    listing_id = _make_listing(client, seller)
    _force(listing_id, status="REJECTED", rejectReason="Hàng giả")

    response = client.get(f"/api/v1/seller/listings/{listing_id}", headers=seller["headers"])
    assert response.status_code == 200
    assert response.json()["status"] == "REJECTED"
