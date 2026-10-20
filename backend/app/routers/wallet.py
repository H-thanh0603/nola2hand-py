"""Ví SafePay — port src/routes/wallet.js."""
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..deps import CurrentUser, current_user
from ..errors import ApiError
from ..models import BankAccount, Wallet, WalletTransaction, WithdrawalRequest
from ..pagination import paged_result, paginate
from ..quota import account_limit
from ..serialize import to_dict
from ..services.withdrawals import request_withdrawal, transition_withdrawal
from ..utils import apply_wallet, vnd

router = APIRouter()


class TopupIn(BaseModel):
    amount: int = Field(ge=10_000)
    method: str = "MOMO_QR"


class WithdrawIn(BaseModel):
    amount: int = Field(ge=50_000, le=1_000_000_000)
    bankAccountId: int = Field(gt=0)
    requestKey: UUID


class BankIn(BaseModel):
    bankName: str
    accountNumber: str
    accountName: str
    isDefault: bool | None = None

    @field_validator("bankName")
    @classmethod
    def _bank_name(cls, value: str) -> str:
        value = value.strip()
        if not 1 <= len(value) <= 100:
            raise ValueError("String must contain at least 1 character(s)" if not value else "String must contain at most 100 character(s)")
        return value

    @field_validator("accountNumber")
    @classmethod
    def _account_number(cls, value: str) -> str:
        value = value.strip()
        if not 6 <= len(value) <= 30:
            raise ValueError("String must contain at least 6 character(s)" if len(value) < 6 else "String must contain at most 30 character(s)")
        return value

    @field_validator("accountName")
    @classmethod
    def _account_name(cls, value: str) -> str:
        value = value.strip()
        if not 1 <= len(value) <= 100:
            raise ValueError("String must contain at least 1 character(s)" if not value else "String must contain at most 100 character(s)")
        return value


def _wallet(db: Session, user_id: int) -> Wallet:
    wallet = db.execute(select(Wallet).where(Wallet.userId == user_id)).scalar_one_or_none()
    if wallet is None:
        wallet = Wallet(userId=user_id)
        db.add(wallet)
        db.commit()
    return wallet


