"""Băm mật khẩu và JWT — kiểm tra tính tương thích với bản Node."""
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.config import settings
from app.security import (
    TokenError,
    _expiry_seconds,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

# Hash do bcryptjs (bản Node) sinh ra: node -e "require('bcryptjs').hashSync('123456',10)"
BCRYPTJS_HASH = "$2a$10$Bei25IxW.Dv32ZxwquC/b.IhdZqIn2/QzNOoIQIlqPePSC1eosRL2"


def test_doc_duoc_hash_sinh_tu_bcryptjs():
    assert verify_password("123456", BCRYPTJS_HASH) is True
    assert verify_password("123457", BCRYPTJS_HASH) is False


def test_hash_moi_dung_dinh_dang_bcryptjs():
    hashed = hash_password("matkhau-that")
    assert hashed.startswith("$2a$10$")
    assert verify_password("matkhau-that", hashed) is True
    assert verify_password("sai", hashed) is False


def test_mat_khau_qua_72_byte_bi_cat_nhu_bcryptjs():
    long_password = "a" * 100
    assert verify_password(long_password, hash_password(long_password)) is True
    # bcryptjs cắt ở 72 byte nên 72 ký tự đầu quyết định kết quả
    assert verify_password("a" * 72 + "KHÁC", hash_password(long_password)) is True


def test_hash_rong_khong_lam_no():
    assert verify_password("abc", "") is False
    assert verify_password("abc", "khong-phai-hash") is False


def test_token_di_ve_dung_du_lieu():
    token = create_access_token(42, 3)
    payload = decode_access_token(token)
    assert payload["sub"] == "42"
    assert payload["purpose"] == "access"
    assert payload["sessionVersion"] == 3


def test_token_het_han_bi_tu_choi():
    expired = jwt.encode(
        {"sub": "1", "purpose": "access", "exp": int((datetime.now(timezone.utc) - timedelta(seconds=5)).timestamp())},
        settings.jwt_secret,
        algorithm="HS256",
    )
    with pytest.raises(TokenError):
        decode_access_token(expired)


def test_token_sai_khoa_bi_tu_choi():
    other = jwt.encode({"sub": "1", "purpose": "access"}, "khoa-khac", algorithm="HS256")
    with pytest.raises(TokenError):
        decode_access_token(other)


def test_token_sai_muc_dich_bao_dung_loai_loi():
    refresh = jwt.encode({"sub": "1", "purpose": "refresh"}, settings.jwt_secret, algorithm="HS256")
    with pytest.raises(TokenError) as exc:
        decode_access_token(refresh)
    assert exc.value.args[0] == "wrong_purpose"


@pytest.mark.parametrize(
    ("value", "seconds"),
    [("7d", 604800), ("12h", 43200), ("30m", 1800), ("45s", 45), ("3600", 3600)],
)
def test_doc_thoi_han_token(value, seconds):
    assert _expiry_seconds(value) == seconds


def test_thoi_han_token_sai_thi_bao_loi():
    with pytest.raises(ValueError):
        _expiry_seconds("7 ngày")
