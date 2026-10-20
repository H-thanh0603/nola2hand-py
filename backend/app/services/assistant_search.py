"""Bộ lọc từ câu nói tự nhiên — port src/services/assistant-search.js."""
import math
import re

BUDGET_RE = re.compile(
    r"(?:dưới|tối đa|không quá)\s*(\d+(?:[.,]\d+)?)\s*(triệu|tr|nghìn|ngàn|k|đ|vnd)?", re.IGNORECASE
)
LOCATION_RE = re.compile(r"\s+(?:tại|ở)\s+(.+)\Z", re.IGNORECASE)
PREFIX_RE = re.compile(r"^(?:tôi cần|tìm|mua|cho tôi)\s+", re.IGNORECASE)


def local_search(message: str) -> dict:
    text = message.strip()
    budget = BUDGET_RE.search(text)
    location = LOCATION_RE.search(text)

    q = text
    if location is not None:
        q = q.replace(location.group(0), "", 1)
    if budget is not None:
        q = q.replace(budget.group(0), "", 1)
    q = PREFIX_RE.sub("", q.strip())

    filters: dict = {"q": q[:150]}
    if budget is not None:
        unit = (budget.group(2) or "").lower()
        multiplier = 1_000_000 if unit in ("triệu", "tr") else 1000 if unit in ("nghìn", "ngàn", "k") else 1
        price = float(budget.group(1).replace(",", ".")) * multiplier
        if math.isfinite(price) and price <= 2_000_000_000:
            filters["maxPrice"] = math.floor(price)
    if location is not None:
        filters["city"] = location.group(1).strip()[:100]
    return filters
