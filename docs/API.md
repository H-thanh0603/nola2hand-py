# API Nola2Hand

Base URL: `/api/v1`. Đăng nhập bằng `Authorization: Bearer <JWT>`.
Sai/thiếu token: 401; sai vai trò: 403; quá hạn mức: 429. Lỗi trả `{ "message": "..." }`.
Ngày giờ là UTC, dạng `2026-10-20T08:00:00.000Z`. Tiền là số nguyên VND.

## admin

- `GET /api/v1/admin/audit`
- `GET /api/v1/admin/finance/charts/order-status`
- `GET /api/v1/admin/finance/charts/revenue`
- `GET /api/v1/admin/finance/fees`
- `POST /api/v1/admin/finance/fees`
- `DELETE /api/v1/admin/finance/fees/{fee_id}`
- `PATCH /api/v1/admin/finance/fees/{fee_id}`
- `GET /api/v1/admin/finance/overview`
- `GET /api/v1/admin/finance/revenue`
- `GET /api/v1/admin/finance/transactions`
- `GET /api/v1/admin/finance/withdrawals`
- `PATCH /api/v1/admin/finance/withdrawals/{withdrawal_id}`
- `GET /api/v1/admin/users`
- `GET /api/v1/admin/users/stats`
- `PATCH /api/v1/admin/users/{user_id}/lock`
- `PATCH /api/v1/admin/users/{user_id}/roles`
- `PATCH /api/v1/admin/users/{user_id}/unlock`
- `PATCH /api/v1/admin/users/{user_id}/verify`

## assistant

- `POST /api/v1/assistant`

## auth

