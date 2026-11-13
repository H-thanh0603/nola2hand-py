"""Custom Vietnamese NLP engine — Phân tích cảm xúc dựa trên ngữ pháp và từ vựng."""
import re
import json
import logging

logger = logging.getLogger(__name__)

# Từ điển cảm xúc (Tích cực / Tiêu cực)
POSITIVE_WORDS = {
    "tốt", "tuyệt", "đẹp", "xịn", "uy tín", "nhanh", "hài lòng", "ok", "ổn", 
    "đúng", "chuẩn", "thích", "rẻ", "mượt", "bền", "nhiệt tình", "dễ thương", 
    "chất lượng", "yêu", "ưng", "5 sao", "đỉnh", "sướng"
}

NEGATIVE_WORDS = {
    "tệ", "dở", "lỗi", "hỏng", "chậm", "lừa đảo", "dởm", "fake", "kém", 
    "thất vọng", "bực", "bẩn", "móp", "méo", "giao sai", "thái độ", "khó chịu",
    "đắt", "chán", "tồi", "vô dụng", "1 sao"
}

# Từ nhấn mạnh (Tăng trọng số)
INTENSIFIERS = {"rất", "cực", "siêu", "vô cùng", "quá", "lắm", "thật sự", "hoàn toàn"}

# Từ phủ định (Đảo ngược cảm xúc)
NEGATIONS = {"không", "chưa", "chả", "chẳng", "chưa hẳn", "không hẳn"}

# Từ nối (Trộn lẫn cảm xúc)
CONJUNCTIONS = {"nhưng", "tuy nhiên", "mặc dù", "dù", "nhưng mà"}

def analyze_text_sentiment(text: str) -> tuple[int, str]:
    """Phân tích text và trả về (score, reason). Score > 0 là tích cực, < 0 là tiêu cực."""
    text = text.lower().strip()
    if not text:
        return 0, "Không có nội dung"

    # Tokenize đơn giản theo khoảng trắng
    words = text.split()
    score = 0
    hits = []
    
    i = 0
    while i < len(words):
        word = words[i]
        
        # Kiểm tra từ ghép (bigram) ví dụ: "lừa đảo", "uy tín"
        bigram = f"{words[i]} {words[i+1]}" if i + 1 < len(words) else ""
        
        target_word = None
        weight = 1
        
        if bigram in POSITIVE_WORDS or bigram in NEGATIVE_WORDS:
            target_word = bigram
            i += 2
        elif word in POSITIVE_WORDS or word in NEGATIVE_WORDS:
            target_word = word
            i += 1
        else:
            i += 1
            continue

        # 1. Kiểm tra từ nhấn mạnh trước đó (VD: "rất tốt")
        if i >= 2 and words[i-2] in INTENSIFIERS:
            weight *= 1.5
        
        # 2. Kiểm tra từ phủ định trước đó (VD: "không tốt")
        is_negated = False
        if i >= 2 and words[i-2] in NEGATIONS:
            is_negated = True
        elif i >= 3 and f"{words[i-3]} {words[i-2]}" in NEGATIONS:
            is_negated = True

        # Xác định điểm cơ bản
        base_score = 1 if target_word in POSITIVE_WORDS else -1
        if is_negated:
            base_score *= -1
            hits.append(f"phủ định '{target_word}'")
        elif base_score > 0:
            hits.append(f"khen '{target_word}'")
        else:
            hits.append(f"chê '{target_word}'")

        score += base_score * weight

    # 3. Xử lý từ nối (VD: "tốt nhưng đắt" -> triệt tiêu lẫn nhau)
    if any(conj in text for conj in CONJUNCTIONS):
        # Nếu có cả khen và chê, điểm tự động bị kéo về 0 (Neutral)
        if score > 0 and any(w in text for w in NEGATIVE_WORDS):
            score = 0
            hits.append("trộn lẫn khen/chê")
        elif score < 0 and any(w in text for w in POSITIVE_WORDS):
            score = 0
            hits.append("trộn lẫn chê/khen")

    reason = ", ".join(hits[:3]) if hits else "Không có từ khóa"
    return score, reason

def local_sentiment(comment: str | None, rating: int) -> dict:
    """Phân tích kết hợp giữa Rating (Sao) và Văn bản."""
    text_score, reason = analyze_text_sentiment(comment or "")
    
    # Rating 1-5 đóng vai trò 60% quyết định, văn bản 40%
    rating_score = 0
    if rating >= 4: rating_score = 2
    elif rating <= 2: rating_score = -2

    # Tính điểm tổng hợp
    final_score = (rating_score * 1.5) + text_score

    # Phân loại
    if final_score >= 1.5:
        sentiment = "POSITIVE"
    elif final_score <= -1.5:
        sentiment = "NEGATIVE"
    else:
        sentiment = "NEUTRAL"

    return {
        "sentiment": sentiment, 
        "sentimentSource": "LOCAL",
        "reason": reason,
        "score": round(final_score, 1)
    }

def analyze_sentiment(comment: str | None, rating: int) -> dict:
    """Hàm chính được gọi khi tạo Review."""
    return local_sentiment(comment, rating)

def json_answer(instructions: str, payload: dict) -> dict | None:
    """Fallback cho Assistant (không dùng AI bên ngoài)."""
    return None