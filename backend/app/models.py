"""Model SQLAlchemy — sinh tự động, đừng sửa tay.

Sinh lại: python scripts/gen_models.py
Nguồn: database PostgreSQL của bản Node (xem PLAN.md).
"""
from typing import Any

from sqlalchemy import Boolean, DateTime, Enum, Float, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class ActionQuota(Base):
    __tablename__ = "ActionQuota"

    userId: Mapped[Any] = mapped_column(Integer, name="userId", primary_key=True, nullable=False)
    action: Mapped[Any] = mapped_column(Text, name="action", primary_key=True, nullable=False)
    windowStart: Mapped[Any] = mapped_column(DateTime, name="windowStart", primary_key=True, nullable=False)
    count: Mapped[Any] = mapped_column(Integer, name="count", nullable=False)


class Address(Base):
    __tablename__ = "Address"

    id: Mapped[Any] = mapped_column(Integer, name="id", primary_key=True, nullable=False)
    userId: Mapped[Any] = mapped_column(Integer, name="userId", nullable=False)
    label: Mapped[Any] = mapped_column(Text, name="label", nullable=False)
    receiver: Mapped[Any] = mapped_column(Text, name="receiver", nullable=False)
    phone: Mapped[Any] = mapped_column(Text, name="phone", nullable=False)
    street: Mapped[Any] = mapped_column(Text, name="street", nullable=False)
    ward: Mapped[Any] = mapped_column(Text, name="ward")
    district: Mapped[Any] = mapped_column(Text, name="district")
    city: Mapped[Any] = mapped_column(Text, name="city", nullable=False)
    isDefault: Mapped[Any] = mapped_column(Boolean, name="isDefault", nullable=False)


class AuditLog(Base):
    __tablename__ = "AuditLog"

    id: Mapped[Any] = mapped_column(Integer, name="id", primary_key=True, nullable=False)
    adminId: Mapped[Any] = mapped_column(Integer, name="adminId", nullable=False)
    action: Mapped[Any] = mapped_column(Text, name="action", nullable=False)
    target: Mapped[Any] = mapped_column(Text, name="target")
    detail: Mapped[Any] = mapped_column(JSONB, name="detail")
    createdAt: Mapped[Any] = mapped_column(DateTime, name="createdAt", nullable=False)


class BankAccount(Base):
    __tablename__ = "BankAccount"

    id: Mapped[Any] = mapped_column(Integer, name="id", primary_key=True, nullable=False)
    walletId: Mapped[Any] = mapped_column(Integer, name="walletId", nullable=False)
    bankName: Mapped[Any] = mapped_column(Text, name="bankName", nullable=False)
    accountNumber: Mapped[Any] = mapped_column(Text, name="accountNumber", nullable=False)
    accountName: Mapped[Any] = mapped_column(Text, name="accountName", nullable=False)
    isDefault: Mapped[Any] = mapped_column(Boolean, name="isDefault", nullable=False)


class Banner(Base):
    __tablename__ = "Banner"

    id: Mapped[Any] = mapped_column(Integer, name="id", primary_key=True, nullable=False)
    title: Mapped[Any] = mapped_column(Text, name="title", nullable=False)
    imageUrl: Mapped[Any] = mapped_column(Text, name="imageUrl", nullable=False)
    linkUrl: Mapped[Any] = mapped_column(Text, name="linkUrl")
    position: Mapped[Any] = mapped_column(Enum("HOME_HERO", "HOME_SECONDARY", "CATEGORY", name="BannerPosition"), name="position", nullable=False)
    startsAt: Mapped[Any] = mapped_column(DateTime, name="startsAt", nullable=False)
    endsAt: Mapped[Any] = mapped_column(DateTime, name="endsAt", nullable=False)
    status: Mapped[Any] = mapped_column(Enum("DRAFT", "ACTIVE", "PAUSED", "ENDED", name="BannerStatus"), name="status", nullable=False)
    views: Mapped[Any] = mapped_column(Integer, name="views", nullable=False)
    createdAt: Mapped[Any] = mapped_column(DateTime, name="createdAt", nullable=False)


class CartItem(Base):
    __tablename__ = "CartItem"

    userId: Mapped[Any] = mapped_column(Integer, name="userId", primary_key=True, nullable=False)
    listingId: Mapped[Any] = mapped_column(Integer, name="listingId", primary_key=True, nullable=False)
    createdAt: Mapped[Any] = mapped_column(DateTime, name="createdAt", nullable=False)


