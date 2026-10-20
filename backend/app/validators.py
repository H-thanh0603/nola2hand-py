"""Kiểm tra dữ liệu vào — giữ nguyên regex và thông báo của src/validators.js."""
import re
from urllib.parse import urlparse

# Regex email lấy đúng theo zod v3 (src/validators.js dùng z.string().email()).
EMAIL_RE = re.compile(r"^(?!\.)(?!.*\.\.)([A-Za-z0-9_'+\-.]*)[A-Za-z0-9_+-]@([A-Za-z0-9][A-Za-z0-9\-]*\.)+[A-Za-z]{2,}$")
PHONE_VN_RE = re.compile(r"^(\+84|0)(3|5|7|8|9)\d{8}$")
PASSWORD_RE = re.compile(r"^(?=.*[A-Za-z])(?=.*\d).+$", re.DOTALL)


def clean_email(value: str) -> str:
    value = value.strip().lower()
    if not EMAIL_RE.match(value):
        raise ValueError("Email không hợp lệ")
    return value


def phone_vn(value: str) -> str:
    value = value.strip()
    if not PHONE_VN_RE.match(value):
        raise ValueError("SĐT Việt Nam chưa đúng (VD: 0987654321)")
    return value


def password(value: str, min_length: int, what: str = "Mật khẩu") -> str:
    if len(value) < min_length:
        raise ValueError(f"{what} tối thiểu {min_length} ký tự")
    if len(value) > 72:
        raise ValueError(f"{what} tối đa 72 ký tự")
    if not PASSWORD_RE.match(value):
        raise ValueError(f"{what} cần có cả chữ và số")
    return value


def http_url(value: str, what: str = "URL") -> str:
    """z.string().url() + chỉ nhận http(s) — hai thông báo lỗi khác nhau như bản Node."""
    value = value.strip()
    parsed = urlparse(value)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"{what} chưa đúng")
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Chỉ nhận URL HTTP/HTTPS")
    return value
