"""Test tích hợp nhóm auth — chạy trên database thật, tự tạo và tự dọn tài khoản thử.

Tài khoản thử có email riêng nên không đụng dữ liệu seed. Mọi thứ nó tạo ra
(User, UserRole, Wallet, ActionQuota, thư trong .local/mail) đều bị xoá ở teardown.
"""
import json
import re
import time
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.config import settings
from app.db import SessionLocal
from app.main import create_app
from app.models import ActionQuota, User, UserRole, Wallet

MAIL_DIR = Path(__file__).resolve().parents[1] / ".local" / "mail"


@pytest.fixture
def client():
    return TestClient(create_app(), raise_server_exceptions=False)


@pytest.fixture
def account():
    email = f"qa-python-{uuid.uuid4().hex[:10]}@nola2hand.vn"
    mail_before = set(MAIL_DIR.glob("*.json")) if MAIL_DIR.exists() else set()
    yield {"email": email, "password": "matkhau123", "fullName": "Tài khoản QA"}
    mail_after = set(MAIL_DIR.glob("*.json")) if MAIL_DIR.exists() else set()
    for file in mail_after - mail_before:
        file.unlink()

    with SessionLocal() as db:
        user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if user is not None:
            db.execute(delete(ActionQuota).where(ActionQuota.userId == user.id))
            db.execute(delete(UserRole).where(UserRole.userId == user.id))
            db.execute(delete(Wallet).where(Wallet.userId == user.id))
            db.execute(delete(User).where(User.id == user.id))
            db.commit()


def _register(client, account):
    return client.post(
        "/api/v1/auth/register",
        json={"fullName": account["fullName"], "email": account["email"], "password": account["password"]},
    )


def _login(client, account, password=None):
    return client.post(
        "/api/v1/auth/login",
        json={"email": account["email"], "password": password or account["password"]},
    )


def _latest_otp(mail_before: set[Path]) -> str:
    """OTP nằm trong thư ghi ra .local/mail khi chưa cấu hình Resend."""
    files = sorted(MAIL_DIR.glob("*.json"), key=lambda f: f.stat().st_mtime)
    text = json.loads(files[-1].read_text())["text"]
    return re.search(r"Mã OTP của bạn: (\d{6})", text).group(1)


def test_dang_ky_tra_201_va_khong_lo_ma_otp(client, account):
    response = _register(client, account)
    assert response.status_code == 201
    body = response.json()
    assert body["message"] == "Đăng ký thành công. Thư xác nhận được lưu trong hộp thư development trên máy chủ."
    assert body["emailDelivery"] == "LOCAL_OUTBOX"
    assert body["user"] == {"id": body["user"]["id"], "fullName": account["fullName"], "email": account["email"]}
    assert body["token"]
    assert "otp" not in json.dumps(body).lower()
    assert "hash" not in json.dumps(body).lower()


def test_dang_ky_trung_email_tra_409(client, account):
    _register(client, account)
    response = _register(client, account)
    assert response.status_code == 409
    assert response.json() == {"message": "Email đã được đăng ký"}


def test_dang_nhap_sai_mat_khau(client, account):
    _register(client, account)
    response = _login(client, account, "saimatkhau1")
    assert response.status_code == 401
    assert response.json() == {"message": "Email hoặc mật khẩu chưa đúng"}


def test_dang_nhap_tra_du_lieu_giong_ban_node(client, account):
    _register(client, account)
    body = _login(client, account).json()
    assert set(body) == {"token", "user"}
    assert set(body["user"]) == {"id", "fullName", "email", "avatarUrl", "roles", "canManageRoles"}
    assert body["user"]["roles"] == ["BUYER"]
    assert body["user"]["canManageRoles"] is False