class Category(Base):
    __tablename__ = "Category"

    id: Mapped[Any] = mapped_column(Integer, name="id", primary_key=True, nullable=False)
    name: Mapped[Any] = mapped_column(Text, name="name", nullable=False)
    slug: Mapped[Any] = mapped_column(Text, name="slug", nullable=False)
    icon: Mapped[Any] = mapped_column(Text, name="icon")
    parentId: Mapped[Any] = mapped_column(Integer, name="parentId")
    feePct: Mapped[Any] = mapped_column(Float, name="feePct")


class Dispute(Base):
    __tablename__ = "Dispute"

    id: Mapped[Any] = mapped_column(Integer, name="id", primary_key=True, nullable=False)
    code: Mapped[Any] = mapped_column(Text, name="code", nullable=False)
    orderId: Mapped[Any] = mapped_column(Integer, name="orderId", nullable=False)
    buyerId: Mapped[Any] = mapped_column(Integer, name="buyerId", nullable=False)
    sellerId: Mapped[Any] = mapped_column(Integer, name="sellerId", nullable=False)
    reason: Mapped[Any] = mapped_column(Text, name="reason", nullable=False)
    description: Mapped[Any] = mapped_column(Text, name="description", nullable=False)
    amount: Mapped[Any] = mapped_column(Integer, name="amount", nullable=False)
    status: Mapped[Any] = mapped_column(Enum("OPEN", "REVIEWING", "REFUNDED", "REJECTED", "CLOSED", name="DisputeStatus"), name="status", nullable=False)
    resolution: Mapped[Any] = mapped_column(Text, name="resolution")
    createdAt: Mapped[Any] = mapped_column(DateTime, name="createdAt", nullable=False)
    updatedAt: Mapped[Any] = mapped_column(DateTime, name="updatedAt", nullable=False)


class DisputeEvidence(Base):
    __tablename__ = "DisputeEvidence"

    id: Mapped[Any] = mapped_column(Integer, name="id", primary_key=True, nullable=False)
    disputeId: Mapped[Any] = mapped_column(Integer, name="disputeId", nullable=False)
    url: Mapped[Any] = mapped_column(Text, name="url", nullable=False)
    note: Mapped[Any] = mapped_column(Text, name="note")


class Escrow(Base):
    __tablename__ = "Escrow"

    id: Mapped[Any] = mapped_column(Integer, name="id", primary_key=True, nullable=False)
    orderId: Mapped[Any] = mapped_column(Integer, name="orderId", nullable=False)
    amount: Mapped[Any] = mapped_column(Integer, name="amount", nullable=False)
    status: Mapped[Any] = mapped_column(Enum("HELD", "RELEASED", "REFUNDED", "CANCELLED", name="EscrowStatus"), name="status", nullable=False)
    heldAt: Mapped[Any] = mapped_column(DateTime, name="heldAt", nullable=False)
    releasedAt: Mapped[Any] = mapped_column(DateTime, name="releasedAt")


class Favorite(Base):
    __tablename__ = "Favorite"

    userId: Mapped[Any] = mapped_column(Integer, name="userId", primary_key=True, nullable=False)
    listingId: Mapped[Any] = mapped_column(Integer, name="listingId", primary_key=True, nullable=False)
    createdAt: Mapped[Any] = mapped_column(DateTime, name="createdAt", nullable=False)


class FeeConfig(Base):
    __tablename__ = "FeeConfig"

    id: Mapped[Any] = mapped_column(Integer, name="id", primary_key=True, nullable=False)
    kind: Mapped[Any] = mapped_column(Enum("PLATFORM_TXN", "WITHDRAW", "PENALTY", name="FeeKind"), name="kind", nullable=False)
    name: Mapped[Any] = mapped_column(Text, name="name", nullable=False)
    percent: Mapped[Any] = mapped_column(Float, name="percent")
    amount: Mapped[Any] = mapped_column(Integer, name="amount")
    minAmount: Mapped[Any] = mapped_column(Integer, name="minAmount")
    condition: Mapped[Any] = mapped_column(Text, name="condition")
    isActive: Mapped[Any] = mapped_column(Boolean, name="isActive", nullable=False)
    updatedAt: Mapped[Any] = mapped_column(DateTime, name="updatedAt", nullable=False)


