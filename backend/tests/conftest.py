"""Fixture dùng chung cho test tích hợp: client + tài khoản thử tự dọn."""
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select, update

from app.db import SessionLocal
from app.main import create_app
from app.models import (
    ActionQuota,
    Address,
    AuditLog,
    BankAccount,
    CartItem,
    Category,
    Dispute,
    DisputeEvidence,
    Escrow,
    Favorite,
    FeeConfig,
    Listing,
    ListingImage,
    Notification,
    Order,
    OrderTimeline,
    Post,
    PriceHistory,
    PriceOffer,
    Promo,
    PromoUsage,
    Report,
    ReturnRequest,
    Review,
    Role,
    SavedSearch,
    SavedSearchMatch,
    SellerProfile,
    User,
    UserRole,
    Wallet,
    WalletTransaction,
    WithdrawalRequest,
)

MAIL_DIR = Path(__file__).resolve().parents[1] / ".local" / "mail"


@pytest.fixture
def client():
    from app.routers.auth import auth_limiter

    auth_limiter.clear()  # giới hạn 100 lượt/15 phút của bản Node không làm hỏng test
    return TestClient(create_app(), raise_server_exceptions=False)


@pytest.fixture
def make_user(client):
    """Đăng ký + đăng nhập một tài khoản thật; teardown xoá sạch mọi thứ nó tạo."""
    created: list[int] = []
    mail_before = set(MAIL_DIR.glob("*.json")) if MAIL_DIR.exists() else set()
    with SessionLocal() as db:
        # Thông báo gửi tới admin thật (vd. finance@nola2hand.vn) cũng phải dọn.
        notif_before = db.execute(select(func.max(Notification.id))).scalar() or 0

    def factory(
        roles: list[str] | None = None,
        can_manage_roles: bool = False,
        verified: bool = False,
    ) -> dict:
        email = f"qa-py-{uuid.uuid4().hex[:10]}@nola2hand.vn"
        password = "matkhau123"
        response = client.post(
            "/api/v1/auth/register",
            json={"fullName": "Tài khoản QA", "email": email, "password": password},
        )
        assert response.status_code == 201, response.text
        user_id = response.json()["user"]["id"]

        if roles or can_manage_roles or verified:
            with SessionLocal() as db:
                for name in roles or []:
                    role_id = db.execute(select(Role.id).where(Role.name == name)).scalar_one()
                    db.add(UserRole(userId=user_id, roleId=role_id))
                values = {}
                if can_manage_roles:
                    values["canManageRoles"] = True
                if verified:
                    values["emailVerifiedAt"] = db.execute(select(User.createdAt).where(User.id == user_id)).scalar_one()
                if values:
                    db.execute(update(User).where(User.id == user_id).values(**values))
                db.commit()

        token = client.post(
            "/api/v1/auth/login", json={"email": email, "password": password}
        ).json()["token"]
        created.append(user_id)
        return {
            "id": user_id,
            "email": email,
            "password": password,
            "token": token,
            "headers": {"Authorization": f"Bearer {token}"},
        }

    yield factory

    mail_after = set(MAIL_DIR.glob("*.json")) if MAIL_DIR.exists() else set()
    for file in mail_after - mail_before:
        file.unlink()

    with SessionLocal() as db:
        listing_ids = list(
            db.execute(select(Listing.id).where(Listing.sellerId.in_(created))).scalars()
        )
        search_ids = list(
            db.execute(select(SavedSearch.id).where(SavedSearch.userId.in_(created))).scalars()
        )
        order_ids = list(
            db.execute(
                select(Order.id).where(Order.buyerId.in_(created) | Order.sellerId.in_(created))
            ).scalars()
        )

        db.execute(delete(PriceOffer).where(PriceOffer.listingId.in_(listing_ids)))
        db.execute(delete(SavedSearchMatch).where(SavedSearchMatch.listingId.in_(listing_ids)))
        db.execute(delete(PriceHistory).where(PriceHistory.listingId.in_(listing_ids)))
        db.execute(delete(ListingImage).where(ListingImage.listingId.in_(listing_ids)))
        db.execute(
            delete(Favorite).where(
                Favorite.listingId.in_(listing_ids) | Favorite.userId.in_(created)
            )
        )
        db.execute(delete(Post).where(Post.authorId.in_(created)))
        db.execute(delete(SavedSearchMatch).where(SavedSearchMatch.searchId.in_(search_ids)))
        db.execute(delete(SavedSearch).where(SavedSearch.userId.in_(created)))
        # Đơn hàng: xoá con trước để không vi phạm khoá ngoại.
        db.execute(
            delete(DisputeEvidence).where(
                DisputeEvidence.disputeId.in_(select(Dispute.id).where(Dispute.orderId.in_(order_ids)))
            )
        )
        db.execute(delete(Dispute).where(Dispute.orderId.in_(order_ids)))
        db.execute(
            delete(Report).where(
                Report.reporterId.in_(created) | Report.targetUserId.in_(created)
            )
        )
        db.execute(delete(ReturnRequest).where(ReturnRequest.orderId.in_(order_ids)))
        db.execute(
            delete(Review).where(
                Review.orderId.in_(order_ids)
                | Review.reviewerId.in_(created)
                | Review.revieweeId.in_(created)
            )
        )
        db.execute(delete(Escrow).where(Escrow.orderId.in_(order_ids)))
        db.execute(delete(OrderTimeline).where(OrderTimeline.orderId.in_(order_ids)))
        db.execute(
            delete(PromoUsage).where(
                PromoUsage.userId.in_(created) | PromoUsage.orderId.in_(order_ids)
            )
        )
        db.execute(
            delete(CartItem).where(
                CartItem.userId.in_(created) | CartItem.listingId.in_(listing_ids)
            )
        )
        db.execute(delete(Order).where(Order.id.in_(order_ids)))
        db.execute(delete(Promo).where(Promo.code.like("qa-promo-%")))
        db.execute(delete(Listing).where(Listing.sellerId.in_(created)))

        targets = [f"listing:{listing_id}" for listing_id in listing_ids]
        db.execute(
            delete(AuditLog).where(
                AuditLog.adminId.in_(created) | AuditLog.target.in_(targets)
            )
        )
        db.execute(
            delete(Notification).where(
                Notification.userId.in_(created) | (Notification.id > notif_before)
            )
        )
        db.execute(delete(Address).where(Address.userId.in_(created)))
        db.execute(delete(SellerProfile).where(SellerProfile.userId.in_(created)))
        db.execute(delete(UserRole).where(UserRole.userId.in_(created)))
        db.execute(delete(WithdrawalRequest).where(WithdrawalRequest.userId.in_(created)))
        db.execute(
            delete(BankAccount).where(
                BankAccount.walletId.in_(select(Wallet.id).where(Wallet.userId.in_(created)))
            )
        )
        db.execute(delete(FeeConfig).where(FeeConfig.name.like("qa-fee-%")))
        db.execute(
            delete(WalletTransaction).where(
                WalletTransaction.walletId.in_(select(Wallet.id).where(Wallet.userId.in_(created)))
            )
        )
        db.execute(delete(Wallet).where(Wallet.userId.in_(created)))
        db.execute(delete(ActionQuota).where(ActionQuota.userId.in_(created)))
        db.execute(delete(User).where(User.id.in_(created)))
        db.execute(delete(Category).where(Category.slug.like("qa-cat-%")))
        db.commit()
