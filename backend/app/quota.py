"""Hạn mức theo tài khoản — port src/services/guards.js (bảng ActionQuota)."""
import math
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from fastapi import Depends
from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from .db import SessionLocal
from .deps import CurrentUser, current_user
from .errors import ApiError
from .models import ActionQuota


def window_start(now_ms: int, window_ms: int) -> datetime:
    """Đầu cửa sổ chứa thời điểm hiện tại, tính theo UTC (giống Math.floor(Date.now()/window)*window)."""
    start_ms = (now_ms // window_ms) * window_ms
    return datetime.fromtimestamp(start_ms / 1000, tz=timezone.utc).replace(tzinfo=None)


def account_limit(action: str, max_calls: int, window_ms: int) -> Callable:
    def dependency(user: CurrentUser = Depends(current_user)) -> CurrentUser:
        now = datetime.now(timezone.utc)
        start = window_start(int(now.timestamp() * 1000), window_ms)
        # Cửa sổ riêng, tách khỏi transaction của route (Node cũng dùng transaction riêng).
        with SessionLocal() as db:  # type: Session
            db.execute(
                insert(ActionQuota)
                .values(userId=user.id, action=action, windowStart=start, count=0)
                .on_conflict_do_nothing(index_elements=["userId", "action", "windowStart"])
            )
            bumped = db.execute(
                update(ActionQuota)
                .where(
                    ActionQuota.userId == user.id,
                    ActionQuota.action == action,
                    ActionQuota.windowStart == start,
                    ActionQuota.count < max_calls,
                )
                .values(count=ActionQuota.count + 1)
                .returning(ActionQuota.count)
            ).scalar_one_or_none()
            db.commit()

        if bumped is None:
            retry_after = math.ceil((start + timedelta(milliseconds=window_ms) - now.replace(tzinfo=None)).total_seconds())
            raise ApiError(
                429,
                "Đã đạt giới hạn thao tác. Vui lòng thử lại sau.",
                headers={"Retry-After": str(max(0, retry_after))},
            )
        return user

    return dependency
