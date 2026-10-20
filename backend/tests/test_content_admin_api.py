"""Test tích hợp nhóm quản trị nội dung: khuyến mãi, banner, nhật ký quản trị."""
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import update

from app.db import SessionLocal
from app.models import AuditLog, Promo



def _iso(days: int, hours: int = 0) -> str:
    moment = datetime.now(timezone.utc) + timedelta(days=days, hours=hours)
    return moment.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _promo(**overrides):
    code = f"qa-promo-{uuid.uuid4().hex[:8]}"
    body = {
        "name": "Giảm 10% QA",
        "type": "VOUCHER",
        "code": code,
        "discountType": "PERCENT",
        "discountValue": 10,
        "maxDiscount": 15_000,
        "minOrder": 50_000,
        "usageLimit": 10,
        "startsAt": _iso(0, -1),
        "endsAt": _iso(7),
        "status": "ACTIVE",
    }
    body.update(overrides)
    return body


def test_khuyen_mai_tao_kiem_tra_va_xoa(make_user, client):
    admin = make_user(["ADMIN_CONTENT"])
    buyer = make_user()

    created = client.post("/api/v1/promos/admin", headers=admin["headers"], json=_promo())
    assert created.status_code == 201, created.text
    promo = created.json()
    assert promo["code"].startswith("qa-promo-")
    assert promo["usedCount"] == 0
    assert promo["startsAt"].endswith("Z")

    public = client.get("/api/v1/promos").json()
    assert promo["id"] in [row["id"] for row in public]

    ok = client.post(
        "/api/v1/promos/validate",
        headers=buyer["headers"],
        json={"code": promo["code"], "orderAmount": 200_000},
    )
    assert ok.status_code == 200
    assert ok.json() == {
        "valid": True,
        "promo": {"name": "Giảm 10% QA", "code": promo["code"]},
        "discount": 15_000,
    }

    small = client.post(
        "/api/v1/promos/validate",
        headers=buyer["headers"],
        json={"code": promo["code"], "orderAmount": 10_000},
    )
    assert small.status_code == 400
    assert small.json() == {"valid": False, "message": "Đơn tối thiểu 50.000đ"}

    with SessionLocal() as db:
        db.execute(update(Promo).where(Promo.id == promo["id"]).values(usedCount=10))
        db.commit()
    used_up = client.post(
        "/api/v1/promos/validate",
        headers=buyer["headers"],
        json={"code": promo["code"], "orderAmount": 200_000},
    )
    assert used_up.json()["message"] == "Mã đã hết lượt sử dụng"

    amount_promo = client.post(
        "/api/v1/promos/admin",
        headers=admin["headers"],
        json=_promo(name="Giảm 20k QA", discountType="AMOUNT", discountValue=20_000, maxDiscount=None),
    ).json()
    amount_ok = client.post(
        "/api/v1/promos/validate",
        headers=buyer["headers"],
        json={"code": amount_promo["code"], "orderAmount": 100_000},
    )
    assert amount_ok.json()["discount"] == 20_000

    expired = client.post(
        "/api/v1/promos/admin",
        headers=admin["headers"],
        json=_promo(name="Hết hạn QA", startsAt=_iso(-10), endsAt=_iso(-1)),
    ).json()
    expired_check = client.post(
        "/api/v1/promos/validate",
        headers=buyer["headers"],
        json={"code": expired["code"], "orderAmount": 200_000},
    )
    assert expired_check.json()["message"] == "Mã không hợp lệ hoặc đã hết hạn"
    assert expired["id"] not in [row["id"] for row in client.get("/api/v1/promos").json()]

    listed = client.get(
        "/api/v1/promos/admin/all",
        headers=admin["headers"],
        params={"status": "ACTIVE", "type": "VOUCHER"},
    ).json()
    assert promo["id"] in [row["id"] for row in listed["data"]]
    assert client.get("/api/v1/promos/admin/all", headers=buyer["headers"]).status_code == 403

    paused = client.patch(
        f"/api/v1/promos/admin/{promo['id']}",
        headers=admin["headers"],
        json={"status": "PAUSED"},
    )
    assert paused.status_code == 200, paused.text
    assert paused.json()["status"] == "PAUSED"
    assert paused.json()["name"] == "Giảm 10% QA"
    assert promo["id"] not in [row["id"] for row in client.get("/api/v1/promos").json()]

    assert client.patch(
        "/api/v1/promos/admin/999999", headers=admin["headers"], json={"status": "PAUSED"}
    ).status_code == 404

    removed = client.delete(f"/api/v1/promos/admin/{promo['id']}", headers=admin["headers"])
    assert removed.json() == {"message": "Đã xoá khuyến mãi"}
    assert client.delete(
        f"/api/v1/promos/admin/{promo['id']}", headers=admin["headers"]
    ).status_code == 404