class Listing(Base):
    __tablename__ = "Listing"

    id: Mapped[Any] = mapped_column(Integer, name="id", primary_key=True, nullable=False)
    sellerId: Mapped[Any] = mapped_column(Integer, name="sellerId", nullable=False)
    categoryId: Mapped[Any] = mapped_column(Integer, name="categoryId", nullable=False)
    title: Mapped[Any] = mapped_column(Text, name="title", nullable=False)
    description: Mapped[Any] = mapped_column(Text, name="description", nullable=False)
    price: Mapped[Any] = mapped_column(Integer, name="price", nullable=False)
    originalPrice: Mapped[Any] = mapped_column(Integer, name="originalPrice")
    condition: Mapped[Any] = mapped_column(Enum("NEW", "LIKE_NEW", "USED_GOOD", "USED_FAIR", "FOR_PARTS", name="ListingCondition"), name="condition", nullable=False)
    isFree: Mapped[Any] = mapped_column(Boolean, name="isFree", nullable=False)
    isVerified: Mapped[Any] = mapped_column(Boolean, name="isVerified", nullable=False)
    status: Mapped[Any] = mapped_column(Enum("DRAFT", "PENDING_REVIEW", "ACTIVE", "HIDDEN", "SOLD_OUT", "REJECTED", "DELETED", "RESERVED", name="ListingStatus"), name="status", nullable=False)
    rejectReason: Mapped[Any] = mapped_column(Text, name="rejectReason")
    views: Mapped[Any] = mapped_column(Integer, name="views", nullable=False)
    boostedUntil: Mapped[Any] = mapped_column(DateTime, name="boostedUntil")
    createdAt: Mapped[Any] = mapped_column(DateTime, name="createdAt", nullable=False)
    updatedAt: Mapped[Any] = mapped_column(DateTime, name="updatedAt", nullable=False)
    city: Mapped[Any] = mapped_column(Text, name="city", nullable=False)
    deliveryMethod: Mapped[Any] = mapped_column(Text, name="deliveryMethod", nullable=False)
    specifications: Mapped[Any] = mapped_column(JSONB, name="specifications", nullable=False)


class ListingImage(Base):
    __tablename__ = "ListingImage"

    id: Mapped[Any] = mapped_column(Integer, name="id", primary_key=True, nullable=False)
    listingId: Mapped[Any] = mapped_column(Integer, name="listingId", nullable=False)
    url: Mapped[Any] = mapped_column(Text, name="url", nullable=False)
    sortOrder: Mapped[Any] = mapped_column(Integer, name="sortOrder", nullable=False)


class Message(Base):
    __tablename__ = "Message"

    id: Mapped[Any] = mapped_column(Integer, name="id", primary_key=True, nullable=False)
    senderId: Mapped[Any] = mapped_column(Integer, name="senderId", nullable=False)
    receiverId: Mapped[Any] = mapped_column(Integer, name="receiverId", nullable=False)
    listingId: Mapped[Any] = mapped_column(Integer, name="listingId")
    orderId: Mapped[Any] = mapped_column(Integer, name="orderId")
    body: Mapped[Any] = mapped_column(Text, name="body", nullable=False)
    isRead: Mapped[Any] = mapped_column(Boolean, name="isRead", nullable=False)
    createdAt: Mapped[Any] = mapped_column(DateTime, name="createdAt", nullable=False)


class Notification(Base):
    __tablename__ = "Notification"

    id: Mapped[Any] = mapped_column(Integer, name="id", primary_key=True, nullable=False)
    userId: Mapped[Any] = mapped_column(Integer, name="userId", nullable=False)
    type: Mapped[Any] = mapped_column(Text, name="type", nullable=False)
    title: Mapped[Any] = mapped_column(Text, name="title", nullable=False)
    body: Mapped[Any] = mapped_column(Text, name="body")
    data: Mapped[Any] = mapped_column(JSONB, name="data")
    isRead: Mapped[Any] = mapped_column(Boolean, name="isRead", nullable=False)
    createdAt: Mapped[Any] = mapped_column(DateTime, name="createdAt", nullable=False)