- `POST /api/v1/auth/change-password`
- `GET /api/v1/auth/config`
- `POST /api/v1/auth/forgot-password`
- `POST /api/v1/auth/google`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/logout`
- `GET /api/v1/auth/me`
- `POST /api/v1/auth/register`
- `POST /api/v1/auth/resend-verification`
- `POST /api/v1/auth/reset-password`
- `POST /api/v1/auth/reset-password-otp`
- `POST /api/v1/auth/verify-email`
- `POST /api/v1/auth/verify-otp`

## banners

- `GET /api/v1/banners`
- `POST /api/v1/banners/admin`
- `GET /api/v1/banners/admin/all`
- `DELETE /api/v1/banners/admin/{banner_id}`
- `PATCH /api/v1/banners/admin/{banner_id}`

## cart

- `DELETE /api/v1/cart`
- `GET /api/v1/cart`
- `POST /api/v1/cart`
- `POST /api/v1/cart/checkout`
- `DELETE /api/v1/cart/{listing_id}`

## categories

- `GET /api/v1/categories`
- `POST /api/v1/categories`
- `GET /api/v1/categories/specifications`
- `DELETE /api/v1/categories/{category_id}`
- `PATCH /api/v1/categories/{category_id}`

## chat

- `GET /api/v1/chat/blocks`
- `DELETE /api/v1/chat/blocks/{blocked_id}`
- `POST /api/v1/chat/blocks/{blocked_id}`
- `GET /api/v1/chat/conversations`
- `POST /api/v1/chat/messages`
- `GET /api/v1/chat/with/{user_id}`

## disputes

- `GET /api/v1/disputes/admin/all`
- `PATCH /api/v1/disputes/admin/{dispute_id}/resolve`
- `GET /api/v1/disputes/mine`
- `POST /api/v1/disputes/orders/{order_id}/disputes`

## escrow

- `GET /api/v1/escrow/mine`
- `POST /api/v1/escrow/orders/{order_id}/deposit`
- `POST /api/v1/escrow/orders/{order_id}/pay-remainder`
- `POST /api/v1/escrow/{escrow_id}/refund`

## khác

- `GET /health`

## listings

- `GET /api/v1/listings`
- `POST /api/v1/listings`
- `GET /api/v1/listings/admin/pending`
- `PATCH /api/v1/listings/admin/{listing_id}/moderate`
- `GET /api/v1/listings/compare`
- `GET /api/v1/listings/me/favorites`
- `GET /api/v1/listings/recommended`
- `DELETE /api/v1/listings/{listing_id}`
- `GET /api/v1/listings/{listing_id}`
- `PATCH /api/v1/listings/{listing_id}`
- `POST /api/v1/listings/{listing_id}/boost`
- `POST /api/v1/listings/{listing_id}/favorite`
- `POST /api/v1/listings/{listing_id}/offers`
- `GET /api/v1/listings/{listing_id}/price-history`
- `GET /api/v1/listings/{listing_id}/related`
- `PATCH /api/v1/listings/{listing_id}/visibility`

## notifications

- `GET /api/v1/notifications`
- `PATCH /api/v1/notifications/read-all`
- `PATCH /api/v1/notifications/{notification_id}/read`

## offers

- `GET /api/v1/offers/inbox`
- `GET /api/v1/offers/mine`
- `PATCH /api/v1/offers/{offer_id}`

## orders

- `POST /api/v1/orders`
- `GET /api/v1/orders/admin/all`
- `GET /api/v1/orders/mine`
- `GET /api/v1/orders/sales`
- `GET /api/v1/orders/{order_id}`
- `POST /api/v1/orders/{order_id}/confirm-cod`
- `PATCH /api/v1/orders/{order_id}/status`

## posts

- `GET /api/v1/posts`
- `POST /api/v1/posts`
- `GET /api/v1/posts/me/all`
- `DELETE /api/v1/posts/{post_id}`
- `PATCH /api/v1/posts/{post_id}`
- `GET /api/v1/posts/{slug}`

## promos

- `GET /api/v1/promos`
- `POST /api/v1/promos/admin`
- `GET /api/v1/promos/admin/all`
- `DELETE /api/v1/promos/admin/{promo_id}`
- `PATCH /api/v1/promos/admin/{promo_id}`
- `POST /api/v1/promos/validate`

## reports

- `POST /api/v1/reports`
- `GET /api/v1/reports/admin/all`
- `GET /api/v1/reports/admin/stats`
- `PATCH /api/v1/reports/admin/{report_id}`

## returns

- `GET /api/v1/returns`
- `GET /api/v1/returns/admin`
- `POST /api/v1/returns/orders/{order_id}`
- `PATCH /api/v1/returns/{return_id}`

## reviews

- `GET /api/v1/reviews/insights`
- `GET /api/v1/reviews/mine/pending`
- `POST /api/v1/reviews/orders/{order_id}/reviews`
- `GET /api/v1/reviews/users/{user_id}`
- `POST /api/v1/reviews/{review_id}/reply`

## saved-searches

- `GET /api/v1/saved-searches`
- `POST /api/v1/saved-searches`
- `DELETE /api/v1/saved-searches/{search_id}`
- `PATCH /api/v1/saved-searches/{search_id}`

## seller

- `GET /api/v1/seller/charts/revenue`
- `GET /api/v1/seller/dashboard`
- `GET /api/v1/seller/listings`
- `GET /api/v1/seller/listings/{listing_id}`

## shops

- `GET /api/v1/shops/search`
- `GET /api/v1/shops/{shop_id}`

## upload

- `POST /api/v1/upload`
- `GET /api/v1/upload/evidence/{name}`

## users

- `PATCH /api/v1/users/me`
- `GET /api/v1/users/me/addresses`
- `POST /api/v1/users/me/addresses`
- `DELETE /api/v1/users/me/addresses/{address_id}`
- `POST /api/v1/users/me/become-seller`
- `GET /api/v1/users/me/profile`
- `GET /api/v1/users/{user_id}`

## wallet

- `GET /api/v1/wallet`
- `GET /api/v1/wallet/banks`
- `POST /api/v1/wallet/banks`
- `DELETE /api/v1/wallet/banks/{bank_id}`
- `POST /api/v1/wallet/topup`
- `GET /api/v1/wallet/transactions`
- `POST /api/v1/wallet/withdraw`
- `GET /api/v1/wallet/withdrawals`
- `PATCH /api/v1/wallet/withdrawals/{withdrawal_id}/cancel`
