import re
import unicodedata

CITIES = [
    "hà nội", "tp.hcm", "hồ chí minh", "sài gòn", "đà nẵng", "hải phòng",
    "cần thơ", "bình dương", "đồng nai", "khánh hòa", "nha trang", "huế",
    "vũng tàu", "đà lạt", "quảng ninh", "hạ long"
]

CONDITIONS = {
    "like new": "LIKE_NEW", "như mới": "LIKE_NEW", "99%": "LIKE_NEW",
    "mới nguyên": "NEW", "chưa sử dụng": "NEW", "mới": "NEW",
    "còn tốt": "USED_GOOD", "xài được": "USED_GOOD", "cũ": "USED_GOOD",
}

STOP_WORDS = {
    "tôi", "mình", "cần", "muốn", "tìm", "mua", "bán", "cho", "một", 
    "cái", "chiếc", "con", "của", "với", "và", "hoặc", "để", "làm", "giá", 
    "rẻ", "tốt", "có", "không", "ai", "đang", "ở", "tại", "khu", "vực", 
    "thì", "là", "thể", "được", "nào", "gì", "đâu", "như", "thế", "dưới", "trên"
}

def local_search(message: str) -> dict:
    text = message.lower().strip()
    filters = {}

    # 1. Trích xuất Giá (Xử lý cả "100000" và "100k", "1 triệu")
    # Pattern này tìm số, theo sau là đơn vị (nếu có)
    price_match = re.search(r"(dưới|tối đa|trên|tối thiểu|tầm|khoảng)\s*(\d+(?:[.,]\d+)?)\s*(triệu|tr|củ|nghìn|ngàn|k|đ|vnd)?", text)
    
    if price_match:
        prefix, amount_str, unit = price_match.groups()
        amount = float(amount_str.replace(",", "."))
        
        # Nếu không có đơn vị, và số > 1000, coi như là VND
        if not unit and amount >= 1000:
            amount = amount
        elif unit in ("triệu", "tr", "củ"):
            amount *= 1_000_000
        elif unit in ("nghìn", "ngàn", "k"):
            amount *= 1_000
        
        amount = int(amount)
        
        if prefix in ("dưới", "tối đa"):
            filters["maxPrice"] = amount
        elif prefix in ("trên", "tối thiểu"):
            filters["minPrice"] = amount
        else:
            filters["minPrice"] = int(amount * 0.8)
            filters["maxPrice"] = int(amount * 1.2)
            
        # Xóa cụm giá khỏi chuỗi
        text = text.replace(price_match.group(0), " ")
        # Xóa luôn chữ "giá" nếu nó đứng một mình
        text = text.replace("giá", " ")

    # 2. Trích xuất Thành phố
    for city in CITIES:
        if city in text:
            filters["city"] = city.title()
            text = text.replace(city, " ")
            break

    # 3. Tạo từ khóa
    words = re.split(r"\W+", text)
    keywords = [w for w in words if w and w not in STOP_WORDS and len(w) > 1]
    
    if keywords:
        filters["q"] = " ".join(keywords).strip()

    return filters