def test_banner_tao_loc_va_sua(make_user, client):
    admin = make_user(["ADMIN_CONTENT"])
    seller = make_user(["SELLER"], verified=True)

    created = client.post(
        "/api/v1/banners/admin",
        headers=admin["headers"],
        json={
            "title": "qa-banner-hero",
            "imageUrl": "https://cdn.example.com/banner.png",
            "linkUrl": "",
            "position": "HOME_HERO",
            "startsAt": _iso(-1),
            "endsAt": _iso(7),
            "status": "ACTIVE",
        },
    )
    assert created.status_code == 201, created.text
    banner = created.json()
    assert banner["linkUrl"] == ""
    assert banner["views"] == 0

    assert client.post(
        "/api/v1/banners/admin",
        headers=admin["headers"],
        json={
            "title": "qa-banner-sai",
            "imageUrl": "khong-phai-url",
            "position": "HOME_HERO",
            "startsAt": _iso(0),
            "endsAt": _iso(1),
        },
    ).status_code == 400

    assert client.post(
        "/api/v1/banners/admin", headers=seller["headers"], json={}
    ).status_code == 403

    hero = client.get("/api/v1/banners", params={"position": "HOME_HERO"}).json()
    assert banner["id"] in [row["id"] for row in hero]
    other = client.get("/api/v1/banners", params={"position": "CATEGORY"}).json()
    assert banner["id"] not in [row["id"] for row in other]

    patched = client.patch(
        f"/api/v1/banners/admin/{banner['id']}",
        headers=admin["headers"],
        json={"status": "DRAFT"},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["status"] == "DRAFT"
    assert banner["id"] not in [
        row["id"] for row in client.get("/api/v1/banners", params={"position": "HOME_HERO"}).json()
    ]

    assert client.patch(
        f"/api/v1/banners/admin/{banner['id']}",
        headers=admin["headers"],
        json={"title": "   "},
    ).status_code == 400

    removed = client.delete(f"/api/v1/banners/admin/{banner['id']}", headers=admin["headers"])
    assert removed.json() == {"message": "Đã xoá banner"}


def test_nhat_ky_quan_tri_loc_va_ngay(make_user, client):
    admin = make_user(["ADMIN_CONTENT"])
    seller = make_user(["SELLER"], verified=True)

    with SessionLocal() as db:
        db.add(
            AuditLog(
                adminId=admin["id"],
                action="QA_AUDIT_ACTION",
                target="qa:1",
                detail={"source": "test"},
            )
        )
        db.commit()

    listed = client.get(
        "/api/v1/admin/audit", headers=admin["headers"], params={"q": "QA_AUDIT_ACTION"}
    ).json()
    assert listed["meta"]["total"] == 1
    assert listed["data"][0]["target"] == "qa:1"
    assert listed["data"][0]["admin"]["fullName"] == "Tài khoản QA"

    none = client.get(
        "/api/v1/admin/audit", headers=admin["headers"], params={"q": "không-có-gì"}
    ).json()
    assert none["meta"]["total"] == 0

    bad_range = client.get(
        "/api/v1/admin/audit",
        headers=admin["headers"],
        params={"from": "2026-02-01", "to": "2026-01-01"},
    )
    assert bad_range.status_code == 400

    assert client.get("/api/v1/admin/audit", headers=seller["headers"]).status_code == 403
