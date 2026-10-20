"""Test tích hợp categories, posts, shops."""
from sqlalchemy import select

from app.db import SessionLocal
from app.models import Post


def test_cay_danh_muc_co_con_va_so_tin(client):
    response = client.get("/api/v1/categories")
    assert response.status_code == 200
    roots = response.json()
    assert roots, "database seed phải có danh mục gốc"
    first = roots[0]
    assert set(first) >= {"id", "name", "slug", "children", "_count"}
    assert isinstance(first["children"], list)
    assert isinstance(first["_count"]["listings"], int)
    assert all(root["parentId"] is None for root in roots)


def test_thong_so_san_pham(client):
    body = client.get("/api/v1/categories/specifications").json()
    assert body["dien-tu-cu"]["batteryHealth"] == "Sức khỏe pin (%)"
    assert set(body) == {"dien-tu-cu", "noi-that", "do-gia-dung"}


def test_admin_tao_sua_xoa_danh_muc(make_user, client):
    admin = make_user(roles=["ADMIN_CONTENT"])
    created = client.post(
        "/api/v1/categories",
        headers=admin["headers"],
        json={"name": "  Danh Mục QA  ", "slug": " QA-CAT-THU ", "feePct": 7.5},
    )
    assert created.status_code == 201
    category = created.json()
    assert category["name"] == "Danh Mục QA"
    assert category["slug"] == "qa-cat-thu"
    assert category["feePct"] == 7.5

    patched = client.patch(
        f"/api/v1/categories/{category['id']}", headers=admin["headers"], json={"feePct": 3}
    )
    assert patched.json()["feePct"] == 3

    assert client.delete(f"/api/v1/categories/{category['id']}", headers=admin["headers"]).json() == {
        "message": "Đã xoá danh mục"
    }
    missing = client.patch(
        f"/api/v1/categories/{category['id']}", headers=admin["headers"], json={"name": "X"}
    )
    assert missing.status_code == 404
    assert missing.json() == {"message": "Không tìm thấy dữ liệu"}


def test_khong_xoa_duoc_danh_muc_con_tin(make_user, client):
    admin = make_user(roles=["ADMIN_CONTENT"])
    roots = client.get("/api/v1/categories").json()
    busy = next(root for root in roots if root["_count"]["listings"] > 0)

    response = client.delete(f"/api/v1/categories/{busy['id']}", headers=admin["headers"])
    assert response.status_code == 400
    assert response.json()["message"].startswith(f"Danh mục còn {busy['_count']['listings']} tin đăng")


def test_tao_danh_muc_can_quyen_noi_dung(make_user, client):
    seller = make_user(roles=["SELLER"])
    response = client.post(
        "/api/v1/categories", headers=seller["headers"], json={"name": "X", "slug": "qa-cat-x"}
    )
    assert response.status_code == 403


def test_bai_viet_vong_doi(make_user, client):
    seller = make_user(roles=["SELLER"])
    payload = {
        "title": "Kinh nghiệm chọn mua laptop cũ",
        "excerpt": "Vài lưu ý khi mua laptop đã qua sử dụng",
        "content": "Nội dung đủ dài để vượt qua giới hạn 50 ký tự của bản Node khi tạo bài viết.",
        "status": "PUBLISHED",
    }
    created = client.post("/api/v1/posts", headers=seller["headers"], json=payload)
    assert created.status_code == 201
    post = created.json()
    assert post["slug"].startswith("kinh-nghiem-chon-mua-laptop-cu-")
    assert post["views"] == 0
    assert post["authorId"] == seller["id"]

    listed = client.get("/api/v1/posts", params={"q": "laptop"}).json()
    assert any(item["id"] == post["id"] for item in listed["data"])
    assert listed["data"][0]["author"]["fullName"] == "Tài khoản QA"

    detail = client.get(f"/api/v1/posts/{post['slug']}").json()
    assert detail["views"] == 0  # trả số cũ, như bản Node

    mine = client.get("/api/v1/posts/me/all", headers=seller["headers"]).json()
    assert [item["id"] for item in mine] == [post["id"]]

    with SessionLocal() as db:
        assert db.execute(select(Post.views).where(Post.id == post["id"])).scalar_one() == 1

    patched = client.patch(
        f"/api/v1/posts/{post['id']}", headers=seller["headers"], json={"status": "HIDDEN"}
    )
    assert patched.json()["status"] == "HIDDEN"
    assert client.get(f"/api/v1/posts/{post['slug']}").status_code == 404

    assert client.delete(
        f"/api/v1/posts/{post['id']}", headers=seller["headers"]
    ).json() == {"message": "Đã xoá bài viết"}
    assert client.delete(f"/api/v1/posts/{post['id']}", headers=seller["headers"]).status_code == 404


def test_bai_viet_can_quyen_nguoi_ban(make_user, client):
    buyer = make_user()
    response = client.post(
        "/api/v1/posts",
        headers=buyer["headers"],
        json={"title": "Tiêu đề đủ mười ký tự", "content": "x" * 60},
    )
    assert response.status_code == 403


def test_bai_viet_sai_du_lieu(make_user, client):
    seller = make_user(roles=["SELLER"])
    response = client.post(
        "/api/v1/posts",
        headers=seller["headers"],
        json={"title": "ngắn", "content": "quá ngắn"},
    )
    assert response.status_code == 400
    assert {detail["field"] for detail in response.json()["details"]} == {"title", "content"}


def test_tim_shop_va_trang_shop(make_user, client):
    seller = make_user()  # chưa phải SELLER, để become-seller tạo hồ sơ
    shop_name = f"Shop QA {seller['id']}"
    client.post(
        "/api/v1/users/me/become-seller",
        headers=seller["headers"],
        json={"shopName": shop_name},
    )

    found = client.get("/api/v1/shops/search", params={"q": shop_name}).json()
    assert found["meta"]["total"] == 1
    item = found["data"][0]
    assert item["shopName"] == shop_name
    assert item["productsCount"] == 0
    assert item["identityVerified"] is False

    detail = client.get(f"/api/v1/shops/{seller['id']}").json()
    assert detail["shopName"] == shop_name
    assert detail["listings"]["data"] == []
    assert detail["recentReviews"] == []
    assert detail["reputation"]["messageSample"] == 0

    missing = client.get("/api/v1/shops/99999999")
    assert missing.status_code == 404
    assert missing.json() == {"message": "Không tìm thấy gian hàng"}
