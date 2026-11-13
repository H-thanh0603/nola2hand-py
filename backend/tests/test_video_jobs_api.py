"""API video-jobs: ép 10 giây, tối đa 3 ảnh, sidecar tắt thì báo rõ."""
import base64

from app.config import settings

PNG = base64.b64encode(
    bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
        "0000000a49444154789c6300010000050001"
        "0d0a2db40000000049454e44ae426082"
    )
).decode()

def _img() -> dict:
    return {"mimeType": "image/png", "base64": PNG}

def test_prompt_rong_tra_400(client, make_user):
    seller = make_user(roles=["SELLER"], verified=True)
    r = client.post(
        "/api/v1/video-jobs", headers=seller["headers"], json={"prompt": "   ", "images": [_img()]}
    )
    assert r.status_code == 400

def test_qua_3_anh_tra_400(client, make_user):
    seller = make_user(roles=["SELLER"], verified=True)
    r = client.post(
        "/api/v1/video-jobs", headers=seller["headers"], json={"prompt": "tai nghe", "images": [_img()] * 4}
    )
    assert r.status_code == 400
    assert "3" in r.json()["message"]

def test_khong_co_anh_tra_400(client, make_user):
    seller = make_user(roles=["SELLER"], verified=True)
    r = client.post("/api/v1/video-jobs", headers=seller["headers"], json={"prompt": "tai nghe", "images": []})
    assert r.status_code == 400

def test_preview_prompt_ep_10_giay(client, make_user):
    seller = make_user(roles=["SELLER"], verified=True)
    r = client.post(
        "/api/v1/video-jobs/preview-prompt",
        headers=seller["headers"],
        json={"prompt": "quay video 30 giây cho tai nghe"},
    )
    assert r.status_code == 200
    body = r.json()
    assert "30 giây" not in body["finalPrompt"]
    assert body["finalPrompt"].count("10 giây") == 2
    assert body["notice"] == "Chỉ tạo được video 10 giây. Tối đa 3 ảnh."

def test_sidecar_tat_thi_tra_503(client, make_user, monkeypatch):
    monkeypatch.setattr(settings, "video_agent_enabled", False)
    seller = make_user(roles=["SELLER"], verified=True)
    r = client.post(
        "/api/v1/video-jobs", headers=seller["headers"], json={"prompt": "tai nghe", "images": [_img()]}
    )
    assert r.status_code == 503

def test_buyer_khong_tao_duoc_video(client, make_user):
    buyer = make_user()
    r = client.post(
        "/api/v1/video-jobs", headers=buyer["headers"], json={"prompt": "tai nghe", "images": [_img()]}
    )
    assert r.status_code == 403
