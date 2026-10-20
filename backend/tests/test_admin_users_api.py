"""Test tích hợp admin-users.js: danh sách, khóa/mở, xác minh, phân quyền."""
from sqlalchemy import select

from app.db import SessionLocal
from app.models import AuditLog, Notification, SellerProfile, User


def _login(client, user):
    return client.post(
        "/api/v1/auth/login", json={"email": user["email"], "password": user["password"]}
    )


def test_nguoi_thuong_khong_vao_duoc(make_user, client):
    user = make_user()
    response = client.get("/api/v1/admin/users", headers=user["headers"])
    assert response.status_code == 403
    assert response.json() == {"message": "Bạn không có quyền thực hiện thao tác này"}


def test_danh_sach_va_bo_loc(make_user, client):
    admin = make_user(roles=["ADMIN_FINANCE"])
    target = make_user()

    response = client.get("/api/v1/admin/users", headers=admin["headers"], params={"q": target["email"]})
    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["total"] == 1
    item = body["data"][0]
    assert item["id"] == target["id"]
    assert item["roles"] == ["BUYER"]
    assert item["_count"] == {"listings": 0, "ordersBuyer": 0}
    assert set(item) == {
        "id", "fullName", "email", "phone", "avatarUrl", "status", "isVerified",
        "idVerified", "banReason", "createdAt", "roles", "_count",
    }

    by_role = client.get("/api/v1/admin/users", headers=admin["headers"], params={"role": "BUYER", "limit": 100})
    assert all("BUYER" in row["roles"] for row in by_role.json()["data"])

    by_status = client.get("/api/v1/admin/users", headers=admin["headers"], params={"status": "BANNED", "limit": 100})
    assert all(row["status"] == "BANNED" for row in by_status.json()["data"])


def test_thong_ke(make_user, client):
    admin = make_user(roles=["ADMIN_CONTENT"])
    body = client.get("/api/v1/admin/users/stats", headers=admin["headers"]).json()
    assert set(body) == {"total", "active", "pendingVerification", "banned"}
    assert body["total"] >= body["active"] + body["banned"]


def test_khong_tu_khoa_chinh_minh(make_user, client):
    admin = make_user(roles=["ADMIN_FINANCE"])
    response = client.patch(
        f"/api/v1/admin/users/{admin['id']}/lock", headers=admin["headers"], json={"reason": "thử"}
    )
    assert response.status_code == 400
    assert response.json() == {"message": "Không thể tự khóa chính mình"}


def test_khoa_va_mo_khoa_tai_khoan(make_user, client):
    admin = make_user(roles=["ADMIN_FINANCE"])
    target = make_user()

    locked = client.patch(
        f"/api/v1/admin/users/{target['id']}/lock", headers=admin["headers"], json={"reason": "Spam"}
    )
    assert locked.status_code == 200
    assert locked.json() == {"message": "Đã khóa tài khoản"}

    assert _login(client, target).status_code == 403
    assert client.get("/api/v1/auth/me", headers=target["headers"]).status_code == 401

    with SessionLocal() as db:
        row = db.execute(select(User).where(User.id == target["id"])).scalar_one()
        assert row.status == "BANNED"
        assert row.banReason == "Spam"
        assert row.bannedAt is not None
        notifications = db.execute(
            select(Notification).where(Notification.userId == target["id"])
        ).scalars().all()
        assert [n.title for n in notifications] == ["Tài khoản của bạn đã bị khóa"]
        assert notifications[0].body == "Lý do: Spam"
        audit = db.execute(select(AuditLog).where(AuditLog.target == f"user:{target['id']}")).scalars().all()
        assert [a.action for a in audit] == ["LOCK_USER"]
        assert audit[0].detail == {"reason": "Spam"}

    unlocked = client.patch(
        f"/api/v1/admin/users/{target['id']}/unlock", headers=admin["headers"], json={"reason": "Đã xác minh nhầm"}
    )
    assert unlocked.json() == {"message": "Đã mở khóa tài khoản"}
    assert _login(client, target).status_code == 200

    with SessionLocal() as db:
        row = db.execute(select(User).where(User.id == target["id"])).scalar_one()
        assert row.status == "ACTIVE"
        assert row.banReason is None and row.bannedAt is None


