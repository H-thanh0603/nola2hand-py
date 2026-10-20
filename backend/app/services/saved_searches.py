"""Thông báo tin mới khớp tìm kiếm đã lưu — port src/services/saved-searches.js."""
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from ..models import Listing, SavedSearch, SavedSearchMatch
from ..utils import notify
from .catalog import ListingFilters, listing_conditions


def notify_matching_searches(db: Session, listing_id: int) -> int:
    """Trả số tìm kiếm được thông báo (dùng lại được trong transaction của route)."""
    searches = db.execute(select(SavedSearch).where(SavedSearch.enabled.is_(True))).scalars().all()
    count = 0

    for search in searches:
        try:
            filters = ListingFilters(**search.filters)
        except (ValidationError, TypeError, ValueError):
            # Dữ liệu lưu từ bản cũ có thể thiếu/khác kiểu — bỏ qua thay vì chặn duyệt tin.
            continue

        listing = db.execute(
            select(Listing.id, Listing.title, Listing.sellerId)
            .where(*listing_conditions(filters), Listing.id == listing_id)
        ).first()
        if listing is None or listing.sellerId == search.userId:
            continue

        inserted = db.execute(
            insert(SavedSearchMatch)
            .values(searchId=search.id, listingId=listing_id)
            .on_conflict_do_nothing(index_elements=["searchId", "listingId"])
            .returning(SavedSearchMatch.searchId)
        ).scalar_one_or_none()
        if inserted is None:
            continue

        notify(
            db,
            search.userId,
            "SAVED_SEARCH",
            f"Tin mới cho “{search.name}”",
            listing.title,
            {"listingId": listing_id, "searchId": search.id},
        )
        count += 1
    return count
