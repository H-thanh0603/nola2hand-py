"""Helper dùng chung — port dần từ src/utils.js khi tới route cần."""
import math
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from .errors import ApiError
from .models import Notification, Wallet, WalletTransaction
from .types import as_json_datetime


def now() -> datetime:
    """UTC dạng naive, khớp kiểu timestamp của Prisma.

    Lưu ý: cột `updatedAt` của Prisma là @updatedAt — không có default trong DB,
    nên mọi insert/update đều phải tự đặt giá trị này (kể cả updateMany).
    """
    return as_json_datetime(datetime.now(timezone.utc).replace(tzinfo=None))


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
