"""Khóa hàng để tránh hai request sửa cùng lúc — port src/services/locks.js."""
from sqlalchemy import text
from sqlalchemy.orm import Session


def lock_user(db: Session, user_id: int) -> None:
    db.execute(text('SELECT id FROM "User" WHERE id = :id FOR UPDATE'), {"id": user_id})
