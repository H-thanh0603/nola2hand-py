"""Fixture dùng chung cho test tích hợp: client + tài khoản thử tự dọn."""
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select, update

from app.db import SessionLocal
from app.main import create_app
from app.models import (
    ActionQuota,
    Address,
    AuditLog,
    Notification,
    Role,
    SellerProfile,
    User,
    UserRole,
    Wallet,
)

MAIL_DIR = Path(__file__).resolve().parents[1] / ".local" / "mail"


@pytest.fixture
def client():
    return TestClient(create_app(), raise_server_exceptions=False)


@pytest.fixture
def make_user(client):
    """Đăng ký + đăng nhập một tài khoản thật; teardown xoá sạch mọi thứ nó tạo."""
    created: list[int] = []
    mail_before = set(MAIL_DIR.glob("*.json")) if MAIL_DIR.exists() else set()

    def factory(roles: list[str] | None = None, can_manage_roles: bool = False) -> dict:
        email = f"qa-py-{uuid.uuid4().hex[:10]}@nola2hand.vn"
        password = "matkhau123"
        response = client.post(
            "/api/v1/auth/register",
            json={"fullName": "Tài khoản QA", "email": email, "password": password},
        )
        assert response.status_code == 201, response.text
        user_id = response.json()["user"]["id"]

        if roles or can_manage_roles:
            with SessionLocal() as db:
                for name in roles or []:
                    role_id = db.execute(select(Role.id).where(Role.name == name)).scalar_one()
                    db.add(UserRole(userId=user_id, roleId=role_id))
                if can_manage_roles:
                    db.execute(update(User).where(User.id == user_id).values(canManageRoles=True))
                db.commit()

        token = client.post(
            "/api/v1/auth/login", json={"email": email, "password": password}
        ).json()["token"]
        created.append(user_id)
        return {
            "id": user_id,
            "email": email,
            "password": password,
            "token": token,
            "headers": {"Authorization": f"Bearer {token}"},
        }

    yield factory

    mail_after = set(MAIL_DIR.glob("*.json")) if MAIL_DIR.exists() else set()
    for file in mail_after - mail_before:
        file.unlink()

    with SessionLocal() as db:
        for user_id in created:
            db.execute(delete(AuditLog).where(AuditLog.adminId == user_id))
            db.execute(delete(Notification).where(Notification.userId == user_id))
            db.execute(delete(Address).where(Address.userId == user_id))
            db.execute(delete(SellerProfile).where(SellerProfile.userId == user_id))
            db.execute(delete(UserRole).where(UserRole.userId == user_id))
            db.execute(delete(Wallet).where(Wallet.userId == user_id))
            db.execute(delete(ActionQuota).where(ActionQuota.userId == user_id))
            db.execute(delete(User).where(User.id == user_id))
        db.commit()
