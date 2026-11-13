"""Tạo video quảng bá 10 giây — người bán gửi prompt + tối đa 3 ảnh, Muse dựng video.

Ràng buộc sản phẩm: video luôn 10 giây, tối đa 3 ảnh (xem `services/video_prompt.py`).
Sidecar `video-agent` chạy trên cùng máy, gọi qua HTTP nội bộ.
"""
import shutil
import uuid
from datetime import timedelta
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..deps import CurrentUser, require_role
from ..errors import ApiError
from ..models import Category, Listing, VideoJob
from ..serialize import to_dict
from ..services import video_agent
from ..services.video_prompt import MAX_IMAGES, PROMPT_NOTICE, finalize
from ..utils import now
from .upload import MAX_BYTES, decode_image

router = APIRouter()

VIDEO_DIR = Path(__file__).resolve().parents[3] / "uploads" / "videos"
# Muse giới hạn tổng ảnh gửi kèm 8MB; chặn sớm để không tốn một lượt gọi sidecar.
MAX_TOTAL_BYTES = 8 * 1024 * 1024
# Một lượt dựng video thật mất ~15 phút (hàng đợi tuần tự, một tài khoản Muse). Quá mốc
# này thì coi như sidecar treo và đóng job, thay vì để seller poll mãi.
JOB_DEADLINE = timedelta(minutes=30)

class ImageIn(BaseModel):
    mimeType: Literal["image/jpeg", "image/png", "image/webp"]
    base64: str = Field(max_length=7_000_000)

class JobIn(BaseModel):
    prompt: str
    listingId: int | None = None
    images: list[ImageIn]

class PreviewIn(BaseModel):
    prompt: str
    listingId: int | None = None

class AttachIn(BaseModel):
    """`listingId` null = bỏ gắn khỏi tin, giữ video lại trong danh sách của seller."""
    listingId: int | None = None

def _listing_context(db: Session, listing_id: int | None, user: CurrentUser) -> dict | None:
    """Bối cảnh tin đăng để cải thiện prompt — chỉ tin của chính người bán."""
    if listing_id is None:
        return None
    listing = db.execute(
        select(Listing).where(Listing.id == listing_id, Listing.sellerId == user.id)
    ).scalar_one_or_none()
    if listing is None:
        raise ApiError(404, "Không tìm thấy tin đăng của bạn")
    category_name = db.execute(
        select(Category.name).where(Category.id == listing.categoryId)
    ).scalar_one_or_none()
    return {
        "title": listing.title,
        "condition": listing.condition,
        "price": listing.price,
        "categoryName": category_name or "",
    }

def _validate_images(images: list[ImageIn]) -> None:
    if not images:
        raise ApiError(400, "Cần ít nhất 1 ảnh để tạo video")
    if len(images) > MAX_IMAGES:
        raise ApiError(400, f"Chỉ được chọn tối đa {MAX_IMAGES} ảnh")
    total = 0
    for image in images:
        data = decode_image(image.base64, image.mimeType)
        total += len(data)
        if len(data) > MAX_BYTES:
            raise ApiError(400, "Mỗi ảnh không được vượt quá 5MB")
    if total > MAX_TOTAL_BYTES:
        raise ApiError(400, "Tổng dung lượng ảnh không được vượt quá 8MB")

@router.post("/preview-prompt")
def preview_prompt(
    payload: PreviewIn,
    user: CurrentUser = Depends(require_role("SELLER")),
    db: Session = Depends(get_db),
):
    """Xem trước prompt sau khi làm sạch mốc thời gian và cải thiện."""
    listing = _listing_context(db, payload.listingId, user)
    try:
        text = finalize(payload.prompt, listing)
    except ValueError as exc:
        raise ApiError(400, str(exc)) from exc
    return {"finalPrompt": text, "notice": PROMPT_NOTICE, "maxImages": MAX_IMAGES}

@router.post("", status_code=201)
def create_job(
    payload: JobIn,
    user: CurrentUser = Depends(require_role("SELLER")),
    db: Session = Depends(get_db),
):
    listing = _listing_context(db, payload.listingId, user)
    try:
        final_prompt = finalize(payload.prompt, listing)
    except ValueError as exc:
        raise ApiError(400, str(exc)) from exc
    _validate_images(payload.images)

    if not settings.video_agent_enabled:
        raise ApiError(503, "Dịch vụ tạo video chưa sẵn sàng")

    job = VideoJob(
        sellerId=user.id,
        listingId=payload.listingId,
        prompt=payload.prompt,
        finalPrompt=final_prompt,
        status="QUEUED",
        createdAt=now(),
    )
    db.add(job)
    db.flush()  # lấy job.id để đặt tên thư mục output, nhưng chưa commit

    try:
        agent_id = video_agent.submit(
            final_prompt,
            [{"mimeType": image.mimeType, "dataBase64": image.base64} for image in payload.images],
            f"job-{job.id}",
        )
    except ApiError as exc:
        # Không commit job khi sidecar từ chối: một row QUEUED với agentJobId NULL sẽ
        # không bao giờ được poll tới và treo vĩnh viễn trong danh sách của seller.
        db.rollback()
        raise ApiError(exc.status, exc.message) from exc

    job.agentJobId = agent_id
    db.commit()
    db.refresh(job)
    return {"job": to_dict(job), "notice": PROMPT_NOTICE}

