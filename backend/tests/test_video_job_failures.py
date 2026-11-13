"""Job video không được treo khi sidecar chết hoặc không bao giờ trả lời."""
from datetime import timedelta

import httpx
import pytest
from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.models import VideoJob
from app.routers import videos as videos_router
from app.utils import now

PNG_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAACklEQVR4nGMAAQAABQAB"
    "DQotBAAAAAAAAAAAAABJRU5ErkJggg=="
)

def _img() -> dict:
    return {"mimeType": "image/png", "base64": PNG_BASE64}

def _job_count(seller_id: int) -> int:
    with SessionLocal() as db:
        return len(
            db.execute(select(VideoJob).where(VideoJob.sellerId == seller_id)).scalars().all()
        )

def test_sidecar_loi_khong_de_lai_job_mo_coi(client, make_user, monkeypatch):
    """submit raise → không được commit row QUEUED với agentJobId NULL."""
    monkeypatch.setattr(settings, "video_agent_enabled", True)

    def boom(*args, **kwargs):
        raise videos_router.video_agent.ApiError(503, "Dịch vụ tạo video chưa sẵn sàng")

    monkeypatch.setattr(videos_router.video_agent, "submit", boom)
    seller = make_user(roles=["SELLER"], verified=True)

    response = client.post(
        "/api/v1/video-jobs", headers=seller["headers"], json={"prompt": "tai nghe", "images": [_img()]}
    )

    assert response.status_code == 503
    assert _job_count(seller["id"]) == 0, "job mồ côi bị bỏ lại trong DB"

def test_job_qua_han_chuyen_failed(client, make_user, monkeypatch):
    """Sidecar không bao giờ trả lời → job phải FAILED sau deadline, không treo RUNNING."""
    monkeypatch.setattr(settings, "video_agent_enabled", True)
    seller = make_user(roles=["SELLER"], verified=True)

    monkeypatch.setattr(videos_router.video_agent, "submit", lambda *a, **k: "job_dead")
    created = client.post(
        "/api/v1/video-jobs", headers=seller["headers"], json={"prompt": "tai nghe", "images": [_img()]}
    )
    assert created.status_code == 201
    job_id = created.json()["job"]["id"]

    # Đẩy createdAt về quá khứ để vượt deadline
    with SessionLocal() as db:
        db.execute(
            select(VideoJob).where(VideoJob.id == job_id)
        )
        job = db.get(VideoJob, job_id)
        job.createdAt = now() - timedelta(hours=2)
        db.commit()

    monkeypatch.setattr(
        videos_router.video_agent,
        "status",
        lambda agent_id: {"status": "running"},
    )

    body = client.get(f"/api/v1/video-jobs/{job_id}", headers=seller["headers"]).json()
    assert body["job"]["status"] == "FAILED"
    assert body["job"]["error"]

def test_sidecar_mat_job_tra_404_thi_failed(client, make_user, monkeypatch):
    """Sidecar restart → job trong RAM mất → backend phải FAILED, không poll mãi."""
    monkeypatch.setattr(settings, "video_agent_enabled", True)
    seller = make_user(roles=["SELLER"], verified=True)
    monkeypatch.setattr(videos_router.video_agent, "submit", lambda *a, **k: "job_gone")
    created = client.post(
        "/api/v1/video-jobs", headers=seller["headers"], json={"prompt": "tai nghe", "images": [_img()]}
    )
    job_id = created.json()["job"]["id"]

    def not_found(agent_id):
        raise videos_router.video_agent.ApiError(404, "Không thấy job")

    monkeypatch.setattr(videos_router.video_agent, "status", not_found)

    body = client.get(f"/api/v1/video-jobs/{job_id}", headers=seller["headers"]).json()
    assert body["job"]["status"] == "FAILED"
    assert "không còn" in body["job"]["error"].lower() or body["job"]["error"]
