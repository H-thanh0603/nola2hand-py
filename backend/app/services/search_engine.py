"""Công cụ tìm kiếm thông minh (Fuzzy Search & Ranking)."""
import re
import unicodedata
from difflib import SequenceMatcher

# 1. Từ điển đồng nghĩa (Semantic mapping)
SYNONYMS = {
    "laptop": ["laptop", "may tinh xach tay", "may tinh", "macbook", "notebook", "thinkpad", "dell", "hp", "asus"],
    "điện thoại": ["dien thoai", "dtdd", "phone", "iphone", "samsung", "xiaomi", "oppo", "vivo"],
    "tai nghe": ["tai nghe", "headphone", "airpods", "earphone", "tai phone"],
    "bàn phím": ["ban phim", "keyboard", "phím cơ", "phim co", "keycap"],
    "tủ lạnh": ["tu lanh", "fridge", "tủ mát"],
    "máy ảnh": ["may anh", "camera", "dslr", "mirrorless", "lens", "ống kính"],
}

# 2. Từ điển Phân loại (Nếu title có từ này, nó thuộc category này)
CATEGORY_MAP = {
    "laptop": ["macbook", "thinkpad", "dell", "hp", "asus", "acer", "lenovo", "laptop", "notebook", "surface"],
    "điện thoại": ["iphone", "samsung", "xiaomi", "oppo", "vivo", "realme", "nokia", "điện thoại"],
    "bàn phím": ["bàn phím", "keyboard", "keycap", "phím cơ", "aula", "akko", "logitech"],
    "tai nghe": ["tai nghe", "airpods", "sony", "bose", "sennheiser", "headphone"],
    "máy ảnh": ["máy ảnh", "camera", "canon", "nikon", "sony", "fujifilm"],
}

def remove_accents(text: str) -> str:
    text = unicodedata.normalize('NFD', text)
    text = "".join(c for c in text if unicodedata.category(c) != 'Mn')
    return text.replace("đ", "d").replace("Đ", "D").lower()

def tokenize(text: str) -> list[str]:
    if not text: return []
    text = remove_accents(text)
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    words = text.split()
    stop_words = {"toi", "minh", "can", "tim", "mua", "ban", "mot", "cai", "chiec", "con", "cua", "voi", "va", "hoac", "de", "lam", "gia", "re", "tot", "co", "khong", "ai", "dang", "o", "tai"}
    return [w for w in words if w not in stop_words and len(w) > 1]

def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()

def smart_match(query: str, title: str, description: str) -> float:
    if not query: return 50.0

    clean_q = remove_accents(query.lower()).strip()
    clean_title = remove_accents(title.lower()).strip()
    clean_desc = remove_accents((description or "").lower()).strip()
    all_text = clean_title + " " + clean_desc

    # 1. Kiểm tra xem query có phải là CATEGORY không (VD: "máy tính" -> laptop)
    # Nếu user search "máy tính", ta map nó thành "laptop" và tìm các brand trong CATEGORY_MAP
    for cat_key, cat_brands in CATEGORY_MAP.items():
        if cat_key in clean_q:
            # Nếu title chứa bất kỳ brand nào của category này -> Trả về điểm cao
            for brand in cat_brands:
                if brand in all_text:
                    return 90.0

    # 2. Đồng nghĩa (VD: search "laptop", title ghi "macbook")
    q_words = tokenize(query)
    for qw in q_words:
        if qw in SYNONYMS:
            for syn in SYNONYMS[qw]:
                if syn in all_text:
                    return 85.0

    # 3. Exact Phrase Match
    if clean_q in clean_title:
        return 100.0
    if clean_q in clean_desc:
        return 80.0

    # 4. Token-based Match
    title_words = tokenize(title)
    desc_words = tokenize(description)

    if not q_words: return 50.0

    score = 0
    max_score = len(q_words) * 100

    for qw in q_words:
        word_score = 0
        # Tìm trong Title
        for tw in title_words:
            if qw == tw:
                word_score = max(word_score, 100)
            elif qw in tw and len(qw) >= 3:
                word_score = max(word_score, 80)
            else:
                sim = similarity(qw, tw)
                if sim > 0.85:
                    word_score = max(word_score, 90)
        # Tìm trong Desc (điểm thấp hơn)
        if word_score < 50:
            for dw in desc_words:
                if qw == dw or (qw in dw and len(qw) >= 3):
                    word_score = max(word_score, 40)
                    break

        score += word_score

    return (score / max_score) * 100