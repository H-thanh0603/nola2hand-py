"""Job video không được treo vĩnh viễn khi sidecar chết, và prompt phải sạch mọi mốc thời gian."""
import pytest

from app.services.video_prompt import finalize, strip_durations

# ---------- Critical: mốc thời gian dạng chữ ----------

@pytest.mark.parametrize(
    "raw",
    [
        "quay video một phút cho tai nghe",
        "làm clip ba mươi giây giới thiệu áo",
        "video mười lăm giây nhé",
        "quay 1 tiếng cũng được",
        "video nửa giờ",
        "quay 30 phút rưỡi",
        "quay video30s cho đẹp",
        "quay hai phút",
    ],
)
def test_bo_moc_thoi_gian_dang_chu(raw):
    out = strip_durations(raw).lower()
    for token in ("giây", "phút", "tiếng", "giờ", "phút", "30s"):
        assert token not in out, f"còn {token!r} trong {out!r}"

@pytest.mark.parametrize(
    "raw",
    [
        "quay iPhone 5s cho khách",
        "quay video 1080p cho đẹp",
        "quay 720p 60fps",
        "tai nghe cao 5m",
        "mua 2 cái",
    ],
)
def test_khong_an_nham_thong_so_san_pham(raw):
    """'iPhone 5s', '1080p', 'cao 5m' là tên sản phẩm/thông số, không phải mốc thời gian."""
    assert strip_durations(raw) == raw

def test_giu_ty_le_khung_hinh():
    out = strip_durations("quay video 30 giây 9:16")
    assert "9:16" in out
    assert "30" not in out

def test_finalize_ep_10_giay_ke_ca_khi_prompt_dai_co_moc_chu():
    prompt = " ".join(["cận cảnh tai nghe trên bàn gỗ"] * 8) + " quay video một phút cho khách"
    out = finalize(prompt)
    assert "một phút" not in out
    assert out.count("10 giây") == 2