def _parse_date(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ApiError(400, "Ngày không hợp lệ") from exc
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


@router.get("")
def get_wallet(user: CurrentUser = Depends(current_user), db: Session = Depends(get_db)):
    return to_dict(_wallet(db, user.id))


@router.get("/transactions")
def transactions(
    request: Request,
    user: CurrentUser = Depends(current_user),
    db: Session = Depends(get_db),
):
    page = paginate(dict(request.query_params))
    wallet = db.execute(select(Wallet).where(Wallet.userId == user.id)).scalar_one_or_none()
    if wallet is None:
        return paged_result([], 0, page["page"], page["limit"])

    conditions = [WalletTransaction.walletId == wallet.id]
    type_filter = request.query_params.get("type")
    if type_filter:
        conditions.append(WalletTransaction.type == type_filter)
    start = request.query_params.get("from")
    end = request.query_params.get("to")
    if start:
        conditions.append(WalletTransaction.createdAt >= _parse_date(start))
    if end:
        conditions.append(WalletTransaction.createdAt <= _parse_date(end))

    rows = db.execute(
        select(WalletTransaction)
        .where(*conditions)
        .order_by(WalletTransaction.createdAt.desc())
        .offset(page["skip"])
        .limit(page["limit"])
    ).scalars().all()
    total = db.execute(
        select(func.count()).select_from(WalletTransaction).where(*conditions)
    ).scalar_one()
    return paged_result([to_dict(row) for row in rows], total, page["page"], page["limit"])


@router.post("/topup")
def topup(
    payload: TopupIn,
    user: CurrentUser = Depends(current_user),
    db: Session = Depends(get_db),
):
    if settings.node_env == "production":
        raise ApiError(503, "Nạp tiền cần cổng thanh toán đã xác minh")
    balance = apply_wallet(
        db, user.id, "TOPUP", payload.amount, "TOPUP", f"Nạp tiền qua {payload.method}"
    )
    db.commit()
    return {"message": f"Nạp {vnd(payload.amount)}đ thành công", "balance": balance}


@router.post("/withdraw", status_code=201)
def withdraw(
    payload: WithdrawIn,
    user: CurrentUser = Depends(current_user),
    _quota: CurrentUser = Depends(account_limit("WITHDRAW", 10, 86_400_000)),
    db: Session = Depends(get_db),
):
    request = request_withdrawal(
        db,
        user.id,
        {
            "amount": payload.amount,
            "bankAccountId": payload.bankAccountId,
            "requestKey": str(payload.requestKey),
        },
    )
    wallet = db.execute(select(Wallet).where(Wallet.userId == user.id)).scalar_one()
    return {
        "message": "Đã giữ tiền cho yêu cầu rút; chờ admin duyệt và chuyển khoản.",
        "request": to_dict(request),
        "balance": wallet.balance,
    }


@router.get("/withdrawals")
def my_withdrawals(
    request: Request,
    user: CurrentUser = Depends(current_user),
    db: Session = Depends(get_db),
):
    page = paginate(dict(request.query_params))
    conditions = [WithdrawalRequest.userId == user.id]
    rows = db.execute(
        select(WithdrawalRequest)
        .where(*conditions)
        .order_by(WithdrawalRequest.createdAt.desc())
        .offset(page["skip"])
        .limit(page["limit"])
    ).scalars().all()
    total = db.execute(
        select(func.count()).select_from(WithdrawalRequest).where(*conditions)
    ).scalar_one()
    return paged_result([to_dict(row) for row in rows], total, page["page"], page["limit"])


@router.patch("/withdrawals/{withdrawal_id}/cancel")
def cancel_withdrawal(
    withdrawal_id: int,
    user: CurrentUser = Depends(current_user),
    db: Session = Depends(get_db),
):
    if withdrawal_id <= 0:
        raise ApiError(400, "Dữ liệu không hợp lệ", details=[{"field": "id", "message": "Invalid input"}])
    updated = transition_withdrawal(
        db,
        user,
        withdrawal_id,
        {"action": "CANCEL", "resolution": "Chủ yêu cầu hủy"},
    )
    return to_dict(updated)


@router.get("/banks")
def list_banks(user: CurrentUser = Depends(current_user), db: Session = Depends(get_db)):
    wallet = db.execute(select(Wallet).where(Wallet.userId == user.id)).scalar_one_or_none()
    if wallet is None:
        return []
    rows = db.execute(
        select(BankAccount).where(BankAccount.walletId == wallet.id).order_by(BankAccount.isDefault.desc())
    ).scalars().all()
    return [to_dict(row) for row in rows]


@router.post("/banks", status_code=201)
def add_bank(
    payload: BankIn,
    user: CurrentUser = Depends(current_user),
    db: Session = Depends(get_db),
):
    wallet = _wallet(db, user.id)
    if payload.isDefault:
        db.execute(update(BankAccount).where(BankAccount.walletId == wallet.id).values(isDefault=False))
    bank = BankAccount(walletId=wallet.id, **payload.model_dump(exclude_none=True))
    db.add(bank)
    db.commit()
    return to_dict(bank)


@router.delete("/banks/{bank_id}")
def delete_bank(
    bank_id: int,
    user: CurrentUser = Depends(current_user),
    db: Session = Depends(get_db),
):
    bank = db.execute(
        select(BankAccount)
        .where(
            BankAccount.id == bank_id,
            BankAccount.walletId.in_(select(Wallet.id).where(Wallet.userId == user.id)),
        )
    ).scalar_one_or_none()
    if bank is None:
        raise ApiError(404, "Không tìm thấy")
    db.delete(bank)
    db.commit()
    return {"message": "Đã xoá tài khoản ngân hàng"}