class Order(Base):
    __tablename__ = "Order"

    id: Mapped[Any] = mapped_column(Integer, name="id", primary_key=True, nullable=False)
    code: Mapped[Any] = mapped_column(Text, name="code", nullable=False)
    buyerId: Mapped[Any] = mapped_column(Integer, name="buyerId", nullable=False)
    sellerId: Mapped[Any] = mapped_column(Integer, name="sellerId", nullable=False)
    listingId: Mapped[Any] = mapped_column(Integer, name="listingId", nullable=False)
    priceAgreed: Mapped[Any] = mapped_column(Integer, name="priceAgreed", nullable=False)
    depositAmount: Mapped[Any] = mapped_column(Integer, name="depositAmount", nullable=False)
    remainingAmount: Mapped[Any] = mapped_column(Integer, name="remainingAmount", nullable=False)
    shippingFee: Mapped[Any] = mapped_column(Integer, name="shippingFee", nullable=False)
    discountAmount: Mapped[Any] = mapped_column(Integer, name="discountAmount", nullable=False)
    totalAmount: Mapped[Any] = mapped_column(Integer, name="totalAmount", nullable=False)
    platformFee: Mapped[Any] = mapped_column(Integer, name="platformFee", nullable=False)
    paymentMethod: Mapped[Any] = mapped_column(Text, name="paymentMethod")
    status: Mapped[Any] = mapped_column(Enum("PENDING_DEPOSIT", "DEPOSITED", "CONFIRMED", "SHIPPING", "DELIVERED", "COMPLETED", "CANCELLED", "DISPUTED", "REFUNDED", name="OrderStatus"), name="status", nullable=False)
    shipName: Mapped[Any] = mapped_column(Text, name="shipName")
    shipPhone: Mapped[Any] = mapped_column(Text, name="shipPhone")
    shipAddress: Mapped[Any] = mapped_column(Text, name="shipAddress")
    note: Mapped[Any] = mapped_column(Text, name="note")
    trackingCode: Mapped[Any] = mapped_column(Text, name="trackingCode")
    cancelReason: Mapped[Any] = mapped_column(Text, name="cancelReason")
    createdAt: Mapped[Any] = mapped_column(DateTime, name="createdAt", nullable=False)
    updatedAt: Mapped[Any] = mapped_column(DateTime, name="updatedAt", nullable=False)
    reservationExpiresAt: Mapped[Any] = mapped_column(DateTime, name="reservationExpiresAt")
    settlementMethod: Mapped[Any] = mapped_column(Text, name="settlementMethod", nullable=False)
    codCollectedAt: Mapped[Any] = mapped_column(DateTime, name="codCollectedAt")


class OrderTimeline(Base):
    __tablename__ = "OrderTimeline"

    id: Mapped[Any] = mapped_column(Integer, name="id", primary_key=True, nullable=False)
    orderId: Mapped[Any] = mapped_column(Integer, name="orderId", nullable=False)
    status: Mapped[Any] = mapped_column(Text, name="status", nullable=False)
    note: Mapped[Any] = mapped_column(Text, name="note")
    createdAt: Mapped[Any] = mapped_column(DateTime, name="createdAt", nullable=False)


class Post(Base):
    __tablename__ = "Post"

    id: Mapped[Any] = mapped_column(Integer, name="id", primary_key=True, nullable=False)
    authorId: Mapped[Any] = mapped_column(Integer, name="authorId", nullable=False)
    title: Mapped[Any] = mapped_column(Text, name="title", nullable=False)
    slug: Mapped[Any] = mapped_column(Text, name="slug", nullable=False)
    excerpt: Mapped[Any] = mapped_column(Text, name="excerpt")
    coverUrl: Mapped[Any] = mapped_column(Text, name="coverUrl")
    content: Mapped[Any] = mapped_column(Text, name="content", nullable=False)
    status: Mapped[Any] = mapped_column(Enum("DRAFT", "PUBLISHED", "HIDDEN", name="PostStatus"), name="status", nullable=False)
    views: Mapped[Any] = mapped_column(Integer, name="views", nullable=False)
    createdAt: Mapped[Any] = mapped_column(DateTime, name="createdAt", nullable=False)
    updatedAt: Mapped[Any] = mapped_column(DateTime, name="updatedAt", nullable=False)


class PriceHistory(Base):
    __tablename__ = "PriceHistory"

    id: Mapped[Any] = mapped_column(Integer, name="id", primary_key=True, nullable=False)
    listingId: Mapped[Any] = mapped_column(Integer, name="listingId", nullable=False)
    price: Mapped[Any] = mapped_column(Integer, name="price", nullable=False)
    createdAt: Mapped[Any] = mapped_column(DateTime, name="createdAt", nullable=False)


