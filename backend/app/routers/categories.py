"""Danh mục sản phẩm — port src/routes/categories.js."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_role
from ..errors import ApiError
from ..models import Category, Listing
from ..serialize import to_dict
from ..services.catalog import SPECIFICATION_FIELDS

router = APIRouter()


def _text(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("String must contain at least 1 character(s)")
    if len(value) > 100:
        raise ValueError("String must contain at most 100 character(s)")
    return value


def _slug(value: str) -> str:
    return _text(value).lower()


def _fee(value: float | None) -> float | None:
    if value is not None and not 0 <= value <= 100:
        raise ValueError("Number must be greater than or equal to 0")
    return value


class CategoryIn(BaseModel):
    name: str
    slug: str
    icon: str | None = None
    parentId: int | None = None
    feePct: float | None = None

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        return _text(v)

    @field_validator("slug")
    @classmethod
    def _slug_field(cls, v: str) -> str:
        return _slug(v)

    @field_validator("feePct")
    @classmethod
    def _fee_field(cls, v: float | None) -> float | None:
        return _fee(v)


class CategoryPatch(BaseModel):
    name: str | None = None
    slug: str | None = None
    icon: str | None = None
    parentId: int | None = None
    feePct: float | None = None

    @field_validator("name")
    @classmethod
    def _name(cls, v: str | None) -> str | None:
        return None if v is None else _text(v)

    @field_validator("slug")
    @classmethod
    def _slug_field(cls, v: str | None) -> str | None:
        return None if v is None else _slug(v)

    @field_validator("feePct")
    @classmethod
    def _fee_field(cls, v: float | None) -> float | None:
        return _fee(v)


def _category_or_404(db: Session, category_id: int) -> Category:
    category = db.execute(select(Category).where(Category.id == category_id)).scalar_one_or_none()
    if category is None:
        raise ApiError(404, "Không tìm thấy dữ liệu")
    return category


@router.get("/specifications")
def specifications():
    return SPECIFICATION_FIELDS


@router.get("")
def category_tree(db: Session = Depends(get_db)):
    roots = db.execute(
        select(Category).where(Category.parentId.is_(None)).order_by(Category.name)
    ).scalars().all()
    if not roots:
        return []

    root_ids = [root.id for root in roots]
    children: dict[int, list[Category]] = {root_id: [] for root_id in root_ids}
    for child in db.execute(
        select(Category).where(Category.parentId.in_(root_ids)).order_by(Category.id)
    ).scalars():
        children[child.parentId].append(child)

    counts = dict(
        db.execute(
            select(Listing.categoryId, func.count())
            .where(Listing.categoryId.in_(root_ids))
            .group_by(Listing.categoryId)
        ).all()
    )

    return [
        {
            **to_dict(root),
            "children": [to_dict(child) for child in children[root.id]],
            "_count": {"listings": counts.get(root.id, 0)},
        }
        for root in roots
    ]


@router.post("", status_code=201, dependencies=[Depends(require_role("ADMIN_CONTENT"))])
def create_category(payload: CategoryIn, db: Session = Depends(get_db)):
    category = Category(**payload.model_dump())
    db.add(category)
    db.commit()
    return to_dict(category)


@router.patch("/{category_id}", dependencies=[Depends(require_role("ADMIN_CONTENT"))])
def update_category(
    category_id: int,
    payload: CategoryPatch,
    db: Session = Depends(get_db),
):
    category = _category_or_404(db, category_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(category, field, value)
    db.commit()
    return to_dict(category)


@router.delete("/{category_id}", dependencies=[Depends(require_role("ADMIN_CONTENT"))])
def delete_category(category_id: int, db: Session = Depends(get_db)):
    count = db.execute(
        select(func.count()).select_from(Listing).where(Listing.categoryId == category_id)
    ).scalar_one()
    if count > 0:
        raise ApiError(400, f"Danh mục còn {count} tin đăng, không thể xoá")
    category = _category_or_404(db, category_id)
    db.delete(category)
    db.commit()
    return {"message": "Đã xoá danh mục"}
