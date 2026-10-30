"""Prompt cho video quảng bá: luôn 10 giây, bỏ mọi mốc thời gian người dùng nhập.

Quy tắc sản phẩm (không thương lượng): video chỉ dài 10 giây, tối đa 3 ảnh.
Người dùng gõ "30 giây" hay "1 phút" đều bị lược bỏ — không có đường nào để xin video dài hơn.
"""

import re

MAX_IMAGES = 3
PROMPT_NOTICE = "Chỉ tạo được video 10 giây. Tối đa 3 ảnh."
HEADER = "Tạo video 10 giây · tỷ lệ 9:16 dọc"
FOOTER = "Độ dài đúng 10 giây."

# "30 giây", "15s", "20 sec", "1 phút", "1p". Không nhận "m" để tránh ăn nhầm "cao 5m".
# Số + đơn vị thời gian có chữ. KHÔNG có nhánh "s"/"p" trần ở đây — "5s" trong "iPhone 5s"
# và "1080p" là tên sản phẩm/thông số, không phải mốc thời gian.
_DURATION = re.compile(
    r"\b\d+(?:[.,]\d+)?\s*(?:giây|giay|seconds?|secs?|phút|phut|minutes?|mins?|tiếng|tieng|giờ|gio|hours?|hrs?)\b",
    re.IGNORECASE,
)
# "15s", "30 s" chỉ khi đứng riêng: không dính chữ số khác phía trước (1080p, 720p) và
# không phải tên máy ("iPhone 5s", "Galaxy 6s", "Note 5s").
_SHORT = re.compile(r"(?<![\w.])\d{1,2}\s*[sp]\b(?![\w.])", re.IGNORECASE)
_PHONE = re.compile(r"\b(?:iphone|galaxy|note|pixel|redmi|oppo|vivo|xiaomi|realme)\s+\d+\s*[sp]\b", re.IGNORECASE)
# Số đếm bằng chữ: "một phút", "ba mươi giây", "mười lăm giây", "hai tiếng".
_WORD_NUM = (
    r"(?:một|hai|ba|bốn|năm|sáu|bảy|tám|chín|mười|lăm|mươi|mốt|tư|rưỡi"
    r"|one|two|three|four|five|six|seven|eight|nine|ten|fifteen|twenty|thirty)"
)
_DURATION_WORDS = re.compile(
    rf"\b(?:{_WORD_NUM}\s*){{1,3}}(?:giây|giay|phút|phut|tiếng|tieng|giờ|gio|seconds?|minutes?|hours?)\b",
    re.IGNORECASE,
)
# "nửa phút", "nửa giờ" — không có số nhưng vẫn là mốc thời gian.
_HALF = re.compile(r"\b(?:nửa|nua|rưỡi|ruoi)\s*(?:phút|phut|giây|giay|giờ|gio|tiếng|tieng)\b", re.IGNORECASE)
# "video30s" dính liền chữ và số (không có \b ở giữa).
_GLUED = re.compile(r"(?<=[a-zà-ỹ])\d+\s*[sp]\b", re.IGNORECASE)
# Dấu câu rác còn lại sau khi bỏ mốc thời gian: ngoặc rỗng, dấu lặp "!!!", " ,"…
_JUNK = re.compile(r"\(\s*\)|\[\s*\]|([!?.,;:])\1+")

CONDITION_NAMES = {
    "NEW": "mới nguyên hộp",
    "LIKE_NEW": "gần như mới",
    "USED_GOOD": "đã dùng, còn tốt",
    "USED_FAIR": "đã dùng, có dấu sử dụng",
    "FOR_PARTS": "bán linh kiện",
}

STYLE = (
    "quay bằng điện thoại kiểu người thật review, ánh sáng thật, người Việt bình thường, "
    "bàn tay tự nhiên đủ năm ngón"
)
BEATS = (
    "Ba nhịp dựng: mở bằng cận cảnh chi tiết sản phẩm, giữa là thao tác sử dụng thật, "
    "chốt bằng toàn cảnh sản phẩm trên tay người bán."
)
AVOID = "Không chữ chạy, không logo, không phụ đề."

# Dưới ngưỡng này coi là prompt sơ sài → ghép thêm bối cảnh cho Muse đủ chất liệu.
MIN_WORDS = 25


def strip_durations(text: str) -> str:
    """Xoá mọi mốc thời gian trong câu, dọn khoảng trắng và dấu câu thừa."""
    if not text:
        return ""
    out = _HALF.sub(" ", text)
    out = _DURATION_WORDS.sub(" ", out)
    out = _GLUED.sub(" ", out)
    # Giữ nguyên tên máy ("iPhone 5s") rồi mới xoá "15s" đứng riêng.
    protected: list[str] = []

    def _keep(match: re.Match) -> str:
        protected.append(match.group(0))
        return f"\x00{len(protected) - 1}\x00"

    out = _PHONE.sub(_keep, out)
    out = _SHORT.sub(" ", out)
    out = _DURATION.sub(" ", out)
    for index, original in enumerate(protected):
        out = out.replace(f"\x00{index}\x00", original)
    out = re.sub(r"\s+", " ", out)
    out = re.sub(r"\s+([,.;:!?])", r"\1", out)
    # Chỉ chuẩn hoá , ; — giữ nguyên dấu ":" để không phá tỷ lệ "9:16".
    out = re.sub(r"([,;])\s*", r"\1 ", out)
    out = _JUNK.sub(" ", out)
    out = re.sub(r"\s{2,}", " ", out).strip()
    return out.strip(" ,;:-")


def _price_text(price) -> str:
    try:
        return f"giá {int(price):,} đồng".replace(",", ".")
    except (TypeError, ValueError):
        return ""


def improve(text: str, listing: dict | None = None) -> str:
    """Ghép thêm bối cảnh khi prompt quá ngắn. Prompt đã đủ dài thì giữ nguyên."""
    body = (text or "").strip()
    if len(body.split()) >= MIN_WORDS:
        return body

    parts: list[str] = []
    if body:
        parts.append(body if body.endswith((".", "!", "?")) else body + ".")

    if listing:
        title = (listing.get("title") or "").strip()
        if title:
            parts.append(f"Cận cảnh {title} đặt trên bàn gỗ sáng đèn.")
        meta = [
            (listing.get("categoryName") or "").strip(),
            CONDITION_NAMES.get(listing.get("condition") or "", ""),
            _price_text(listing.get("price")),
        ]
        meta = [item for item in meta if item]
        if meta:
            parts.append("Thông tin sản phẩm: " + ", ".join(meta) + ".")

    parts.append(STYLE[0].upper() + STYLE[1:] + ".")
    parts.append(BEATS)
    parts.append(AVOID)
    return " ".join(parts)


def finalize(prompt: str, listing: dict | None = None) -> str:
    """Prompt cuối cùng gửi Muse: bỏ mốc thời gian, cải thiện, ép đúng 10 giây."""
    body = strip_durations(prompt)
    if not body and not listing:
        raise ValueError("Prompt không được để trống")
    return f"{HEADER}\n{improve(body, listing).strip()}\n{FOOTER}"