class PriceOffer(Base):
    __tablename__ = "PriceOffer"

    id: Mapped[Any] = mapped_column(Integer, name="id", primary_key=True, nullable=False)
    listingId: Mapped[Any] = mapped_column(Integer, name="listingId", nullable=False)
    buyerId: Mapped[Any] = mapped_column(Integer, name="buyerId", nullable=False)
    offeredPrice: Mapped[Any] = mapped_column(Integer, name="offeredPrice", nullable=False)
    message: Mapped[Any] = mapped_column(Text, name="message")
    shipMethod: Mapped[Any] = mapped_column(Text, name="shipMethod")
    status: Mapped[Any] = mapped_column(Enum("PENDING", "ACCEPTED", "REJECTED", "CANCELLED", "EXPIRED", name="OfferStatus"), name="status", nullable=False)
    expiresAt: Mapped[Any] = mapped_column(DateTime, name="expiresAt", nullable=False)
    createdAt: Mapped[Any] = mapped_column(DateTime, name="createdAt", nullable=False)


class Promo(Base):
    __tablename__ = "Promo"

    id: Mapped[Any] = mapped_column(Integer, name="id", primary_key=True, nullable=False)
    name: Mapped[Any] = mapped_column(Text, name="name", nullable=False)
    type: Mapped[Any] = mapped_column(Enum("PLATFORM_FEE_DISCOUNT", "FREESHIP", "VOUCHER", "BOOST", name="PromoType"), name="type", nullable=False)
    code: Mapped[Any] = mapped_column(Text, name="code")
    discountType: Mapped[Any] = mapped_column(Text, name="discountType", nullable=False)
    discountValue: Mapped[Any] = mapped_column(Integer, name="discountValue", nullable=False)
    maxDiscount: Mapped[Any] = mapped_column(Integer, name="maxDiscount")
    minOrder: Mapped[Any] = mapped_column(Integer, name="minOrder", nullable=False)
    usageLimit: Mapped[Any] = mapped_column(Integer, name="usageLimit")
    usedCount: Mapped[Any] = mapped_column(Integer, name="usedCount", nullable=False)
    startsAt: Mapped[Any] = mapped_column(DateTime, name="startsAt", nullable=False)
    endsAt: Mapped[Any] = mapped_column(DateTime, name="endsAt", nullable=False)
    status: Mapped[Any] = mapped_column(Enum("DRAFT", "ACTIVE", "PAUSED", "ENDED", name="PromoStatus"), name="status", nullable=False)
    createdAt: Mapped[Any] = mapped_column(DateTime, name="createdAt", nullable=False)


class PromoUsage(Base):
    __tablename__ = "PromoUsage"

    id: Mapped[Any] = mapped_column(Integer, name="id", primary_key=True, nullable=False)
    promoId: Mapped[Any] = mapped_column(Integer, name="promoId", nullable=False)
    userId: Mapped[Any] = mapped_column(Integer, name="userId", nullable=False)
    orderId: Mapped[Any] = mapped_column(Integer, name="orderId")
    usedAt: Mapped[Any] = mapped_column(DateTime, name="usedAt", nullable=False)


class Report(Base):
    __tablename__ = "Report"

    id: Mapped[Any] = mapped_column(Integer, name="id", primary_key=True, nullable=False)
    reporterId: Mapped[Any] = mapped_column(Integer, name="reporterId", nullable=False)
    targetType: Mapped[Any] = mapped_column(Enum("COMMENT", "LISTING_DESC", "MESSAGE", "AVATAR", "LISTING", name="ReportTargetType"), name="targetType", nullable=False)
    targetId: Mapped[Any] = mapped_column(Integer, name="targetId", nullable=False)
    targetUserId: Mapped[Any] = mapped_column(Integer, name="targetUserId")
    reason: Mapped[Any] = mapped_column(Text, name="reason", nullable=False)
    description: Mapped[Any] = mapped_column(Text, name="description")
    status: Mapped[Any] = mapped_column(Enum("NEW", "REVIEWING", "RESOLVED", "DISMISSED", name="ReportStatus"), name="status", nullable=False)
    handlerId: Mapped[Any] = mapped_column(Integer, name="handlerId")
    resolution: Mapped[Any] = mapped_column(Text, name="resolution")
    createdAt: Mapped[Any] = mapped_column(DateTime, name="createdAt", nullable=False)
    updatedAt: Mapped[Any] = mapped_column(DateTime, name="updatedAt", nullable=False)


