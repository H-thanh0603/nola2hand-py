"""Kiểu ngày giờ trả ra JSON giống Prisma.

Prisma (và `JSON.stringify` của JS) trả '2026-10-19T07:21:29.354Z'. Python
isoformat trả '2026-10-19T07:21:29.354000' — không có Z, nên `new Date(...)`
phía trình duyệt hiểu là giờ địa phương và lệch 7 tiếng ở Việt Nam.
"""
from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy.types import TypeDecorator


class JsonDateTime(datetime):
    """datetime naive (giờ UTC trong DB) nhưng in ra kèm 'Z' và 3 số mili giây."""

    def isoformat(self, sep: str = "T", timespec: str = "milliseconds") -> str:
        return super().isoformat(sep=sep, timespec=timespec) + "Z"

    # Cộng/trừ giữ nguyên kiểu, nếu không `now() + timedelta` rơi về datetime
    # thường và JSON mất 'Z' (JS hiểu sai múi giờ).
    def __add__(self, other):
        return as_json_datetime(super().__add__(other))

    def __sub__(self, other):
        result = super().__sub__(other)
        return as_json_datetime(result) if isinstance(result, datetime) else result


def as_json_datetime(value: datetime | None) -> JsonDateTime | None:
    if value is None:
        return None
    if isinstance(value, JsonDateTime):
        return value
    return JsonDateTime(
        value.year, value.month, value.day, value.hour, value.minute, value.second, value.microsecond
    )


class JsDateTime(TypeDecorator):
    """Cột timestamp của Prisma: giữ naive để so sánh được, in ra dạng ISO của JS."""

    impl = DateTime
    cache_ok = True

    def process_result_value(self, value, dialect):
        return as_json_datetime(value)
