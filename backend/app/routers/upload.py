"""Tải ảnh sản phẩm/bằng chứng — port src/routes/upload.js."""
import base64
import binascii
import os
import re
import uuid
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import CurrentUser, current_user
from ..errors import ApiError
from ..limits import MemoryLimiter
from ..quota import account_limit
from ..services.evidence import EVIDENCE_DIR, NAME_RE, may_read_evidence, origin

router = APIRouter()

UPLOAD_DIR = Path(__file__).resolve().parents[3] / "uploads"
MAX_BYTES = 5 * 1024 * 1024
BASE64_RE = re.compile(r"[A-Za-z0-9+/]+={0,2}\Z")
EXTENSIONS = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
MEDIA_TYPES = {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp"}

# express-rate-limit mặc định: 50 lượt/giờ/IP, thông báo tiếng Anh.
upload_limiter = MemoryLimiter(50, 60 * 60 * 1000, "Too many requests, please try again later.")


def upload_rate_limit(request: Request) -> None:
    upload_limiter.check(request.client.host if request.client else "unknown")


class UploadIn(BaseModel):
    mimeType: Literal["image/jpeg", "image/png", "image/webp"]
    base64: str = Field(max_length=7_000_000)
    purpose: Literal["PRODUCT", "EVIDENCE"] = "PRODUCT"


def decode_image(encoded: str, mime_type: str) -> bytes:
    if not BASE64_RE.match(encoded):
        raise ApiError(400, "Dữ liệu ảnh không hợp lệ")
    try:
        data = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ApiError(400, "Dữ liệu ảnh không hợp lệ") from exc
    if not data or len(data) > MAX_BYTES or base64.b64encode(data).decode() != encoded:
        raise ApiError(400, "Ảnh phải hợp lệ và không vượt quá 5MB")

    if mime_type == "image/jpeg":
        valid = len(data) >= 4 and data[:3] == b"\xff\xd8\xff" and data[-2:] == b"\xff\xd9"
    elif mime_type == "image/png":
        valid = data[:8] == b"\x89PNG\r\n\x1a\n"
    else:
        valid = data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    if not valid:
        raise ApiError(400, "Nội dung ảnh không khớp loại JPEG/PNG/WebP")
    return data


@router.post("", status_code=201, dependencies=[Depends(upload_rate_limit)])
def upload_image(
    payload: UploadIn,
    user: CurrentUser = Depends(account_limit("UPLOAD_IMAGE", 50, 3_600_000)),
):
    data = decode_image(payload.base64, payload.mimeType)
    extension = EXTENSIONS[payload.mimeType]
    private_file = payload.purpose == "EVIDENCE"
    name = f"{user.id}-{uuid.uuid4()}.{extension}" if private_file else f"{uuid.uuid4()}.{extension}"

    directory = EVIDENCE_DIR if private_file else UPLOAD_DIR
    directory.mkdir(parents=True, exist_ok=True, mode=0o700 if private_file else 0o755)
    path = directory / name
    with open(path, "xb") as handle:
        os.chmod(path, 0o600 if private_file else 0o644)
        handle.write(data)

    folder = "api/v1/upload/evidence" if private_file else "uploads"
    return {"message": "Đã lưu ảnh", "url": f"{origin()}/{folder}/{name}"}


@router.get("/evidence/{name}")
def read_evidence(
    name: str,
    user: CurrentUser = Depends(current_user),
    db: Session = Depends(get_db),
):
    if len(name) > 100 or not NAME_RE.match(name):
        raise ApiError(404, "Không tìm thấy bằng chứng")
    url = f"{origin()}/api/v1/upload/evidence/{name}"
    if not may_read_evidence(db, user, url):
        raise ApiError(403, "Không có quyền xem bằng chứng")

    path = EVIDENCE_DIR / name
    if not path.is_file():
        raise ApiError(404, "Không tìm thấy bằng chứng")
    return FileResponse(
        path,
        media_type=MEDIA_TYPES[name.rsplit(".", 1)[1]],
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
    )