class ReturnRequest(Base):
    __tablename__ = "ReturnRequest"

    id: Mapped[Any] = mapped_column(Integer, name="id", primary_key=True, nullable=False)
    orderId: Mapped[Any] = mapped_column(Integer, name="orderId", nullable=False)
    reference: Mapped[Any] = mapped_column(Text, name="reference", nullable=False)
    status: Mapped[Any] = mapped_column(Text, name="status", nullable=False)
    originalOrderStatus: Mapped[Any] = mapped_column(Enum("PENDING_DEPOSIT", "DEPOSITED", "CONFIRMED", "SHIPPING", "DELIVERED", "COMPLETED", "CANCELLED", "DISPUTED", "REFUNDED", name="OrderStatus"), name="originalOrderStatus", nullable=False)
    reason: Mapped[Any] = mapped_column(Text, name="reason", nullable=False)
    evidences: Mapped[Any] = mapped_column(JSONB, name="evidences", nullable=False)
    resolution: Mapped[Any] = mapped_column(Text, name="resolution")
    fundingSource: Mapped[Any] = mapped_column(Text, name="fundingSource")
    refundAmount: Mapped[Any] = mapped_column(Integer, name="refundAmount", nullable=False)
    codAmount: Mapped[Any] = mapped_column(Integer, name="codAmount", nullable=False)
    codReference: Mapped[Any] = mapped_column(Text, name="codReference")
    codRefundedAt: Mapped[Any] = mapped_column(DateTime, name="codRefundedAt")
    codConfirmedAt: Mapped[Any] = mapped_column(DateTime, name="codConfirmedAt")
    trackingCode: Mapped[Any] = mapped_column(Text, name="trackingCode")
    receivedNote: Mapped[Any] = mapped_column(Text, name="receivedNote")
    requestedAt: Mapped[Any] = mapped_column(DateTime, name="requestedAt", nullable=False)
    approvedAt: Mapped[Any] = mapped_column(DateTime, name="approvedAt")
    shippedAt: Mapped[Any] = mapped_column(DateTime, name="shippedAt")
    receivedAt: Mapped[Any] = mapped_column(DateTime, name="receivedAt")
    refundedAt: Mapped[Any] = mapped_column(DateTime, name="refundedAt")
    updatedAt: Mapped[Any] = mapped_column(DateTime, name="updatedAt", nullable=False)


class Review(Base):
    __tablename__ = "Review"

    id: Mapped[Any] = mapped_column(Integer, name="id", primary_key=True, nullable=False)
    orderId: Mapped[Any] = mapped_column(Integer, name="orderId", nullable=False)
    reviewerId: Mapped[Any] = mapped_column(Integer, name="reviewerId", nullable=False)
    revieweeId: Mapped[Any] = mapped_column(Integer, name="revieweeId", nullable=False)
    listingId: Mapped[Any] = mapped_column(Integer, name="listingId")
    rating: Mapped[Any] = mapped_column(Integer, name="rating", nullable=False)
    comment: Mapped[Any] = mapped_column(Text, name="comment")
    type: Mapped[Any] = mapped_column(Text, name="type", nullable=False)
    sellerReply: Mapped[Any] = mapped_column(Text, name="sellerReply")
    createdAt: Mapped[Any] = mapped_column(DateTime, name="createdAt", nullable=False)
    sentiment: Mapped[Any] = mapped_column(Text, name="sentiment", nullable=False)
    sentimentSource: Mapped[Any] = mapped_column(Text, name="sentimentSource", nullable=False)


class Role(Base):
    __tablename__ = "Role"

    id: Mapped[Any] = mapped_column(Integer, name="id", primary_key=True, nullable=False)
    name: Mapped[Any] = mapped_column(Text, name="name", nullable=False)
    description: Mapped[Any] = mapped_column(Text, name="description")


