"""Phân trang — so với hành vi của parseInt trong JavaScript."""
import pytest

from app.pagination import js_parse_int, paged_result, paginate


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("5", 5),
        ("5.9", 5),  # parseInt cắt ở dấu chấm
        ("  7abc", 7),
        ("-3", -3),
        ("abc", None),
        ("", None),
        (None, None),
        (0, 0),
    ],
)
def test_js_parse_int(raw, expected):
    assert js_parse_int(raw) == expected


def test_mac_dinh_khi_thieu_hoac_sai():
    assert paginate({}) == {"page": 1, "limit": 20, "skip": 0}
    assert paginate({"page": "abc", "limit": "-1"}) == {"page": 1, "limit": 1, "skip": 0}


def test_gioi_han_limit_100_va_page_toi_thieu_1():
    assert paginate({"page": "0", "limit": "500"})["limit"] == 100
    assert paginate({"page": "-9"})["page"] == 1


def test_skip_tinh_tu_page_va_limit():
    assert paginate({"page": "3", "limit": "15"})["skip"] == 30


def test_meta_lam_tron_tong_so_trang():
    assert paged_result([], 0, 1, 20)["meta"]["totalPages"] == 0
    assert paged_result([], 21, 1, 20)["meta"]["totalPages"] == 2
