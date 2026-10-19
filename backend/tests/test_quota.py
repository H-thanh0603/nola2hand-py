"""Hạn mức theo tài khoản — bảng ActionQuota, dùng tài khoản seed có sẵn trong DB."""
from datetime import datetime, timezone

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.db import SessionLocal
from app.main import create_app
from app.models import ActionQuota, User
from app.quota import account_limit, window_start
from app.security import create_access_token

ACTION = "TEST_QUOTA"


@pytest.fixture
def seeded_user():
    with SessionLocal() as db:
        user = db.execute(select(User).where(User.status == "ACTIVE").limit(1)).scalar_one()
        return user.id, user.sessionVersion


@pytest.fixture(autouse=True)
def clean_quota_rows():
    def wipe():
        with SessionLocal() as db:
            db.execute(delete(ActionQuota).where(ActionQuota.action == ACTION))
            db.commit()

    wipe()
    yield
    wipe()


@pytest.fixture
def client():
    app = create_app()

    @app.get("/thu")
    def thu(user=Depends(account_limit(ACTION, 2, 60_000))):
        return {"ok": True, "user": user.id}

    return TestClient(app, raise_server_exceptions=False)


def test_cua_so_tinh_theo_moc_thoi_gian():
    # 12:34:56.789 với cửa sổ 1 phút → 12:34:00
    ms = int(datetime(2026, 10, 19, 12, 34, 56, 789000, tzinfo=timezone.utc).timestamp() * 1000)
    assert window_start(ms, 60_000) == datetime(2026, 10, 19, 12, 34, 0)
    assert window_start(ms, 15 * 60_000) == datetime(2026, 10, 19, 12, 30, 0)


def test_thieu_token_thi_401(client):
    response = client.get("/thu")
    assert response.status_code == 401
    assert response.json() == {"message": "Thiếu token đăng nhập"}


def test_qua_so_lan_thi_429_kem_retry_after(client, seeded_user):
    user_id, session_version = seeded_user
    headers = {"Authorization": f"Bearer {create_access_token(user_id, session_version)}"}

    assert client.get("/thu", headers=headers).status_code == 200
    assert client.get("/thu", headers=headers).status_code == 200

    blocked = client.get("/thu", headers=headers)
    assert blocked.status_code == 429
    assert blocked.json() == {"message": "Đã đạt giới hạn thao tác. Vui lòng thử lại sau."}
    assert 0 <= int(blocked.headers["Retry-After"]) <= 60


def test_token_cua_phien_da_thu_hoi_bi_tu_choi(client, seeded_user):
    user_id, session_version = seeded_user
    headers = {"Authorization": f"Bearer {create_access_token(user_id, session_version + 99)}"}
    response = client.get("/thu", headers=headers)
    assert response.status_code == 401
    assert response.json() == {"message": "Phiên đã bị thu hồi. Hãy đăng nhập lại."}
