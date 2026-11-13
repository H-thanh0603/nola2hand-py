"""Client gọi sidecar `video-agent` (Node + Chrome + Muse) qua HTTP nội bộ.

Sidecar chỉ nghe 127.0.0.1 — không lộ ra ngoài. Mọi lỗi mạng quy về ApiError 503 để
người dùng thấy "dịch vụ tạo video chưa sẵn sàng" thay vì traceback.
"""
from __future__ import annotations

import httpx

from ..config import settings
from ..errors import ApiError

TIMEOUT = httpx.Timeout(15.0, connect=5.0)

def _url(path: str) -> str:
    return settings.video_agent_url.rstrip("/") + path

def healthy() -> bool:
    try:
        response = httpx.get(_url("/health"), timeout=TIMEOUT)
        return response.status_code == 200 and bool(response.json().get("ok"))
    except (httpx.HTTPError, ValueError):
        return False

def submit(prompt: str, images: list[dict], output_dir: str) -> str:
    """Gửi job sang sidecar, trả id job bên đó."""
    try:
        response = httpx.post(
            _url("/jobs"),
            json={"prompt": prompt, "images": images, "outputDir": output_dir},
            timeout=TIMEOUT,
        )
    except httpx.HTTPError as exc:
        raise ApiError(503, "Dịch vụ tạo video chưa sẵn sàng") from exc
    if response.status_code >= 400:
        raise ApiError(503, "Dịch vụ tạo video chưa sẵn sàng")
    return str(response.json()["id"])

def status(agent_job_id: str) -> dict:
    """Hỏi trạng thái job bên sidecar.

    Giữ nguyên mã lỗi thật: 404 nghĩa là sidecar đã quên job (restart, hàng đợi trong
    RAM) — không bao giờ trả lời nữa nên bên gọi phải kết luận FAILED ngay. Các lỗi
    khác (503, timeout) chỉ là tạm thời, còn thử lại được.
    """
    try:
        response = httpx.get(_url(f"/jobs/{agent_job_id}"), timeout=TIMEOUT)
    except httpx.HTTPError as exc:
        raise ApiError(503, "Không hỏi được trạng thái job video") from exc
    if response.status_code == 404:
        raise ApiError(404, "Job không còn trên dịch vụ tạo video")
    if response.status_code >= 400:
        raise ApiError(503, "Không hỏi được trạng thái job video")
    return response.json()

def cancel(agent_job_id: str) -> None:
    try:
        httpx.post(_url(f"/jobs/{agent_job_id}/cancel"), timeout=TIMEOUT)
    except httpx.HTTPError:
        pass  # huỷ là best-effort; job phía mình vẫn được đánh dấu CANCELLED
