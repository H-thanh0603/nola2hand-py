"""Gắn video đã tạo xong vào tin đăng — kể cả khi lúc tạo đã chọn "Không gắn".

Luồng thật: seller bấm tạo video mà quên chọn tin, 15 phút sau video xong và nằm mồ côi.
Endpoint attach cho phép gắn lại mà không phải dựng lại video (mỗi lượt dựng tốn ~15 phút).
"""
from sqlalchemy import select

from app.db import SessionLocal
from app.models import VideoJob
from app.utils import now

PAYLOAD = {
    "categoryId": 1,
    "title": "Tai nghe QA gắn video sau",
    "description": "Mô tả đủ dài cho tin đăng thử nghiệm, vượt qua giới hạn hai mươi ký tự.",
    "price": 500000,
    "condition": "USED_GOOD",
    "city": "TP.HCM",
    "images": ["https://cdn.example.com/qa-attach-1.jpg"],
}


def _make_listing(client, seller) -> int:
    response = client.post("/api/v1/listings", headers=seller["headers"], json=PAYLOAD)
    assert response.status_code == 201, response.text
    return response.json()["listing"]["id"]


def _make_job(seller_id: int, status: str = "DONE", listing_id: int | None = None) -> int:
    with SessionLocal() as db:
        job = VideoJob(
            sellerId=seller_id,
            listingId=listing_id,
            prompt="x",
            finalPrompt="x",
            status=status,
            videoUrl="/uploads/videos/attach.mp4" if status == "DONE" else None,
            createdAt=now(),
        )
        db.add(job)
        db.commit()
        return job.id


def _job_row(job_id: int) -> VideoJob:
    with SessionLocal() as db:
        return db.execute(select(VideoJob).where(VideoJob.id == job_id)).scalar_one()


def test_gan_video_da_xong_vao_tin(client, make_user):
    seller = make_user(roles=["SELLER"], verified=True)
    listing_id = _make_listing(client, seller)
    job_id = _make_job(seller["id"])

    response = client.post(
        f"/api/v1/video-jobs/{job_id}/attach",
        headers=seller["headers"],
        json={"listingId": listing_id},
    )

    assert response.status_code == 200, response.text
    assert response.json()["job"]["listingId"] == listing_id
    assert _job_row(job_id).listingId == listing_id
    # Trang sản phẩm phải thấy video ngay sau khi gắn.
    assert client.get(f"/api/v1/listings/{listing_id}").json()["video"]["videoUrl"]


def test_doi_video_sang_tin_khac(client, make_user):
    seller = make_user(roles=["SELLER"], verified=True)
    first = _make_listing(client, seller)
    second = _make_listing(client, seller)
    job_id = _make_job(seller["id"], listing_id=first)

    response = client.post(
        f"/api/v1/video-jobs/{job_id}/attach",
        headers=seller["headers"],
        json={"listingId": second},
    )

    assert response.status_code == 200, response.text
    assert _job_row(job_id).listingId == second
    assert client.get(f"/api/v1/listings/{first}").json()["video"] is None


def test_bo_gan_khoi_tin(client, make_user):
    seller = make_user(roles=["SELLER"], verified=True)
    listing_id = _make_listing(client, seller)
    job_id = _make_job(seller["id"], listing_id=listing_id)

    response = client.post(
        f"/api/v1/video-jobs/{job_id}/attach",
        headers=seller["headers"],
        json={"listingId": None},
    )

    assert response.status_code == 200, response.text
    assert _job_row(job_id).listingId is None
    assert client.get(f"/api/v1/listings/{listing_id}").json()["video"] is None


def test_khong_gan_duoc_video_chua_xong(client, make_user):
    seller = make_user(roles=["SELLER"], verified=True)
    listing_id = _make_listing(client, seller)
    job_id = _make_job(seller["id"], status="RUNNING")

    response = client.post(
        f"/api/v1/video-jobs/{job_id}/attach",
        headers=seller["headers"],
        json={"listingId": listing_id},
    )

    assert response.status_code == 400
    assert _job_row(job_id).listingId is None


def test_gan_vao_tin_cua_nguoi_khac_tra_404(client, make_user):
    owner = make_user(roles=["SELLER"], verified=True)
    other = make_user(roles=["SELLER"], verified=True)
    listing_id = _make_listing(client, owner)
    job_id = _make_job(other["id"])

    response = client.post(
        f"/api/v1/video-jobs/{job_id}/attach",
        headers=other["headers"],
        json={"listingId": listing_id},
    )

    assert response.status_code == 404
    assert _job_row(job_id).listingId is None


def test_khong_gan_duoc_job_cua_nguoi_khac(client, make_user):
    owner = make_user(roles=["SELLER"], verified=True)
    other = make_user(roles=["SELLER"], verified=True)
    listing_id = _make_listing(client, other)
    job_id = _make_job(owner["id"])

    response = client.post(
        f"/api/v1/video-jobs/{job_id}/attach",
        headers=other["headers"],
        json={"listingId": listing_id},
    )

    assert response.status_code == 404
    assert _job_row(job_id).listingId is None


def test_buyer_khong_gan_duoc_video(client, make_user):
    seller = make_user(roles=["SELLER"], verified=True)
    buyer = make_user()
    listing_id = _make_listing(client, seller)
    job_id = _make_job(seller["id"])

    response = client.post(
        f"/api/v1/video-jobs/{job_id}/attach",
        headers=buyer["headers"],
        json={"listingId": listing_id},
    )

    assert response.status_code == 403
    assert _job_row(job_id).listingId is None
