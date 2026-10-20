"""Gửi thư tài khoản — port src/services/mail.js (Resend, thiếu key thì ghi ra .local/mail)."""
import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx

from ..config import settings
from ..errors import ApiError

LOCAL_OUTBOX = Path(__file__).resolve().parents[2] / ".local" / "mail"


def _message(purpose: str, token: str, otp: str) -> tuple[str, str]:
    origin = settings.app_url.rstrip("/")
    link = f"{origin}/#/{'verify' if purpose == 'verify' else 'reset'}/{token}"
    subject = "Xác nhận email Nola2Hand" if purpose == "verify" else "Đặt lại mật khẩu Nola2Hand"
    text = (
        f"{subject}\n\nMã OTP của bạn: {otp} (hiệu lực 10 phút, tối đa 5 lần nhập sai)"
        f"\n\nHoặc mở liên kết sau: {link}\n\nNếu bạn không yêu cầu, hãy bỏ qua thư này."
    )
    return subject, text


def email_mode() -> str:
    if settings.resend_api_key and settings.mail_from:
        return "EMAIL"
    return "UNAVAILABLE" if not settings.is_development else "LOCAL_OUTBOX"


def send_account_email(to: str, purpose: str, token: str, otp: str) -> str:
    """Trả 'EMAIL' | 'LOCAL_OUTBOX'; ném ApiError(503) khi dịch vụ thư hỏng."""
    subject, text = _message(purpose, token, otp)

    if settings.resend_api_key and settings.mail_from:
        idempotency_key = hashlib.sha256(f"{purpose}:{token}".encode()).hexdigest()
        try:
            response = httpx.post(
                "https://api.resend.com/emails",
                timeout=10,
                headers={
                    "Authorization": f"Bearer {settings.resend_api_key}",
                    "Content-Type": "application/json",
                    "Idempotency-Key": idempotency_key,
                },
                json={"from": settings.mail_from, "to": [to], "subject": subject, "text": text},
            )
        except httpx.HTTPError as exc:
            raise ApiError(503, "Dịch vụ email chưa gửi được thư") from exc
        if response.status_code >= 400:
            raise ApiError(503, "Dịch vụ email chưa gửi được thư")
        return "EMAIL"

    if not settings.is_development:
        raise ApiError(503, "Chưa cấu hình dịch vụ email")

    LOCAL_OUTBOX.mkdir(parents=True, exist_ok=True, mode=0o700)
    file = LOCAL_OUTBOX / f"{uuid.uuid4()}.json"
    file.write_text(
        json.dumps(
            {"to": to, "subject": subject, "text": text, "createdAt": datetime.now(timezone.utc).isoformat()},
            ensure_ascii=False,
        )
    )
    file.chmod(0o600)
    return "LOCAL_OUTBOX"
