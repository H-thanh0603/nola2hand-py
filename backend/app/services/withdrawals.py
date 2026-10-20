"""Yêu cầu rút tiền — port src/services/withdrawals.js."""
import uuid

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from ..deps import CurrentUser
from ..errors import ApiError
from ..models import AuditLog, BankAccount, FeeConfig, Wallet, WithdrawalRequest
from ..utils import notify, now
from .locks import lock_user
from .wallet_holds import finish_hold, hold_wallet, post_held_ledger

ALLOWED_FROM = {
    "APPROVE": ("PENDING",),
    "PAY": ("APPROVED",),
    "REJECT": ("PENDING", "APPROVED"),
    "FAIL": ("APPROVED",),
    "CANCEL": ("PENDING",),
}

NEXT_STATUS = {
    "APPROVE": "APPROVED",
    "PAY": "PAID",
    "REJECT": "REJECTED",
    "FAIL": "FAILED",
    "CANCEL": "CANCELLED",
}


def request_withdrawal(db: Session, user_id: int, payload: dict) -> WithdrawalRequest:
    lock_user(db, user_id)

    existing = db.execute(
        select(WithdrawalRequest).where(
            WithdrawalRequest.userId == user_id,
            WithdrawalRequest.requestKey == payload["requestKey"],
        )
    ).scalar_one_or_none()
    if existing is not None:
        if existing.amount != payload["amount"] or existing.bankAccountId != payload["bankAccountId"]:
            raise ApiError(409, "Mã yêu cầu đã dùng với nội dung khác")
        return existing

    bank = db.execute(
        select(BankAccount).where(
            BankAccount.id == payload["bankAccountId"],
            BankAccount.walletId.in_(select(Wallet.id).where(Wallet.userId == user_id)),
        )
    ).scalar_one_or_none()
    if bank is None:
        raise ApiError(404, "Không tìm thấy tài khoản ngân hàng")

    config = db.execute(
        select(FeeConfig).where(
            FeeConfig.kind == "WITHDRAW",
            FeeConfig.name == "Phí rút tiền tiêu chuẩn",
            FeeConfig.isActive.is_(True),
        )
    ).scalars().first()
    fee = config.amount if config is not None and config.amount is not None else 0

    total = payload["amount"] + fee
    if total > 2_000_000_000 or fee < 0:
        raise ApiError(400, "Số tiền/phí không hợp lệ")

    hold_wallet(db, user_id, total)

    request = WithdrawalRequest(
        userId=user_id,
        requestKey=payload["requestKey"],
        reference=f"WD-{uuid.uuid4()}",
        amount=payload["amount"],
        fee=fee,
        bankName=bank.bankName,
        accountNumber=bank.accountNumber,
        accountName=bank.accountName,
        bankAccountId=bank.id,
        updatedAt=now(),
    )
    db.add(request)
    db.commit()
    return request


def transition_withdrawal(
    db: Session,
    actor: CurrentUser,
    request_id: int,
    payload: dict,
) -> WithdrawalRequest:
    db.execute(
        text('SELECT id FROM "WithdrawalRequest" WHERE id = :id FOR UPDATE'), {"id": request_id}
    )
    request = db.execute(
        select(WithdrawalRequest).where(WithdrawalRequest.id == request_id)
    ).scalar_one_or_none()
    if request is None:
        raise ApiError(404, "Không tìm thấy yêu cầu rút")

    action = payload["action"]
    is_admin = "ADMIN_FINANCE" in actor.roles
    if action == "CANCEL":
        if request.userId != actor.id:
            raise ApiError(403, "Chỉ chủ yêu cầu được hủy")
    elif not is_admin:
        raise ApiError(403, "Chỉ admin tài chính xử lý yêu cầu rút")
    elif request.userId == actor.id:
        raise ApiError(403, "Không được duyệt/chuyển yêu cầu rút của chính mình")

    if request.status not in ALLOWED_FROM[action]:
        raise ApiError(409, "Yêu cầu đã thay đổi hoặc không thể thực hiện bước này")
    if action == "PAY" and not (payload.get("transferReference") or "").strip():
        raise ApiError(400, "Cần mã chứng từ chuyển khoản thực tế")

    status = NEXT_STATUS[action]
    total = request.amount + request.fee

    if status != "APPROVED":
        wallet = finish_hold(db, request.userId, total, refund=status != "PAID")
        if status == "PAID":
            post_held_ledger(
                db,
                wallet,
                [
                    {"type": "WITHDRAW", "amount": -request.amount},
                    {"type": "PLATFORM_FEE", "amount": -request.fee},
                ],
                request.reference,
                f"Rút về {request.bankName}; chứng từ {payload['transferReference']}",
            )

    request.status = status
    request.resolution = payload["resolution"]
    request.handledBy = actor.id
    request.updatedAt = now()
    if status == "PAID":
        request.transferReference = payload["transferReference"]
        request.paidAt = now()

    if is_admin:
        db.add(
            AuditLog(
                adminId=actor.id,
                action=f"WITHDRAW_{action}",
                target=f"withdrawal:{request_id}",
                detail={
                    "amount": request.amount,
                    "fee": request.fee,
                    "resolution": payload["resolution"],
                    "transferReference": payload.get("transferReference") or None,
                },
            )
        )
    notify(
        db,
        request.userId,
        "WALLET",
        "Cập nhật yêu cầu rút tiền",
        f"{request.reference}: {status}",
        {"withdrawalId": request_id},
    )
    db.commit()
    db.refresh(request)
    return request
