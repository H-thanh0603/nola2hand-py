"""Giữ tiền trong ví (pendingBalance) — port src/services/wallet-holds.js."""
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..errors import ApiError
from ..models import Wallet, WalletTransaction


def hold_wallet(db: Session, user_id: int, amount: int) -> Wallet:
    """Chuyển `amount` từ số dư khả dụng sang số dư đang giữ."""
    if amount <= 0:
        raise ApiError(400, "Số tiền giữ không hợp lệ")
    wallet = db.execute(select(Wallet).where(Wallet.userId == user_id)).scalar_one_or_none()
    if wallet is None:
        raise ApiError(404, "Không tìm thấy ví")

    changed = db.execute(
        update(Wallet)
        .where(Wallet.id == wallet.id, Wallet.balance >= amount)
        .values(balance=Wallet.balance - amount, pendingBalance=Wallet.pendingBalance + amount)
    )
    if changed.rowcount == 0:
        raise ApiError(400, "Số dư khả dụng không đủ để giữ tiền")

    db.refresh(wallet)
    return wallet


def finish_hold(db: Session, user_id: int, amount: int, refund: bool = False) -> Wallet:
    """Kết thúc giữ tiền: hoàn về số dư (refund) hoặc trừ hẳn khỏi ví."""
    wallet = db.execute(select(Wallet).where(Wallet.userId == user_id)).scalar_one_or_none()
    if wallet is None:
        raise ApiError(404, "Không tìm thấy ví")

    values = {"pendingBalance": Wallet.pendingBalance - amount}
    if refund:
        values["balance"] = Wallet.balance + amount
    changed = db.execute(
        update(Wallet)
        .where(Wallet.id == wallet.id, Wallet.pendingBalance >= amount)
        .values(**values)
    )
    if changed.rowcount == 0:
        raise ApiError(409, "Tiền giữ không khớp, cần đối soát")

    db.refresh(wallet)
    return wallet


def post_held_ledger(
    db: Session,
    wallet: Wallet,
    entries: list[dict],
    reference: str | None,
    note: str | None,
) -> None:
    for entry in entries:
        if not entry.get("amount"):
            continue
        db.add(
            WalletTransaction(
                walletId=wallet.id,
                type=entry["type"],
                amount=entry["amount"],
                balanceAfter=wallet.balance,
                status="SUCCESS",
                reference=reference,
                note=note,
            )
        )