class SavedSearch(Base):
    __tablename__ = "SavedSearch"

    id: Mapped[Any] = mapped_column(Integer, name="id", primary_key=True, nullable=False)
    userId: Mapped[Any] = mapped_column(Integer, name="userId", nullable=False)
    name: Mapped[Any] = mapped_column(Text, name="name", nullable=False)
    filters: Mapped[Any] = mapped_column(JSONB, name="filters", nullable=False)
    enabled: Mapped[Any] = mapped_column(Boolean, name="enabled", nullable=False)
    createdAt: Mapped[Any] = mapped_column(DateTime, name="createdAt", nullable=False)


class SavedSearchMatch(Base):
    __tablename__ = "SavedSearchMatch"

    searchId: Mapped[Any] = mapped_column(Integer, name="searchId", primary_key=True, nullable=False)
    listingId: Mapped[Any] = mapped_column(Integer, name="listingId", primary_key=True, nullable=False)
    createdAt: Mapped[Any] = mapped_column(DateTime, name="createdAt", nullable=False)


class SellerProfile(Base):
    __tablename__ = "SellerProfile"

    id: Mapped[Any] = mapped_column(Integer, name="id", primary_key=True, nullable=False)
    userId: Mapped[Any] = mapped_column(Integer, name="userId", nullable=False)
    shopName: Mapped[Any] = mapped_column(Text, name="shopName", nullable=False)
    rating: Mapped[Any] = mapped_column(Float, name="rating", nullable=False)
    totalReviews: Mapped[Any] = mapped_column(Integer, name="totalReviews", nullable=False)
    responseRate: Mapped[Any] = mapped_column(Integer, name="responseRate", nullable=False)
    totalOrders: Mapped[Any] = mapped_column(Integer, name="totalOrders", nullable=False)
    createdAt: Mapped[Any] = mapped_column(DateTime, name="createdAt", nullable=False)


class User(Base):
    __tablename__ = "User"

    id: Mapped[Any] = mapped_column(Integer, name="id", primary_key=True, nullable=False)
    email: Mapped[Any] = mapped_column(Text, name="email", nullable=False)
    passwordHash: Mapped[Any] = mapped_column(Text, name="passwordHash", nullable=False)
    fullName: Mapped[Any] = mapped_column(Text, name="fullName", nullable=False)
    phone: Mapped[Any] = mapped_column(Text, name="phone")
    avatarUrl: Mapped[Any] = mapped_column(Text, name="avatarUrl")
    dateOfBirth: Mapped[Any] = mapped_column(DateTime, name="dateOfBirth")
    gender: Mapped[Any] = mapped_column(Text, name="gender")
    bio: Mapped[Any] = mapped_column(Text, name="bio")
    isVerified: Mapped[Any] = mapped_column(Boolean, name="isVerified", nullable=False)
    idVerified: Mapped[Any] = mapped_column(Boolean, name="idVerified", nullable=False)
    status: Mapped[Any] = mapped_column(Enum("ACTIVE", "BANNED", "PENDING_VERIFICATION", name="UserStatus"), name="status", nullable=False)
    banReason: Mapped[Any] = mapped_column(Text, name="banReason")
    bannedAt: Mapped[Any] = mapped_column(DateTime, name="bannedAt")
    createdAt: Mapped[Any] = mapped_column(DateTime, name="createdAt", nullable=False)
    updatedAt: Mapped[Any] = mapped_column(DateTime, name="updatedAt", nullable=False)
    googleId: Mapped[Any] = mapped_column(Text, name="googleId")
    passwordResetTokenHash: Mapped[Any] = mapped_column(Text, name="passwordResetTokenHash")
    passwordResetExpiresAt: Mapped[Any] = mapped_column(DateTime, name="passwordResetExpiresAt")
    emailVerificationTokenHash: Mapped[Any] = mapped_column(Text, name="emailVerificationTokenHash")
    emailVerificationExpiresAt: Mapped[Any] = mapped_column(DateTime, name="emailVerificationExpiresAt")
    sessionVersion: Mapped[Any] = mapped_column(Integer, name="sessionVersion", nullable=False)
    canManageRoles: Mapped[Any] = mapped_column(Boolean, name="canManageRoles", nullable=False)
    emailVerifiedAt: Mapped[Any] = mapped_column(DateTime, name="emailVerifiedAt")
    emailOtpHash: Mapped[Any] = mapped_column(Text, name="emailOtpHash")
    emailOtpExpiresAt: Mapped[Any] = mapped_column(DateTime, name="emailOtpExpiresAt")
    emailOtpAttempts: Mapped[Any] = mapped_column(Integer, name="emailOtpAttempts", nullable=False)
    passwordOtpHash: Mapped[Any] = mapped_column(Text, name="passwordOtpHash")
    passwordOtpExpiresAt: Mapped[Any] = mapped_column(DateTime, name="passwordOtpExpiresAt")
    passwordOtpAttempts: Mapped[Any] = mapped_column(Integer, name="passwordOtpAttempts", nullable=False)


