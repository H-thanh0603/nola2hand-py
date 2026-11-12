"""Trợ lý tìm đồ — Xử lý ngôn ngữ tự nhiên (NLP) cục bộ."""
import re
import unicodedata

# 1. Từ điển Địa điểm
CITIES = [
    "hà nội", "tp.hcm", "hồ chí minh", "sài gòn", "đà nẵng", "hải phòng",
    "cần thơ", "bình dương", "đồng nai", "khánh hòa", "nha trang", "huế",
    "vũng tàu", "đà lạt", "quảng ninh", "hạ long", "vĩnh phúc", "bắc ninh",
    "hà nam", "quảng nam", "thanh hóa"
]

# 2. Từ điển Tình trạng
CONDITIONS = {
    "like new": "LIKE_NEW", "như mới": "LIKE_NEW", "99%": "LIKE_NEW",
    "mới nguyên": "NEW", "chưa sử dụng": "NEW", "mới": "NEW",
    "còn tốt": "USED_GOOD", "xài được": "USED_GOOD", "cũ": "USED_GOOD",
    "hư": "FOR_PARTS", "hỏng": "FOR_PARTS", "linh kiện": "FOR_PARTS"
}

# 3. Từ dừng (Stop words) - Loại bỏ hoàn toàn khỏi từ khóa
STOP_WORDS = {
    # Đại từ, giới từ
    "tôi", "mình", "bạn", "cần", "muốn", "tìm", "mua", "bán", "cho", "một", 
    "cái", "chiếc", "con", "của", "với", "và", "hoặc", "để", "làm", "giá", 
    "rẻ", "tốt", "có", "không", "ai", "đang", "ở", "tại", "khu", "vực", 
    "thì", "là", "thể", "được", "nào", "gì", "đâu", "như", "thế",
    # Từ lóng / Tiếng Anh giao tiếp
    "budget", "tầm", "khoảng", "chắc", "hơi", "đổ", "lại", "lướt", "web", 
    "chơi", "game", "làm", "việc", "học", "tập", "giá", "tiền", "vnd", "vnđ"
}

def _strip_accents(s: str) -> str:
    """Bỏ dấu tiếng Việt để so sánh dễ hơn."""
    return "".join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')

def local_search(message: str) -> dict:
    text = message.lower().strip()
    filters = {}

    # --- BƯỚC 1: TRÍCH XUẤT GIÁ ---
    # Regex: "15tr", "dưới 5 triệu", "tầm 2 củ đổ lại", "trên 500k"
    price_regex = r"(dưới|tối đa|trên|tối thiểu|tầm|khoảng|giá|budget)\s*(?:là|tầm|khoảng)?\s*(\d+(?:[.,]\d+)?)\s*(triệu|tr|củ|nghìn|ngàn|k|đ|vnd)?"
    price_match = re.search(price_regex, text)
    
    # Hỗ trợ viết tắt: 15tr5 = 15.5 triệu
    short_price_match = re.search(r"(\d+)(tr|triệu)(\d+)", text)
    
    if short_price_match:
        main, unit, sub = short_price_match.groups()
        amount = float(f"{main}.{sub}") * 1_000_000
        # Nếu có "dưới" hoặc "tối đa" ở trước, thì là max price, không thì là khoảng
        prefix_match = re.search(r"(dưới|tối đa|trên|tối thiểu)", text)
        if prefix_match and prefix_match.group(1) in ("dưới", "tối đa"):
            filters["maxPrice"] = int(amount)
        elif prefix_match and prefix_match.group(1) in ("trên", "tối thiểu"):
            filters["minPrice"] = int(amount)
        else:
            filters["minPrice"] = int(amount * 0.8)
            filters["maxPrice"] = int(amount * 1.2)
        text = text.replace(short_price_match.group(0), " ")
        
    elif price_match:
        prefix, amount_str, unit = price_match.groups()
        amount = float(amount_str.replace(",", "."))
        
        # Quy đổi ra VND
        if unit in ("triệu", "tr", "củ"):
            amount *= 1_000_000
        elif unit in ("nghìn", "ngàn", "k"):
            amount *= 1_000
        
        amount = int(amount)
        
        if prefix in ("dưới", "tối đa") or "đổ lại" in text:
            filters["maxPrice"] = amount
        elif prefix in ("trên", "tối thiểu"):
            filters["minPrice"] = amount
        else:
            # "tầm", "khoảng", "giá" -> Cho phép sai số 20%
            filters["minPrice"] = int(amount * 0.8)
            filters["maxPrice"] = int(amount * 1.2)
            
        # Xóa phần giá khỏi câu
        text = text.replace(price_match.group(0), " ")
        # Đôi khi "đổ lại" bị dính vào sau giá
        text = text.replace("đổ lại", " ")

    # --- BƯỚC 2: TRÍCH XUẤT THÀNH PHỐ ---
    for city in CITIES:
        if city in text:
            filters["city"] = city.title()
            text = text.replace(city, " ")
            break

    # --- BƯỚC 3: TRÍCH XUẤT TÌNH TRẠNG ---
    for cond, enum_val in CONDITIONS.items():
        if cond in text:
            filters["condition"] = enum_val
            text = text.replace(cond, " ")
            break

    # --- BƯỚC 4: TẠO TỪ KHÓA (Q) ---
    # Loại bỏ các ký tự đặc biệt và tách từ
    words = re.split(r"\W+", text)
    
    # Lọc bỏ stop words và các từ quá ngắn
    keywords = [w for w in words if w and w not in STOP_WORDS and len(w) > 1]
    
    if keywords:
        filters["q"] = " ".join(keywords).strip()[:150]
    else:
        # Nếu sau khi bỏ stop words mà không còn gì (VD: "tìm cái gì đó"), 
        # trả về rỗng để backend trả về toàn bộ
        pass

    return filters