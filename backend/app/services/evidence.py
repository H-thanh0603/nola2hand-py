"""Bằng chứng trả hàng/tranh chấp — port src/services/evidence.js.

Ảnh nằm trong <repo>/.local/evidence, tên do route upload (nhóm 6) sinh ra:
<userId>-<uuid>.<jpg|png|webp>.
"""
import re
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..deps import CurrentUser
from ..errors import ApiError
from ..models import Dispute, DisputeEvidence, Order, ReturnRequest

EVIDENCE_DIR = Path(__file__).resolve().parents[3] / ".local" / "evidence"
NAME_RE = re.compile(
    r"^[1-9]\d*-[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}\.(jpg|png|webp)\Z"
)
PATH_PREFIX = "/api/v1/upload/evidence/"


def origin() -> str:
    return settings.app_url.rstrip("/")


def evidence_name(url: str) -> str | None:
    """Tên file nếu URL thuộc kho bằng chứng của chính app này, None nếu là URL ngoài."""
    parsed = urlparse(url)
    if f"{parsed.scheme}://{parsed.netloc}" != origin():
        return None
    if not parsed.path.startswith(PATH_PREFIX):
        return None
    name = parsed.path[len(PATH_PREFIX):]
    if len(name) > 100 or not NAME_RE.match(name) or parsed.query or parsed.fragment:
        raise ApiError(400, "Đường dẫn bằng chứng không hợp lệ")
    return name


def assert_own_evidence(urls: list[str] | None, user_id: int) -> None:
    for url in urls or []:
        name = evidence_name(url)
        if name is None:
            continue
        if int(name.split("-")[0]) != user_id:
            raise ApiError(403, "Không được đính kèm bằng chứng riêng của tài khoản khác")
        if not (EVIDENCE_DIR / name).is_file():
            raise ApiError(400, "Không tìm thấy ảnh bằng chứng")


def may_read_evidence(db: Session, actor: CurrentUser, url: str) -> bool:
    """Chủ ảnh, admin tài chính, hoặc buyer/seller của đơn có tranh chấp/trả hàng chứa ảnh."""
    name = evidence_name(url)
    if name is None:
        return False
    if int(name.split("-")[0]) == actor.id or "ADMIN_FINANCE" in actor.roles:
        return True

    parties = (Order.buyerId == actor.id) | (Order.sellerId == actor.id)
    returning = db.execute(
        select(ReturnRequest.id)
        .join(Order, Order.id == ReturnRequest.orderId)
        .where(ReturnRequest.evidences.contains([url]), parties)
    ).first()
    if returning is not None:
        return True

    dispute = db.execute(
        select(DisputeEvidence.id)
        .join(Dispute, Dispute.id == DisputeEvidence.disputeId)
        .join(Order, Order.id == Dispute.orderId)
        .where(DisputeEvidence.url == url, parties)
    ).first()
    return dispute is not None