def test_khoa_can_ly_do(make_user, client):
    admin = make_user(roles=["ADMIN_FINANCE"])
    target = make_user()
    response = client.patch(
        f"/api/v1/admin/users/{target['id']}/lock", headers=admin["headers"], json={"reason": "  "}
    )
    assert response.status_code == 400
    assert response.json()["details"][0]["field"] == "reason"


def test_duyet_xac_minh(make_user, client):
    admin = make_user(roles=["ADMIN_CONTENT"])
    target = make_user()
    response = client.patch(f"/api/v1/admin/users/{target['id']}/verify", headers=admin["headers"])
    assert response.json() == {"message": "Đã duyệt xác minh"}
    with SessionLocal() as db:
        assert db.execute(select(User.idVerified).where(User.id == target["id"])).scalar_one() is True


def test_xac_minh_tai_khoan_khong_ton_tai(make_user, client):
    admin = make_user(roles=["ADMIN_CONTENT"])
    response = client.patch("/api/v1/admin/users/99999999/verify", headers=admin["headers"])
    assert response.status_code == 404
    assert response.json() == {"message": "Không tìm thấy dữ liệu"}


def test_gan_quyen_can_quyen_quan_ly_phan_quyen(make_user, client):
    admin = make_user(roles=["ADMIN_FINANCE"])  # không có canManageRoles
    target = make_user()
    response = client.patch(
        f"/api/v1/admin/users/{target['id']}/roles", headers=admin["headers"], json={"roles": ["SELLER"]}
    )
    assert response.status_code == 403
    assert response.json() == {"message": "Cần quyền quản lý phân quyền riêng"}


def test_gan_quyen_tao_ho_so_nguoi_ban_va_thu_hoi_phien(make_user, client):
    admin = make_user(roles=["ADMIN_FINANCE"], can_manage_roles=True)
    target = make_user()

    response = client.patch(
        f"/api/v1/admin/users/{target['id']}/roles",
        headers=admin["headers"],
        json={"roles": ["BUYER", "SELLER"]},
    )
    assert response.status_code == 200
    assert response.json() == {"message": "Đã cập nhật phân quyền", "roles": ["BUYER", "SELLER"]}

    with SessionLocal() as db:
        profile = db.execute(select(SellerProfile).where(SellerProfile.userId == target["id"])).scalar_one()
        assert profile.shopName == "Shop Tài khoản QA"
        target_row = db.execute(select(User).where(User.id == target["id"])).scalar_one()
        assert target_row.sessionVersion == 1
        assert target_row.canManageRoles is False

    # Phiên cũ bị thu hồi, phải đăng nhập lại.
    assert client.get("/api/v1/auth/me", headers=target["headers"]).status_code == 401
    fresh = _login(client, target).json()
    assert sorted(fresh["user"]["roles"]) == ["BUYER", "SELLER"]


def test_khong_tu_doi_quyen_chinh_minh(make_user, client):
    admin = make_user(roles=["ADMIN_FINANCE"], can_manage_roles=True)
    response = client.patch(
        f"/api/v1/admin/users/{admin['id']}/roles", headers=admin["headers"], json={"roles": ["BUYER"]}
    )
    assert response.status_code == 403
    assert response.json() == {"message": "Không được thay đổi vai trò của chính mình"}


def test_khoa_admin_khac_can_quan_ly_phan_quyen(make_user, client):
    admin = make_user(roles=["ADMIN_CONTENT"])
    other_admin = make_user(roles=["ADMIN_CONTENT"])
    response = client.patch(
        f"/api/v1/admin/users/{other_admin['id']}/lock",
        headers=admin["headers"],
        json={"reason": "thử"},
    )
    assert response.status_code == 403
    assert response.json() == {"message": "Cần quyền quản lý phân quyền riêng"}


def test_danh_sach_quyen_sai_bi_tu_choi(make_user, client):
    admin = make_user(roles=["ADMIN_FINANCE"], can_manage_roles=True)
    target = make_user()
    response = client.patch(
        f"/api/v1/admin/users/{target['id']}/roles", headers=admin["headers"], json={"roles": []}
    )
    assert response.status_code == 400
    assert response.json()["details"][0]["field"] == "roles"
