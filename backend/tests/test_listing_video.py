"""Trang sản phẩm phải trả kèm video quảng bá đã tạo xong (nếu có)."""
from sqlalchemy import select

from app.db import SessionLocal
from app.models import Listing, VideoJob
from app.utils import now

PAYLOAD = {
    "categoryId": 1,
    "title": "Tai nghe QA có video quảng bá",
    "description": "Mô tả đủ dài cho tin đăng thử nghiệm, vượt qua giới hạn hai mươi ký tự.",
    "price": 500000,
    "condition": "USED_GOOD",
    "city": "TP.HCM",
    "images": ["https://cdn.example.com/qa-video-1.jpg"],
}

def _make_listing(client, seller) -> int:
    response = client.post("/api/v1/listings", headers=seller["headers"], json=PAYLOAD)
    assert response.status_code == 201, response.text
    return response.json()["listing"]["id"]

def test_chi_tiet_tin_tra_kem_video(client, make_user):
    seller = make_user(roles=["SELLER"], verified=True)
    listing_id = _make_listing(client, seller)
    with SessionLocal() as db:
        db.add(
            VideoJob(
                sellerId=seller["id"],
                listingId=listing_id,
                prompt="x",
                finalPrompt="x",
                status="DONE",
                videoUrl="/uploads/videos/a.mp4",
                createdAt=now(),
            )
        )
        db.commit()

    body = client.get(f"/api/v1/listings/{listing_id}").json()
    assert body["video"]["videoUrl"] == "/uploads/videos/a.mp4"

def test_tin_chua_co_video_tra_null(client, make_user):
    seller = make_user(roles=["SELLER"], verified=True)
    listing_id = _make_listing(client, seller)
    body = client.get(f"/api/v1/listings/{listing_id}").json()
    assert body["video"] is None

def test_video_dang_loi_khong_hien(client, make_user):
    seller = make_user(roles=["SELLER"], verified=True)
    listing_id = _make_listing(client, seller)
    with SessionLocal() as db:
        db.add(
            VideoJob(
                sellerId=seller["id"],
                listingId=listing_id,
                prompt="x",
                finalPrompt="x",
                status="FAILED",
                error="Muse lỗi",
                createdAt=now(),
            )
        )
        db.commit()
    body = client.get(f"/api/v1/listings/{listing_id}").json()
    assert body["video"] is None

def test_chi_lay_video_moi_nhat(client, make_user):
    seller = make_user(roles=["SELLER"], verified=True)
    listing_id = _make_listing(client, seller)
    with SessionLocal() as db:
        for index in (1, 2):
            db.add(
                VideoJob(
                    sellerId=seller["id"],
                    listingId=listing_id,
                    prompt="x",
                    finalPrompt="x",
                    status="DONE",
                    videoUrl=f"/uploads/videos/v{index}.mp4",
                    createdAt=now(),
                )
            )
        db.commit()
    body = client.get(f"/api/v1/listings/{listing_id}").json()
    assert body["video"]["videoUrl"] == "/uploads/videos/v2.mp4"
