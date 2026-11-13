"""Bảng VideoJob phải khớp model và database thật (test parity chung sẽ chặn nếu lệch)."""
from sqlalchemy import inspect

from app.db import engine
from app.models import VideoJob

def test_bang_video_job_ton_tai_va_du_cot():
    cols = [c["name"] for c in inspect(engine).get_columns("VideoJob", schema="public")]
    assert cols == [
        "id", "sellerId", "listingId", "agentJobId", "prompt", "finalPrompt",
        "status", "error", "videoUrl", "createdAt", "finishedAt",
    ]

def test_enum_status_dung_gia_tri():
    assert set(VideoJob.__table__.c.status.type.enums) == {
        "QUEUED", "RUNNING", "DONE", "FAILED", "CANCELLED",
    }
