"""Bài viết người bán — port src/routes/posts.js."""
import re
import unicodedata
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, field_validator
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import CurrentUser, current_user, require_role
from ..errors import ApiError
from ..models import Post, User
from ..pagination import paged_result, paginate
from ..serialize import to_dict
from ..utils import now

router = APIRouter()

_BASE36 = "0123456789abcdefghijklmnopqrstuvwxyz"


def _base36(number: int) -> str:
    out = ""
    while number:
        number, remainder = divmod(number, 36)
        out = _BASE36[remainder] + out
    return out or "0"


def slugify(text: str) -> str:
    """Giống slugify của bản Node: bỏ dấu tiếng Việt rồi thêm hậu tố thời gian base36."""
    decomposed = unicodedata.normalize("NFD", text.lower())
    stripped = "".join(char for char in decomposed if not "\u0300" <= char <= "\u036f")
    stripped = re.sub(r"[^a-z0-9]+", "-", stripped.replace("đ", "d")).strip("-")
    stamp = int(datetime.now(timezone.utc).timestamp() * 1000)
    return f"{stripped}-{_base36(stamp)}"


def _title(value: str) -> str:
    value = value.strip()
    if len(value) < 10:
        raise ValueError("String must contain at least 10 character(s)")
    if len(value) > 200:
        raise ValueError("String must contain at most 200 character(s)")
    return value


def _excerpt(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if len(value) > 300:
        raise ValueError("String must contain at most 300 character(s)")
    return value


def _content(value: str) -> str:
    value = value.strip()
    if len(value) < 50:
        raise ValueError("String must contain at least 50 character(s)")
    return value


def _cover(value: str | None) -> str | None:
    if value is None:
        return None
    if not re.match(r"^https?://", value):
        raise ValueError("Invalid url")
    return value


class PostIn(BaseModel):
    title: str
    excerpt: str | None = None
    coverUrl: str | None = None
    content: str
    status: Literal["DRAFT", "PUBLISHED", "HIDDEN"] = "DRAFT"

    @field_validator("title")
    @classmethod
    def _v_title(cls, v: str) -> str:
        return _title(v)

    @field_validator("excerpt")
    @classmethod
    def _v_excerpt(cls, v: str | None) -> str | None:
        return _excerpt(v)

    @field_validator("content")
    @classmethod
    def _v_content(cls, v: str) -> str:
        return _content(v)

    @field_validator("coverUrl")
    @classmethod
    def _v_cover(cls, v: str | None) -> str | None:
        return _cover(v)


class PostPatch(BaseModel):
    title: str | None = None
    excerpt: str | None = None
    coverUrl: str | None = None
    content: str | None = None
    status: Literal["DRAFT", "PUBLISHED", "HIDDEN"] | None = None

    @field_validator("title")
    @classmethod
    def _v_title(cls, v: str | None) -> str | None:
        return None if v is None else _title(v)

    @field_validator("excerpt")
    @classmethod
    def _v_excerpt(cls, v: str | None) -> str | None:
        return _excerpt(v)

    @field_validator("content")
    @classmethod
    def _v_content(cls, v: str | None) -> str | None:
        return None if v is None else _content(v)

    @field_validator("coverUrl")
    @classmethod
    def _v_cover(cls, v: str | None) -> str | None:
        return _cover(v)


def _with_author(db: Session, posts: list[Post]) -> list[dict]:
    author_ids = {post.authorId for post in posts}
    authors = (
        {user.id: user for user in db.execute(select(User).where(User.id.in_(author_ids))).scalars()}
        if author_ids
        else {}
    )

    items = []
    for post in posts:
        item = to_dict(post)
        author = authors.get(post.authorId)
        item["author"] = (
            {"id": author.id, "fullName": author.fullName, "avatarUrl": author.avatarUrl}
            if author
            else None
        )
        items.append(item)
    return items


@router.get("")
def list_posts(request: Request, db: Session = Depends(get_db)):
    query = dict(request.query_params)
    page = paginate(query)

    conditions = [Post.status == "PUBLISHED"]
    if query.get("q"):
        conditions.append(Post.title.ilike(f"%{query['q']}%"))

    posts = db.execute(
        select(Post)
        .where(*conditions)
        .order_by(Post.createdAt.desc())
        .offset(page["skip"])
        .limit(page["limit"])
    ).scalars().all()
    total = db.execute(select(func.count()).select_from(Post).where(*conditions)).scalar_one()
    return paged_result(_with_author(db, posts), total, page["page"], page["limit"])


@router.get("/me/all", dependencies=[Depends(require_role("SELLER"))])
def my_posts(user: CurrentUser = Depends(current_user), db: Session = Depends(get_db)):
    posts = db.execute(
        select(Post).where(Post.authorId == user.id).order_by(Post.updatedAt.desc())
    ).scalars().all()
    return [to_dict(post) for post in posts]


@router.post("", status_code=201, dependencies=[Depends(require_role("SELLER"))])
def create_post(
    payload: PostIn,
    user: CurrentUser = Depends(current_user),
    db: Session = Depends(get_db),
):
    post = Post(
        **payload.model_dump(),
        authorId=user.id,
        slug=slugify(payload.title),
        updatedAt=now(),
    )
    db.add(post)
    db.commit()
    return to_dict(post)


@router.get("/{slug}")
def get_post(slug: str, db: Session = Depends(get_db)):
    post = db.execute(select(Post).where(Post.slug == slug)).scalar_one_or_none()
    if post is None or post.status != "PUBLISHED":
        raise ApiError(404, "Không tìm thấy bài viết")

    payload = _with_author(db, [post])[0]
    db.execute(
        update(Post).where(Post.id == post.id).values(views=Post.views + 1, updatedAt=now())
    )
    db.commit()
    return payload  # như bản Node: số views trả về là số trước khi tăng


@router.patch("/{post_id}", dependencies=[Depends(require_role("SELLER"))])
def update_post(
    post_id: int,
    payload: PostPatch,
    user: CurrentUser = Depends(current_user),
    db: Session = Depends(get_db),
):
    post = db.execute(
        select(Post).where(Post.id == post_id, Post.authorId == user.id)
    ).scalar_one_or_none()
    if post is None:
        raise ApiError(404, "Không tìm thấy bài viết")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(post, field, value)
    post.updatedAt = now()
    db.commit()
    return to_dict(post)


@router.delete("/{post_id}", dependencies=[Depends(require_role("SELLER"))])
def delete_post(
    post_id: int,
    user: CurrentUser = Depends(current_user),
    db: Session = Depends(get_db),
):
    post = db.execute(
        select(Post).where(Post.id == post_id, Post.authorId == user.id)
    ).scalar_one_or_none()
    if post is None:
        raise ApiError(404, "Không tìm thấy bài viết")
    db.delete(post)
    db.commit()
    return {"message": "Đã xoá bài viết"}
