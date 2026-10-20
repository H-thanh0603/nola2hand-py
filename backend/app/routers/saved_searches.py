"""Theo dõi tìm kiếm — port src/routes/saved-searches.js."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, field_validator
from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import CurrentUser, current_user
from ..errors import ApiError
from ..models import Listing, SavedSearch, SavedSearchMatch
from ..serialize import to_dict
from ..services.catalog import ListingFilters, listing_conditions

router = APIRouter()

PAGING_KEYS = ("page", "limit", "sort")


class SavedSearchIn(BaseModel):
    name: str
    filters: ListingFilters

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("String must contain at least 1 character(s)")
        if len(value) > 100:
            raise ValueError("String must contain at most 100 character(s)")
        return value


class EnabledIn(BaseModel):
    enabled: bool


@router.get("")
def list_saved(user: CurrentUser = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.execute(
        select(SavedSearch)
        .where(SavedSearch.userId == user.id)
        .order_by(SavedSearch.createdAt.desc())
    ).scalars().all()
    return [to_dict(row) for row in rows]


@router.post("", status_code=201)
def create_saved(
    payload: SavedSearchIn,
    user: CurrentUser = Depends(current_user),
    db: Session = Depends(get_db),
):
    payload.filters.check_range()
    filters = payload.filters.model_dump(exclude_none=True, exclude=PAGING_KEYS)

    total = db.execute(
        select(func.count()).select_from(SavedSearch).where(SavedSearch.userId == user.id)
    ).scalar_one()
    if total >= 20:
        raise ApiError(400, "Tối đa 20 tìm kiếm theo dõi")

    search = SavedSearch(userId=user.id, name=payload.name, filters=filters)
    db.add(search)
    db.flush()

    matched = db.execute(
        select(Listing.id).where(*listing_conditions(payload.filters))
    ).scalars().all()
    if matched:
        db.execute(
            insert(SavedSearchMatch)
            .values([{"searchId": search.id, "listingId": listing_id} for listing_id in matched])
            .on_conflict_do_nothing(index_elements=["searchId", "listingId"])
        )
    db.commit()
    return to_dict(search)


@router.patch("/{search_id}")
def toggle_saved(
    search_id: int,
    payload: EnabledIn,
    user: CurrentUser = Depends(current_user),
    db: Session = Depends(get_db),
):
    changed = db.execute(
        update(SavedSearch)
        .where(SavedSearch.id == search_id, SavedSearch.userId == user.id)
        .values(enabled=payload.enabled)
    )
    if changed.rowcount == 0:
        db.rollback()
        raise ApiError(404, "Không tìm thấy tìm kiếm")
    db.commit()
    return {"message": "Đã cập nhật theo dõi"}


@router.delete("/{search_id}")
def delete_saved(
    search_id: int,
    user: CurrentUser = Depends(current_user),
    db: Session = Depends(get_db),
):
    db.execute(
        delete(SavedSearch).where(SavedSearch.id == search_id, SavedSearch.userId == user.id)
    )
    db.commit()
    return {"message": "Đã xóa theo dõi"}
