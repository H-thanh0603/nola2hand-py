"""Chuyển bản ghi ORM thành dict giống Prisma trả về (đủ mọi cột, trừ cột bị loại)."""
from typing import Any

from sqlalchemy import inspect


def to_dict(obj: Any, exclude: tuple[str, ...] = ()) -> dict:
    row = {column.key: getattr(obj, column.key) for column in inspect(obj).mapper.columns}
    return {key: value for key, value in row.items() if key not in exclude}