def _fail(job: VideoJob, message: str) -> None:
    job.status = "FAILED"
    job.error = message
    job.finishedAt = now()

def _refresh_from_agent(job: VideoJob, db: Session) -> None:
    """Hỏi sidecar khi job còn chạy; sidecar xong thì copy file vào uploads/videos.

    Không bao giờ để job treo mãi: sidecar quên job (404) thì FAILED ngay, còn lỗi tạm
    thời (503, timeout) thì thử lại tới `JOB_DEADLINE` rồi cũng FAILED kèm lý do.
    """
    if job.status not in ("QUEUED", "RUNNING"):
        return
    if not job.agentJobId:
        # Chỉ xảy ra với row cũ tạo trước khi create_job rollback khi submit lỗi.
        _fail(job, "Không gửi được yêu cầu tạo video, vui lòng thử lại")
        db.commit()
        db.refresh(job)
        return
    try:
        state = video_agent.status(job.agentJobId)
    except ApiError as exc:
        if exc.status == 404:
            _fail(job, "Dịch vụ tạo video không còn giữ job này, vui lòng tạo lại")
            db.commit()
            db.refresh(job)
            return
        if now() - job.createdAt > JOB_DEADLINE:
            _fail(job, "Hết thời gian chờ dịch vụ tạo video, vui lòng thử lại")
            db.commit()
            db.refresh(job)
        return  # lỗi tạm thời: giữ nguyên trạng thái, lần poll sau thử lại
    status = state.get("status")
    overdue = now() - job.createdAt > JOB_DEADLINE
    if status == "running":
        if overdue:
            _fail(job, "Hết thời gian chờ dịch vụ tạo video, vui lòng thử lại")
        else:
            job.status = "RUNNING"
    elif status == "done":
        source = state.get("file")
        if not source or not Path(source).is_file():
            _fail(job, "Sidecar báo xong nhưng không thấy file video")
        else:
            VIDEO_DIR.mkdir(parents=True, exist_ok=True)
            name = f"{uuid.uuid4().hex}.mp4"
            shutil.copyfile(source, VIDEO_DIR / name)
            job.videoUrl = f"/uploads/videos/{name}"
            job.status = "DONE"
            job.finishedAt = now()
    elif status == "failed":
        _fail(job, state.get("error") or "Muse không tạo được video")
    elif status == "cancelled":
        job.status = "CANCELLED"
        job.finishedAt = now()
    db.commit()
    db.refresh(job)

@router.get("")
def list_jobs(
    user: CurrentUser = Depends(require_role("SELLER")),
    db: Session = Depends(get_db),
):
    jobs = db.execute(
        select(VideoJob).where(VideoJob.sellerId == user.id).order_by(VideoJob.id.desc()).limit(50)
    ).scalars().all()
    for job in jobs:
        _refresh_from_agent(job, db)
    return {"jobs": [to_dict(job) for job in jobs]}

@router.get("/{job_id}")
def get_job(
    job_id: int,
    user: CurrentUser = Depends(require_role("SELLER")),
    db: Session = Depends(get_db),
):
    job = db.execute(
        select(VideoJob).where(VideoJob.id == job_id, VideoJob.sellerId == user.id)
    ).scalar_one_or_none()
    if job is None:
        raise ApiError(404, "Không tìm thấy job video")
    _refresh_from_agent(job, db)
    return {"job": to_dict(job)}

@router.post("/{job_id}/attach")
def attach_job(
    job_id: int,
    payload: AttachIn,
    user: CurrentUser = Depends(require_role("SELLER")),
    db: Session = Depends(get_db),
):
    """Gắn video đã dựng xong vào một tin của chính seller (hoặc bỏ gắn).

    Lúc tạo job seller có thể chọn "Không gắn"; mỗi lượt dựng tốn ~15 phút nên phải cho
    gắn lại thay vì bắt tạo job mới. Chỉ video DONE mới gắn được — video đang chạy chưa
    có file để trang sản phẩm phát.
    """
    job = db.execute(
        select(VideoJob).where(VideoJob.id == job_id, VideoJob.sellerId == user.id)
    ).scalar_one_or_none()
    if job is None:
        raise ApiError(404, "Không tìm thấy job video")

    # `_listing_context` đã chặn tin của người khác (404) — dùng lại thay vì query riêng.
    _listing_context(db, payload.listingId, user)

    if payload.listingId is not None and job.status != "DONE":
        raise ApiError(400, "Chỉ gắn được video đã dựng xong")

    job.listingId = payload.listingId
    db.commit()
    db.refresh(job)
    return {"job": to_dict(job)}

@router.post("/{job_id}/cancel")
def cancel_job(
    job_id: int,
    user: CurrentUser = Depends(require_role("SELLER")),
    db: Session = Depends(get_db),
):
    job = db.execute(
        select(VideoJob).where(VideoJob.id == job_id, VideoJob.sellerId == user.id)
    ).scalar_one_or_none()
    if job is None:
        raise ApiError(404, "Không tìm thấy job video")
    if job.status in ("QUEUED", "RUNNING"):
        if job.agentJobId:
            video_agent.cancel(job.agentJobId)
        job.status = "CANCELLED"
        job.finishedAt = now()
        db.commit()
        db.refresh(job)
    return {"job": to_dict(job)}
