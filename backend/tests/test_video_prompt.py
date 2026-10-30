"""Prompt video: luôn 10 giây, bỏ mốc thời gian người dùng nhập, tối đa 3 ảnh."""
import pytest

from app.services.video_prompt import (
    MAX_IMAGES,
    PROMPT_NOTICE,
    finalize,
    improve,
    strip_durations,
)

@pytest.mark.parametrize("raw", [
    "Quay video 30 giây giới thiệu tai nghe",
    "Làm clip 15s cho áo khoác",
    "video 20 giây, đẹp",
    "quay 1 phút cũng được",
    "Video 10s nhé",
])
def test_bo_moi_moc_thoi_gian(raw):
    out = strip_durations(raw)
    assert "30" not in out and "15" not in out and "20" not in out
    assert "giây" not in out.lower() and "phút" not in out.lower()

def test_giu_nguyen_noi_dung_khi_khong_co_moc_thoi_gian():
    assert strip_durations("Tai nghe Sony màu đen, còn bảo hành") == "Tai nghe Sony màu đen, còn bảo hành"

def test_finalize_luon_ep_10_giay():
    out = finalize("Quay video 30 giây giới thiệu tai nghe")
    assert out.count("10 giây") == 2          # dòng đầu + câu cuối
    assert "30 giây" not in out
    assert out.startswith("Tạo video 10 giây")
    assert out.rstrip().endswith("Độ dài đúng 10 giây.")

def test_finalize_prompt_rong_bi_tu_choi():
    with pytest.raises(ValueError):
        finalize("   ")

def test_improve_them_boi_canh_tu_tin_dang():
    listing = {"title": "Tai nghe Sony WH-1000XM4", "condition": "USED_GOOD", "price": 2500000, "categoryName": "Điện tử"}
    out = improve("", listing)
    assert "Tai nghe Sony WH-1000XM4" in out
    assert "Điện tử" in out
    assert len(out.split()) >= 25

def test_improve_khong_doi_prompt_da_du_dai():
    long_prompt = " ".join(["cận cảnh tai nghe trên bàn gỗ"] * 12)
    assert improve(long_prompt) == long_prompt

def test_max_images_la_3():
    assert MAX_IMAGES == 3
    assert PROMPT_NOTICE == "Chỉ tạo được video 10 giây. Tối đa 3 ảnh."
