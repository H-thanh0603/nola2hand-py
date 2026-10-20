"""Helper dùng chung — port dần từ src/utils.js khi tới route cần."""
import math
import random
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from .errors import ApiError
from .models import Category, FeeConfig, Notification, OrderTimeline, Wallet, WalletTransaction
from .types import as_json_datetime


def now() -> datetime:
    """UTC dạng naive, khớp kiểu timestamp của Prisma.

    Lưu ý: cột `updatedAt` của Prisma là @updatedAt — không có default trong DB,
    nên mọi insert/update đều phải tự đặt giá trị này (kể cả updateMany).
    """
    return as_json_datetime(datetime.now(timezone.utc).replace(tzinfo=None))


def parse_js_date(value: str) -> datetime:
    """new Date(value) cho chuỗi ISO; chuỗi không có múi giờ hiểu là UTC.

    Frontend luôn gửi `toISOString()` nên nhánh không múi giờ chỉ là lưới an toàn.
    """
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ApiError(400, "Ngày giờ không hợp lệ") from exc
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return as_json_datetime(parsed)


def vnd(amount: int) -> str:
    """10.000 — giống Number.toLocaleString('vi-VN') trong thông báo."""
    return f"{amount:,}".replace(",", ".")


def js_round(value: float) -> int:
    """Math.round của JS: .5 làm tròn lên (Python round() làm tròn chẵn)."""
    return math.floor(value + 0.5)


def notify(
    db: Session,
    user_id: int,
    type_: str,
    title: str,
    body: str | None = None,
    data: dict | None = None,
) -> None:
    db.add(Notification(userId=user_id, type=type_, title=title, body=body, data=data or {}))


def apply_wallet(
    db: Session,
    user_id: int,
    type_: str,
    amount: int,
    reference: str | None = None,
    note: str | None = None,
) -> int:
    """Cộng/trừ số dư ví (amount âm = trừ) và ghi giao dịch. Trả số dư sau khi đổi."""
    wallet = db.execute(select(Wallet).where(Wallet.userId == user_id)).scalar_one_or_none()
    if wallet is None:
        wallet = Wallet(userId=user_id)
        db.add(wallet)
        db.flush()

    statement = update(Wallet).where(Wallet.id == wallet.id)
    if amount < 0:
        statement = statement.where(Wallet.balance >= -amount)  # không cho âm ví
    balance_after = db.execute(
        statement.values(balance=Wallet.balance + amount).returning(Wallet.balance)
    ).scalar_one_or_none()
    if balance_after is None:
        raise ApiError(400, "Số dư ví không đủ")

    db.add(
        WalletTransaction(
            walletId=wallet.id,
            type=type_,
            amount=amount,
            balanceAfter=balance_after,
            reference=reference,
            note=note,
        )
    )
    return balance_after


def gen_order_code() -> str:
    return f"NL2H-{random.randint(10000, 99999)}"


def gen_dispute_code() -> str:
    return f"TC-{random.randint(1000, 9999)}"


def push_timeline(db: Session, order_id: int, status: str, note: str | None = None) -> None:
    db.add(OrderTimeline(orderId=order_id, status=status, note=note))


def calc_platform_fee(db: Session, category_id: int, order_amount: int) -> tuple[int, float]:
    """Phí sàn của một đơn: ưu tiên feePct của danh mục, không có thì lấy cấu hình chung."""
    category = db.execute(select(Category).where(Category.id == category_id)).scalar_one_or_none()
    percent = 5.0
    if category is not None and category.feePct is not None:
        percent = category.feePct
    else:
        config = db.execute(
            select(FeeConfig).where(
                FeeConfig.kind == "PLATFORM_TXN",
                FeeConfig.name == "Phí sàn chung",
                FeeConfig.isActive.is_(True),
            )
        ).scalars().first()
        if config is not None and config.percent is not None:
            percent = config.percent

    min_config = db.execute(
        select(FeeConfig).where(
            FeeConfig.kind == "PLATFORM_TXN",
            FeeConfig.name == "Phí sàn chung",
            FeeConfig.isActive.is_(True),
        )
    ).scalars().first()
    minimum = min_config.minAmount if min_config is not None and min_config.minAmount is not None else 5000
    raw = js_round(order_amount * percent / 100)
    return max(raw, minimum), float(percent)

