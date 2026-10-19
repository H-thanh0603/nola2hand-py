"""Phân trang — giống hệt src/utils.js (page >= 1, limit 1..100, mặc định 20)."""
import re


def js_parse_int(raw) -> int | None:
    """Mô phỏng parseInt của JavaScript: lấy phần số ở đầu chuỗi, '5.9' → 5, 'abc' → None."""
    if raw is None:
        return None
    if isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        return int(raw)
    match = re.match(r"\s*([+-]?\d+)", str(raw))
    return int(match.group(1)) if match else None


def paginate(query: dict, default_page: int = 1, default_limit: int = 20) -> dict:
    # JS: parseInt(x, 10) || mặc định — số 0 và NaN đều rơi về mặc định.
    page = js_parse_int(query.get("page")) or default_page
    limit = js_parse_int(query.get("limit")) or default_limit
    page = max(1, page)
    limit = min(100, max(1, limit))
    return {"page": page, "limit": limit, "skip": (page - 1) * limit}


def paged_result(data: list, total: int, page: int, limit: int) -> dict:
    total_pages = -(-total // limit)  # làm tròn lên, khớp Math.ceil
    return {"data": data, "meta": {"page": page, "limit": limit, "total": total, "totalPages": total_pages}}