def test_me_khong_lo_hash_va_co_vi(client, account):
    _register(client, account)
    token = _login(client, account).json()["token"]
    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    body = response.json()
    for secret in ("passwordHash", "passwordResetTokenHash", "emailVerificationTokenHash"):
        assert secret not in body
    assert body["roles"] == ["BUYER"]
    assert body["wallet"] == {"balance": 0, "pendingBalance": 0}
    assert body["createdAt"].endswith("Z")  # giống Prisma, để JS hiểu là UTC


def test_thieu_token_va_token_sai(client):
    assert client.get("/api/v1/auth/me").json() == {"message": "Thiếu token đăng nhập"}
    response = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer abc.def.ghi"})
    assert response.status_code == 401
    assert response.json() == {"message": "Token không hợp lệ hoặc đã hết hạn"}


def test_xac_nhan_email_bang_otp(client, account):
    mail_before = set(MAIL_DIR.glob("*.json")) if MAIL_DIR.exists() else set()
    _register(client, account)
    otp = _latest_otp(mail_before)

    wrong = client.post("/api/v1/auth/verify-otp", json={"email": account["email"], "otp": "000000"})
    assert wrong.status_code == 400
    assert wrong.json() == {"message": "Mã OTP chưa đúng (còn 4 lượt)"}

    good = client.post("/api/v1/auth/verify-otp", json={"email": account["email"], "otp": otp})
    assert good.status_code == 200
    assert good.json() == {"message": "Đã xác nhận email thành công"}


def test_dang_xuat_thu_hoi_phien_cu(client, account):
    _register(client, account)
    token = _login(client, account).json()["token"]
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 200

    out = client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert out.json() == {"message": "Đã đăng xuất và thu hồi các phiên đăng nhập."}

    after = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert after.status_code == 401
    assert after.json() == {"message": "Phiên đã bị thu hồi. Hãy đăng nhập lại."}


def test_quen_mat_khau_khong_tiet_lo_email_ton_tai(client, account):
    response = client.post("/api/v1/auth/forgot-password", json={"email": f"khong-ton-tai-{uuid.uuid4().hex[:8]}@nola2hand.vn"})
    assert response.status_code == 200
    assert response.json() == {"message": "Nếu email tồn tại, thư được lưu trong hộp thư development trên máy chủ."}


def test_du_lieu_sai_tra_400_kem_chi_tiet(client):
    response = client.post("/api/v1/auth/login", json={"email": "khong-phai-email", "password": ""})
    assert response.status_code == 400
    body = response.json()
    assert body["message"] == "Dữ liệu không hợp lệ"
    assert {d["field"] for d in body["details"]} == {"email", "password"}


def test_mat_khau_yeu_bi_tu_choi(client):
    response = client.post(
        "/api/v1/auth/register",
        json={"fullName": "Người Thử", "email": f"qa-{uuid.uuid4().hex[:8]}@nola2hand.vn", "password": "khongcoso"},
    )
    assert response.status_code == 400
    assert response.json()["details"][0]["message"] == "Mật khẩu cần có cả chữ và số"


def test_mail_limit_khong_chan_ngay(client, account):
    # mailLimit(10) mỗi giờ: vài lượt đầu phải đi qua, không bị 429.
    for _ in range(3):
        response = client.post("/api/v1/auth/forgot-password", json={"email": account["email"]})
        assert response.status_code == 200


def test_dang_nhap_tai_khoan_bi_khoa(client, account):
    _register(client, account)
    with SessionLocal() as db:
        db.execute(
            User.__table__.update()
            .where(User.email == account["email"])
            .values(status="BANNED", banReason="Vi phạm thử nghiệm")
        )
        db.commit()
    response = _login(client, account)
    assert response.status_code == 403
    assert response.json() == {"message": "Tài khoản đã bị khóa: Vi phạm thử nghiệm"}


def test_dang_nhap_lien_tuc_khong_bi_chan(client, account):
    """Không đặt rate limit cho /login trong bản Node, giữ nguyên như vậy."""
    _register(client, account)
    start = time.time()
    for _ in range(5):
        assert _login(client, account).status_code == 200
    assert time.time() - start < 30
