"""Test tích hợp users.js: hồ sơ, địa chỉ, lên người bán, trang cá nhân."""

ADDRESS = {
    "label": "Nhà",
    "receiver": "Tài khoản QA",
    "phone": "0987654321",
    "street": "12 Nguyễn Huệ",
    "city": "TP.HCM",
}


def test_ho_so_day_du(make_user, client):
    user = make_user()
    response = client.get("/api/v1/users/me/profile", headers=user["headers"])
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == user["email"]
    assert body["roles"] == ["BUYER"]
    assert body["sellerProfile"] is None
    assert body["addresses"] == []
    assert "passwordHash" not in body


def test_cap_nhat_ho_so(make_user, client):
    user = make_user()
    response = client.patch(
        "/api/v1/users/me",
        headers=user["headers"],
        json={"fullName": "Tên Mới", "bio": "  Thích đồ cũ  ", "avatarUrl": "", "gender": "Nam"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["fullName"] == "Tên Mới"
    assert body["bio"] == "Thích đồ cũ"
    assert body["avatarUrl"] == ""
    assert body["gender"] == "Nam"
    assert "passwordHash" not in body


def test_cap_nhat_sai_du_lieu(make_user, client):
    user = make_user()
    response = client.patch(
        "/api/v1/users/me", headers=user["headers"], json={"phone": "123", "avatarUrl": "khong-phai-url"}
    )
    assert response.status_code == 400
    fields = {detail["field"] for detail in response.json()["details"]}
    assert fields == {"phone", "avatarUrl"}


def test_len_nguoi_ban_tao_ho_so_va_dia_chi(make_user, client):
    user = make_user()
    response = client.post(
        "/api/v1/users/me/become-seller",
        headers=user["headers"],
        json={"shopName": "Shop QA", "phone": "0912345678", "city": "Hà Nội", "street": "1 Tràng Tiền"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["message"] == "Mở kênh người bán thành công"
    assert body["profile"]["shopName"] == "Shop QA"
    assert body["profile"]["rating"] == 0

    profile = client.get("/api/v1/users/me/profile", headers=user["headers"]).json()
    assert profile["roles"] == ["BUYER", "SELLER"]
    assert profile["phone"] == "0912345678"
    assert len(profile["addresses"]) == 1
    assert profile["addresses"][0]["label"] == "Lấy hàng"
    assert profile["addresses"][0]["isDefault"] is True

    again = client.post(
        "/api/v1/users/me/become-seller", headers=user["headers"], json={"shopName": "Shop 2"}
    )
    assert again.status_code == 400
    assert again.json() == {"message": "Bạn đã là người bán"}


def test_so_dia_chi(make_user, client):
    user = make_user()
    headers = user["headers"]

    first = client.post("/api/v1/users/me/addresses", headers=headers, json={**ADDRESS, "isDefault": True})
    assert first.status_code == 201
    assert first.json()["isDefault"] is True

    second = client.post(
        "/api/v1/users/me/addresses", headers=headers, json={**ADDRESS, "label": "Cơ quan"}
    )
    assert second.status_code == 201
    assert second.json()["isDefault"] is False

    listed = client.get("/api/v1/users/me/addresses", headers=headers).json()
    assert [a["label"] for a in listed] == ["Nhà", "Cơ quan"]  # mặc định lên trước

    deleted = client.delete(f"/api/v1/users/me/addresses/{second.json()['id']}", headers=headers)
    assert deleted.json() == {"message": "Đã xoá địa chỉ"}

    missing = client.delete(f"/api/v1/users/me/addresses/{second.json()['id']}", headers=headers)
    assert missing.status_code == 404
    assert missing.json() == {"message": "Không tìm thấy địa chỉ"}


def test_khong_xoa_duoc_dia_chi_cua_nguoi_khac(make_user, client):
    owner = make_user()
    other = make_user()
    address = client.post("/api/v1/users/me/addresses", headers=owner["headers"], json=ADDRESS).json()

    response = client.delete(f"/api/v1/users/me/addresses/{address['id']}", headers=other["headers"])
    assert response.status_code == 404


def test_trang_ca_nhan_cong_khai(make_user, client):
    user = make_user()
    response = client.get(f"/api/v1/users/{user['id']}")
    assert response.status_code == 200
    body = response.json()
    assert body["user"]["id"] == user["id"]
    assert body["user"]["_count"] == {"listings": 0}
    assert body["data"] == []
    assert body["meta"] == {"page": 1, "limit": 5, "total": 0, "totalPages": 0}


def test_trang_ca_nhan_khong_ton_tai(client):
    response = client.get("/api/v1/users/99999999")
    assert response.status_code == 404
    assert response.json() == {"message": "Không tìm thấy người dùng"}
