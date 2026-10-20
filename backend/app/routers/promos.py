"""Khuyến mãi — port src/routes/promos.js."""
import math
from typing import Literal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import CurrentUser, current_user, require_role
from ..errors import ApiError
from ..models import Promo
from ..pagination import paged_result, paginate
from ..serialize import to_dict
from ..utils import now, parse_js_date

router = APIRouter()


class ValidateIn(BaseModel):
    code: str
    orderAmount: int = Field(ge=0)


def clean_name(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("String must contain at least 1 character(s)")
    if len(value) > 150:
        raise ValueError("String must contain at most 150 character(s)")
    return value


def clean_code(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if len(value) > 30:
        raise ValueError("String must contain at most 30 character(s)")
    return value


class PromoIn(BaseModel):
    name: str
    type: Literal["PLATFORM_FEE_DISCOUNT", "FREESHIP", "VOUCHER", "BOOST"]
    code: str | None = None
    discountType: Literal["PERCENT", "AMOUNT"] = "PERCENT"
    discountValue: int = Field(ge=0)
    maxDiscount: int | None = None
    minOrder: int = 0
    usageLimit: int | None = None
    startsAt: str
    endsAt: str
    status: Literal["DRAFT", "ACTIVE", "PAUSED", "ENDED"] = "DRAFT"

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        return clean_name(value)

    @field_validator("code")
    @classmethod
    def _code(cls, value: str | None) -> str | None:
        return clean_code(value)


class PromoPatch(BaseModel):
    """promoSchema.partial() của zod: mọi trường không bắt buộc."""

    name: str | None = None
    type: Literal["PLATFORM_FEE_DISCOUNT", "FREESHIP", "VOUCHER", "BOOST"] | None = None
    code: str | None = None
    discountType: Literal["PERCENT", "AMOUNT"] | None = None
    discountValue: int | None = Field(None, ge=0)
    maxDiscount: int | None = None
    minOrder: int | None = None
    usageLimit: int | None = None
    startsAt: str | None = None
    endsAt: str | None = None
    status: Literal["DRAFT", "ACTIVE", "PAUSED", "ENDED"] | None = None

    @field_validator("name")
    @classmethod
    def _name(cls, value: str | None) -> str | None:
        return None if value is None else clean_name(value)

    @field_validator("code")
    @classmethod
    def _code(cls, value: str | None) -> str | None:
        return clean_code(value)


@router.get("")
def active_promos(db: Session = Depends(get_db)):
    moment = now()
    rows = db.execute(
        select(Promo)
        .where(Promo.status == "ACTIVE", Promo.startsAt <= moment, Promo.endsAt >= moment)
        .order_by(Promo.endsAt.asc())
    ).scalars().all()
    return [to_dict(row) for row in rows]


@router.post("/validate")
def validate_promo(payload: ValidateIn, _user: CurrentUser = Depends(current_user), db: Session = Depends(get_db)):
    promo = db.execute(select(Promo).where(Promo.code == payload.code)).scalar_one_or_none()
    moment = now()
    if promo is None or promo.status != "ACTIVE" or promo.startsAt > moment or promo.endsAt < moment:
        return JSONResponse(
            status_code=400, content={"valid": False, "message": "Mã không hợp lệ hoặc đã hết hạn"}
        )
    if promo.usageLimit and promo.usedCount >= promo.usageLimit:
        return JSONResponse(
            status_code=400, content={"valid": False, "message": "Mã đã hết lượt sử dụng"}
        )
    if payload.orderAmount < promo.minOrder:
        minimum = f"{promo.minOrder:,}".replace(",", ".")
        return JSONResponse(
            status_code=400, content={"valid": False, "message": f"Đơn tối thiểu {minimum}đ"}
        )

    if promo.discountType == "PERCENT":
        discount = min(
            math.floor(payload.orderAmount * promo.discountValue / 100 + 0.5),
            promo.maxDiscount or math.inf,
        )
    else:
        discount = promo.discountValue
    return {"valid": True, "promo": {"name": promo.name, "code": promo.code}, "discount": discount}


@router.get("/admin/all")
def all_promos(
    request: Request,
    _admin: CurrentUser = Depends(require_role("ADMIN_CONTENT")),
    db: Session = Depends(get_db),
):
    page = paginate(dict(request.query_params))
    conditions = []
    status = request.query_params.get("status")
    if status:
        conditions.append(Promo.status == status)
    promo_type = request.query_params.get("type")
    if promo_type:
        conditions.append(Promo.type == promo_type)

    rows = db.execute(
        select(Promo)
        .where(*conditions)
        .order_by(Promo.createdAt.desc())
        .offset(page["skip"])
        .limit(page["limit"])
    ).scalars().all()
    total = db.execute(select(func.count()).select_from(Promo).where(*conditions)).scalar_one()
    return paged_result([to_dict(row) for row in rows], total, page["page"], page["limit"])


def _values(payload: PromoIn | PromoPatch) -> dict:
    data = payload.model_dump(exclude_unset=True)
    if "startsAt" in data:
        data["startsAt"] = parse_js_date(data["startsAt"])
    if "endsAt" in data:
        data["endsAt"] = parse_js_date(data["endsAt"])
    return data


@router.post("/admin", status_code=201)
def create_promo(
    payload: PromoIn,
    _admin: CurrentUser = Depends(require_role("ADMIN_CONTENT")),
    db: Session = Depends(get_db),
):
    promo = Promo(**_values(payload))
    db.add(promo)
    db.commit()
    return to_dict(promo)


@router.patch("/admin/{promo_id}")
def update_promo(
    promo_id: int,
    payload: PromoPatch,
    _admin: CurrentUser = Depends(require_role("ADMIN_CONTENT")),
    db: Session = Depends(get_db),
):
    changed = db.execute(
        update(Promo).where(Promo.id == promo_id).values(**_values(payload))
    )
    if changed.rowcount == 0:
        db.rollback()
        raise ApiError(404, "Không tìm thấy khuyến mãi")
    db.commit()
    promo = db.execute(select(Promo).where(Promo.id == promo_id)).scalar_one()
    return to_dict(promo)


@router.delete("/admin/{promo_id}")
def delete_promo(
    promo_id: int,
    _admin: CurrentUser = Depends(require_role("ADMIN_CONTENT")),
    db: Session = Depends(get_db),
):
    deleted = db.execute(Promo.__table__.delete().where(Promo.id == promo_id))
    if deleted.rowcount == 0:
        db.rollback()
        raise ApiError(404, "Không tìm thấy khuyến mãi")
    db.commit()
    return {"message": "Đã xoá khuyến mãi"}
