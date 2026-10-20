"""Tin nhắn người mua & người bán — port src/routes/chat.js (polling)."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, field_validator
from sqlalchemy import func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import CurrentUser, current_user
from ..errors import ApiError
from ..models import Message, Order, User, UserBlock
from ..quota import account_limit
from ..serialize import to_dict
from ..utils import notify

router = APIRouter()

BRIEF = ("id", "fullName", "avatarUrl")


class MessageIn(BaseModel):
    receiverId: int
    body: str
    listingId: int | None = None
    orderId: int | None = None

    @field_validator("body")
    @classmethod
    def _body(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Tin nhắn không được bỏ trống")
        if len(value) > 2000:
            raise ValueError("String must contain at most 2000 character(s)")
        return value


def _brief(user: User) -> dict:
    return {field: getattr(user, field) for field in BRIEF}


def _users(db: Session, ids: set[int]) -> dict[int, User]:
    if not ids:
        return {}
    return {
        user.id: user for user in db.execute(select(User).where(User.id.in_(ids))).scalars()
    }


@router.get("/conversations")
def conversations(user: CurrentUser = Depends(current_user), db: Session = Depends(get_db)):
    messages = db.execute(
        select(Message)
        .where(or_(Message.senderId == user.id, Message.receiverId == user.id))
        .order_by(Message.createdAt.desc())
        .limit(200)
    ).scalars().all()

    people = _users(
        db,
        {message.senderId for message in messages} | {message.receiverId for message in messages},
    )

    grouped: dict[str, dict] = {}
    for message in messages:
        other_id = message.receiverId if message.senderId == user.id else message.senderId
        key = f"{other_id}:{message.listingId or 0}"
        if key not in grouped:
            other = people.get(other_id)
            grouped[key] = {
                "user": _brief(other) if other is not None else None,
                "listingId": message.listingId,
                "lastMessage": message.body,
                "at": message.createdAt,
            }

    unread = dict(
        db.execute(
            select(Message.senderId, func.count())
            .where(Message.receiverId == user.id, Message.isRead.is_(False))
            .group_by(Message.senderId)
        ).all()
    )

    result = []
    for key, conversation in grouped.items():
        other_id = int(key.split(":")[0])
        result.append({**conversation, "unread": unread.get(other_id, 0)})
    return result


@router.get("/with/{user_id}")
def history(
    user_id: int,
    listingId: int | None = None,
    user: CurrentUser = Depends(current_user),
    db: Session = Depends(get_db),
):
    conditions = [
        or_(
            (Message.senderId == user.id) & (Message.receiverId == user_id),
            (Message.senderId == user_id) & (Message.receiverId == user.id),
        )
    ]
    if listingId is not None:
        conditions.append(Message.listingId == listingId)

    messages = db.execute(
        select(Message).where(*conditions).order_by(Message.createdAt.asc()).limit(100)
    ).scalars().all()

    db.execute(
        update(Message)
        .where(
            Message.senderId == user_id,
            Message.receiverId == user.id,
            Message.isRead.is_(False),
        )
        .values(isRead=True)
    )
    db.commit()
    return [to_dict(message) for message in messages]


@router.post("/messages", status_code=201)
def send_message(
    payload: MessageIn,
    user: CurrentUser = Depends(account_limit("SEND_MESSAGE", 30, 60_000)),
    db: Session = Depends(get_db),
):
    if payload.receiverId == user.id:
        raise ApiError(400, "Không thể tự nhắn cho chính mình")

    receiver = db.execute(select(User).where(User.id == payload.receiverId)).scalar_one_or_none()
    if receiver is None or receiver.status != "ACTIVE":
        raise ApiError(404, "Người nhận không tồn tại")

    blocked = db.execute(
        select(UserBlock.blockerId).where(
            or_(
                (UserBlock.blockerId == user.id) & (UserBlock.blockedId == receiver.id),
                (UserBlock.blockerId == receiver.id) & (UserBlock.blockedId == user.id),
            )
        )
    ).first()
    if blocked is not None:
        raise ApiError(403, "Không thể nhắn tin do chặn liên lạc")

    if payload.orderId is not None:
        order = db.execute(
            select(Order.id).where(
                Order.id == payload.orderId,
                or_(
                    (Order.buyerId == user.id) & (Order.sellerId == receiver.id),
                    (Order.buyerId == receiver.id) & (Order.sellerId == user.id),
                ),
            )
        ).first()
        if order is None:
            raise ApiError(403, "Đơn không thuộc hai người trong hội thoại")

    message = Message(**payload.model_dump(), senderId=user.id)
    db.add(message)
    db.flush()

    sender = db.execute(select(User).where(User.id == user.id)).scalar_one()
    notify(
        db,
        receiver.id,
        "SYSTEM",
        f"Tin nhắn mới từ {sender.fullName}",
        payload.body[:120],
        {"senderId": user.id},
    )
    db.commit()

    item = to_dict(message)
    item["sender"] = _brief(sender)
    return item


@router.get("/blocks")
def list_blocks(user: CurrentUser = Depends(current_user), db: Session = Depends(get_db)):
    blocked_ids = db.execute(
        select(UserBlock.blockedId).where(UserBlock.blockerId == user.id)
    ).scalars().all()
    users = db.execute(select(User).where(User.id.in_(blocked_ids))).scalars().all()
    return [_brief(row) for row in users]


@router.post("/blocks/{blocked_id}")
def block_user(
    blocked_id: str,
    user: CurrentUser = Depends(account_limit("BLOCK_USER", 20, 3_600_000)),
    db: Session = Depends(get_db),
):
    try:
        target = int(blocked_id)
    except ValueError:
        target = 0
    if target <= 0 or target == user.id:
        raise ApiError(400, "Tài khoản cần chặn không hợp lệ")

    exists = db.execute(select(User.id).where(User.id == target)).scalar_one_or_none()
    if exists is None:
        raise ApiError(404, "Không tìm thấy tài khoản")

    db.execute(
        insert(UserBlock)
        .values(blockerId=user.id, blockedId=target)
        .on_conflict_do_nothing(index_elements=["blockerId", "blockedId"])
    )
    db.commit()
    return {"message": "Đã chặn liên lạc"}


@router.delete("/blocks/{blocked_id}")
def unblock_user(
    blocked_id: int,
    user: CurrentUser = Depends(current_user),
    db: Session = Depends(get_db),
):
    if blocked_id <= 0:
        raise ApiError(400, "Dữ liệu không hợp lệ")
    db.execute(
        UserBlock.__table__.delete().where(
            UserBlock.blockerId == user.id, UserBlock.blockedId == blocked_id
        )
    )
    db.commit()
    return {"message": "Đã bỏ chặn"}
