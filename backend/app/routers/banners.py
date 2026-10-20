"""Banner quảng cáo — port src/routes/banners.js."""
from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, field_validator
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import CurrentUser, require_role
from ..errors import ApiError
from ..models import Banner
from ..pagination import paged_result, paginate
from ..serialize import to_dict
from ..utils import now, parse_js_date
from ..validators import http_url

router = APIRouter()

Position = Literal["HOME_HERO", "HOME_SECONDARY", "CATEGORY"]
BannerStatus = Literal["DRAFT", "ACTIVE", "PAUSED", "ENDED"]


def clean_title(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("String must contain at least 1 character(s)")
    if len(value) > 150:
        raise ValueError("String must contain at most 150 character(s)")
    return value


def clean_link(value: str | None) -> str | None:
    if value is None or value == "":
        return value
    return http_url(value, "Link")


class BannerIn(BaseModel):
    title: str
    imageUrl: str
    linkUrl: str | None = None
    position: Position
    startsAt: str
    endsAt: str
    status: BannerStatus = "DRAFT"

    @field_validator("title")
    @classmethod
    def _title(cls, value: str) -> str:
        return clean_title(value)

    @field_validator("imageUrl")
    @classmethod
    def _image(cls, value: str) -> str:
        return http_url(value, "Ảnh banner")

    @field_validator("linkUrl")
    @classmethod
    def _link(cls, value: str | None) -> str | None:
        return clean_link(value)


class BannerPatch(BaseModel):
    """bannerSchema.partial() của zod: mọi trường không bắt buộc."""

    title: str | None = None
    imageUrl: str | None = None
    linkUrl: str | None = None
    position: Position | None = None
    startsAt: str | None = None
    endsAt: str | None = None
    status: BannerStatus | None = None

    @field_validator("title")
    @classmethod
    def _title(cls, value: str | None) -> str | None:
        return None if value is None else clean_title(value)

    @field_validator("imageUrl")
    @classmethod
    def _image(cls, value: str | None) -> str | None:
        return None if value is None else http_url(value, "Ảnh banner")

    @field_validator("linkUrl")
    @classmethod
    def _link(cls, value: str | None) -> str | None:
        return clean_link(value)


@router.get("")
def active_banners(request: Request, db: Session = Depends(get_db)):
    moment = now()
    conditions = [Banner.status == "ACTIVE", Banner.startsAt <= moment, Banner.endsAt >= moment]
    position = request.query_params.get("position")
    if position:
        conditions.append(Banner.position == position)
    rows = db.execute(
        select(Banner).where(*conditions).order_by(Banner.createdAt.desc())
    ).scalars().all()
    return [to_dict(row) for row in rows]


@router.get("/admin/all")
def all_banners(
    request: Request,
    _admin: CurrentUser = Depends(require_role("ADMIN_CONTENT")),
    db: Session = Depends(get_db),
):
    page = paginate(dict(request.query_params))
    conditions = []
    status = request.query_params.get("status")
    if status:
        conditions.append(Banner.status == status)

    rows = db.execute(
        select(Banner)
        .where(*conditions)
        .order_by(Banner.createdAt.desc())
        .offset(page["skip"])
        .limit(page["limit"])
    ).scalars().all()
    total = db.execute(select(func.count()).select_from(Banner).where(*conditions)).scalar_one()
    return paged_result([to_dict(row) for row in rows], total, page["page"], page["limit"])


def _values(payload: BannerIn | BannerPatch) -> dict:
    data = payload.model_dump(exclude_unset=True)
    if "startsAt" in data:
        data["startsAt"] = parse_js_date(data["startsAt"])
    if "endsAt" in data:
        data["endsAt"] = parse_js_date(data["endsAt"])
    return data


@router.post("/admin", status_code=201)
def create_banner(
    payload: BannerIn,
    _admin: CurrentUser = Depends(require_role("ADMIN_CONTENT")),
    db: Session = Depends(get_db),
):
    banner = Banner(**_values(payload))
    db.add(banner)
    db.commit()
    return to_dict(banner)


@router.patch("/admin/{banner_id}")
def update_banner(
    banner_id: int,
    payload: BannerPatch,
    _admin: CurrentUser = Depends(require_role("ADMIN_CONTENT")),
    db: Session = Depends(get_db),
):
    changed = db.execute(
        update(Banner).where(Banner.id == banner_id).values(**_values(payload))
    )
    if changed.rowcount == 0:
        db.rollback()
        raise ApiError(404, "Không tìm thấy banner")
    db.commit()
    banner = db.execute(select(Banner).where(Banner.id == banner_id)).scalar_one()
    return to_dict(banner)


@router.delete("/admin/{banner_id}")
def delete_banner(
    banner_id: int,
    _admin: CurrentUser = Depends(require_role("ADMIN_CONTENT")),
    db: Session = Depends(get_db),
):
    deleted = db.execute(Banner.__table__.delete().where(Banner.id == banner_id))
    if deleted.rowcount == 0:
        db.rollback()
        raise ApiError(404, "Không tìm thấy banner")
    db.commit()
    return {"message": "Đã xoá banner"}