class UserBlock(Base):
    __tablename__ = "UserBlock"

    blockerId: Mapped[Any] = mapped_column(Integer, name="blockerId", primary_key=True, nullable=False)
    blockedId: Mapped[Any] = mapped_column(Integer, name="blockedId", primary_key=True, nullable=False)
    createdAt: Mapped[Any] = mapped_column(DateTime, name="createdAt", nullable=False)


class UserRole(Base):
    __tablename__ = "UserRole"

    userId: Mapped[Any] = mapped_column(Integer, name="userId", primary_key=True, nullable=False)
    roleId: Mapped[Any] = mapped_column(Integer, name="roleId", primary_key=True, nullable=False)


class Wallet(Base):
    __tablename__ = "Wallet"

    id: Mapped[Any] = mapped_column(Integer, name="id", primary_key=True, nullable=False)
    userId: Mapped[Any] = mapped_column(Integer, name="userId", nullable=False)
    balance: Mapped[Any] = mapped_column(Integer, name="balance", nullable=False)
    pendingBalance: Mapped[Any] = mapped_column(Integer, name="pendingBalance", nullable=False)


class WalletTransaction(Base):
    __tablename__ = "WalletTransaction"

    id: Mapped[Any] = mapped_column(Integer, name="id", primary_key=True, nullable=False)
    walletId: Mapped[Any] = mapped_column(Integer, name="walletId", nullable=False)
    type: Mapped[Any] = mapped_column(Enum("TOPUP", "WITHDRAW", "ORDER_INCOME", "ORDER_PAYMENT", "PLATFORM_FEE", "REFUND", "ADJUSTMENT", name="TxnType"), name="type", nullable=False)
    amount: Mapped[Any] = mapped_column(Integer, name="amount", nullable=False)
    balanceAfter: Mapped[Any] = mapped_column(Integer, name="balanceAfter", nullable=False)
    status: Mapped[Any] = mapped_column(Enum("PENDING", "SUCCESS", "FAILED", name="TxnStatus"), name="status", nullable=False)
    reference: Mapped[Any] = mapped_column(Text, name="reference")
    note: Mapped[Any] = mapped_column(Text, name="note")
    createdAt: Mapped[Any] = mapped_column(DateTime, name="createdAt", nullable=False)


class WithdrawalRequest(Base):
    __tablename__ = "WithdrawalRequest"

    id: Mapped[Any] = mapped_column(Integer, name="id", primary_key=True, nullable=False)
    userId: Mapped[Any] = mapped_column(Integer, name="userId", nullable=False)
    requestKey: Mapped[Any] = mapped_column(Text, name="requestKey", nullable=False)
    reference: Mapped[Any] = mapped_column(Text, name="reference", nullable=False)
    amount: Mapped[Any] = mapped_column(Integer, name="amount", nullable=False)
    fee: Mapped[Any] = mapped_column(Integer, name="fee", nullable=False)
    bankName: Mapped[Any] = mapped_column(Text, name="bankName", nullable=False)
    accountNumber: Mapped[Any] = mapped_column(Text, name="accountNumber", nullable=False)
    accountName: Mapped[Any] = mapped_column(Text, name="accountName", nullable=False)
    status: Mapped[Any] = mapped_column(Text, name="status", nullable=False)
    resolution: Mapped[Any] = mapped_column(Text, name="resolution")
    transferReference: Mapped[Any] = mapped_column(Text, name="transferReference")
    paidAt: Mapped[Any] = mapped_column(DateTime, name="paidAt")
    handledBy: Mapped[Any] = mapped_column(Integer, name="handledBy")
    createdAt: Mapped[Any] = mapped_column(DateTime, name="createdAt", nullable=False)
    updatedAt: Mapped[Any] = mapped_column(DateTime, name="updatedAt", nullable=False)
    bankAccountId: Mapped[Any] = mapped_column(Integer, name="bankAccountId")


