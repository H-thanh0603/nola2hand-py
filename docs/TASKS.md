# Kế hoạch 4 người — các phần còn thiếu

Tài liệu nền: [`docs/PROJECT.md`](./PROJECT.md). Danh sách endpoint: [`docs/API.md`](./API.md).

Bản Excel dễ đọc để giao việc và theo dõi tiến độ: [`docs/KE-HOACH-TASK-4-NGUOI.xlsx`](./KE-HOACH-TASK-4-NGUOI.xlsx) — 4 sheet: Tổng quan, Danh sách task, Lịch 2 tuần, Chức năng hiện tại.

## 1. Mục tiêu đợt này

Hoàn thiện các chức năng còn thiếu so với checklist, đưa dự án từ "chạy được" sang "bàn giao được":

1. Thanh toán trực tuyến thật (sandbox trước).
2. Đủ section trang chủ: bán chạy, mới nhất, xem nhiều.
3. Sắp xếp theo bán chạy/lượt xem.
4. Báo cáo gian hàng/khách hàng.
5. Sửa địa chỉ, bật Google login.
6. Phân tích cảm xúc hiển thị trên trang sản phẩm.
7. E2E tự động, CI, deploy, mobile/a11y, giảm bundle.

Ước lượng: **25–32 người-ngày**, 4 người làm khoảng **1,5–2 tuần**.

## 2. Nguyên tắc làm việc

- Mỗi người sở hữu nhóm file riêng; sửa file dùng chung (`ui.jsx`, `App.jsx`, `main.py`, migration) phải báo trước.
- Database dùng chung với bản Node: **chỉ migration thêm** (bảng/cột/index), không đổi/xoá cột cũ.
- Chỉ một backend ghi DB tại mỗi thời điểm.
- Mỗi task xong phải có: test (backend hoặc E2E), cập nhật docs, không lỗi console, chạy mobile 375px nếu là UI.
- Không commit `.env`, dữ liệu test, ảnh upload.
- Nhánh: `feat/<task-id>-<mô-tả>`, PR nhỏ, review chéo bắt buộc.

## 3. Phân công

### Người 1 — Thanh toán và đơn hàng

Phụ trách backend thanh toán, escrow, UI thanh toán. Đây là phần rủi ro cao nhất.

| ID | Việc | File/khu vực | Ước lượng | Phụ thuộc |
|---|---|---|---|---|
| T1.1 | Tạo lớp adapter thanh toán: interface `create_payment`, `verify_webhook`, `refund`; provider sandbox đầu tiên (MoMo hoặc VNPay) | `backend/app/services/payments/`, `config.py` | 1,5 ngày | Có credential sandbox |
| T1.2 | Bảng `PaymentIntent` + migration: provider, purpose (TOPUP/DEPOSIT/REMAINDER), orderId, amount, status, externalId, idempotencyKey | `models.py`, `alembic/` | 0,5 ngày | — |
| T1.3 | API tạo thanh toán + webhook/IPN: xác minh chữ ký, idempotent, cập nhật Order/Escrow/Wallet trong một transaction | `routers/payments.py`, `services/escrow.py` | 2 ngày | T1.1, T1.2 |
| T1.4 | Cho phép cọc/thanh toán phần còn lại bằng cổng ngoài; bỏ giới hạn "chỉ ví" ở escrow | `routers/escrow.py`, `orders.py` | 1 ngày | T1.3 |
| T1.5 | UI chọn phương thức, mở cổng/QR, chờ webhook, hiển thị trạng thái; bỏ nhãn "demo" khi provider bật | `Cart.jsx`, `OrderDetail.jsx`, `Wallet.jsx` | 1,5 ngày | T1.3 |
| T1.6 | Test: chữ ký sai, webhook trùng, timeout, huỷ, hoàn tiền; script đối soát | `tests/test_payments.py` | 1 ngày | T1.3–T1.5 |

**Nghiệm thu**
- Thanh toán sandbox thành công → đơn chuyển đúng trạng thái, tiền vào escrow/ví đúng một lần.
- Gửi webhook 2 lần không cộng tiền 2 lần.
- Chữ ký sai bị từ chối, có log audit.
- Không có đường nào cộng tiền khi chưa xác minh webhook.
- Có script đối soát `PaymentIntent` với `WalletTransaction`/`Escrow`.

### Người 2 — Khám phá và trang chủ

Phụ trách truy vấn xếp hạng, section trang chủ, sắp xếp.

| ID | Việc | File/khu vực | Ước lượng | Phụ thuộc |
|---|---|---|---|---|
| T2.1 | API xếp hạng: bán chạy (đơn COMPLETED, loại huỷ/hoàn), mới nhất, xem nhiều; thêm `sort=best_sellers`, `sort=most_viewed` | `routers/listings.py` | 1 ngày | — |
| T2.2 | Index DB cho `views`, `createdAt`, `Order.status/listingId` nếu thiếu | migration | 0,5 ngày | — |
| T2.3 | 3 section trang chủ: Bán chạy / Mới nhất / Xem nhiều, mỗi section 8 tin + link "Xem tất cả" | `Catalog.jsx` | 1 ngày | T2.1 |
| T2.4 | Thêm 2 lựa chọn sắp xếp vào catalog; giữ state trên URL | `Catalog.jsx` | 0,5 ngày | T2.1 |
| T2.5 | Test API xếp hạng + test UI section, responsive 375px | `tests/test_listings*.py`, E2E | 1 ngày | T2.1–T2.4 |

**Nghiệm thu**
- Trang chủ hiển thị đủ 3 section, không trùng tin trong cùng section.
- "Bán chạy" chỉ tính đơn hoàn tất; huỷ/hoàn tiền không tính.
- Sắp xếp mới hoạt động và giữ khi chuyển trang.
- API không N+1; thời gian phản hồi trang chủ < 500 ms với dữ liệu hiện tại.

### Người 3 — Tài khoản và tin cậy

Phụ trách Google login, địa chỉ, báo cáo shop/người dùng, cảm xúc trên trang sản phẩm.

| ID | Việc | File/khu vực | Ước lượng | Phụ thuộc |
|---|---|---|---|---|
| T3.1 | Bật Google login: cấu hình `GOOGLE_CLIENT_ID` + Authorized JavaScript origin, kiểm thử đăng nhập, tài liệu hoá | `Auth.jsx`, `auth.py`, `.env.example` | 0,5 ngày | Client ID |
| T3.2 | API + UI sửa địa chỉ (`PATCH /users/me/addresses/:id`) | `users.py`, `Profile.jsx` | 0,5 ngày | — |
| T3.3 | Mở rộng report target `SHOP`, `USER`: validate, chống trùng, thông báo admin | `reports.py` | 1 ngày | — |
| T3.4 | UI báo cáo shop/người dùng ở trang shop, chat, hồ sơ; admin xử lý cảnh cáo/khoá | `Shop.jsx`, `Chat.jsx`, `Admin.jsx` | 1 ngày | T3.3 |
| T3.5 | Cảm xúc trên trang sản phẩm: API insights theo listing + badge/tóm tắt trong phần đánh giá | `reviews.py`, `Listing.jsx` | 1 ngày | — |
| T3.6 | Test quyền, report trùng, report chính mình, ẩn danh người báo cáo | `tests/` | 1 ngày | T3.1–T3.5 |
| T3.7 | Admin UI quản lý danh mục (API CRUD đã có) | `Admin.jsx` | 1 ngày | — |

**Nghiệm thu**
- Google login chạy với client ID test; thiếu cấu hình thì nút ẩn, không lỗi.
- Sửa địa chỉ lưu đúng, chỉ chủ tài khoản sửa được.
- Report shop/user tạo được, admin thấy trong hàng đợi, người bị báo không thấy danh tính người báo.
- Trang sản phẩm hiển thị tóm tắt cảm xúc; thiếu AI key vẫn có kết quả local.

### Người 4 — Nền tảng, QA, deploy

Phụ trách email/AI production, E2E, CI, deploy, mobile/a11y, bundle.

| ID | Việc | File/khu vực | Ước lượng | Phụ thuộc |
|---|---|---|---|---|
| T4.1 | Email production: xác minh domain Resend, template, retry, log; kiểm tra hộp thư thật | `services/mail.py`, docs | 1 ngày | Resend key |
| T4.2 | OpenAI production: key, model, đánh giá prompt trợ lý + cảm xúc, fallback, rate limit | `services/ai.py`, `assistant.py` | 1 ngày | Key |
| T4.3 | Đưa Playwright vào repo: auth, catalog, giỏ → đơn, seller, admin, payment mock | `e2e/`, `package.json` | 2 ngày | T1.5 |
| T4.4 | CI GitHub Actions: PostgreSQL service, pytest, build frontend, E2E, cache | `.github/workflows/` | 1 ngày | T4.3 |
| T4.5 | Deploy: nginx/systemd hoặc compose, HTTPS, volume `uploads` + `.local`, backup/restore, chạy migration, một backend ghi DB | `deploy/`, docs | 2 ngày | — |
| T4.6 | Mobile 375/768 + a11y: focus trap modal, label, contrast, keyboard | `ui.jsx`, CSS, pages | 1,5 ngày | — |
| T4.7 | Fallback route hash lạ + code-split Admin/Seller/chart.js; ngân sách JS ban đầu < 400 KB | `App.jsx`, `vite.config.js` | 1 ngày | — |
| T4.8 | Chuẩn hoá URL ảnh seed `localhost:4000` khi deploy domain khác | script/docs | 0,5 ngày | — |

**Nghiệm thu**
- CI xanh trên PR: pytest + build + E2E.
- Deploy một lệnh, healthcheck OK, upload/evidence còn sau restart.
- Backup và restore thử thành công.
- Lighthouse mobile accessibility ≥ 90; không tràn ngang 375px.
- Trang lỗi route lạ không còn trắng.

## 4. Lịch 2 sprint

### Sprint 1 (ngày 1–5)

| Người | Việc |
|---|---|
| 1 | T1.1 adapter + T1.2 bảng PaymentIntent + T1.3 webhook |
| 2 | T2.1 API xếp hạng + T2.2 index + T2.3 section trang chủ |
| 3 | T3.1 Google + T3.2 sửa địa chỉ + T3.3 backend report |
| 4 | T4.1 email + T4.3 khung E2E + T4.4 CI |

Mốc ngày 5: backend các phần mới chạy được, UI cơ bản, CI có pipeline.

### Sprint 2 (ngày 6–10)

| Người | Việc |
|---|---|
| 1 | T1.4–T1.6 UI thanh toán + test + đối soát |
| 2 | T2.4–T2.5 sắp xếp + test + responsive |
| 3 | T3.4 UI report + T3.5 cảm xúc + T3.6 test + T3.7 danh mục |
| 4 | T4.2 AI + T4.5 deploy + T4.6 mobile/a11y + T4.7 bundle |

Ngày 11–12: tích hợp, chạy E2E toàn bộ, sửa lỗi, cập nhật docs, release.

## 5. Việc chung cuối đợt

- Chạy lại 125 test backend + toàn bộ E2E.
- Kiểm tra 4 role bằng tài khoản thật: guest, buyer, seller, admin nội dung, admin tài chính.
- Kiểm tra luồng tiền trên database test: cọc → xác nhận → giao → hoàn tất → đối soát ví/escrow.
- Cập nhật `docs/PROJECT.md`, `docs/API.md`, README.
- Tag phiên bản mới, ghi changelog.

## 6. Không làm trong đợt này

| Việc | Lý do |
|---|---|
| Thêm cột số lượng vào `CartItem` | Đổi schema dùng chung, ảnh hưởng bản Node; nghiệp vụ hiện tại mỗi tin là một món |
| Khuyến mãi cho giỏ nhiều món | Mỗi tin tạo một đơn riêng; cần thiết kế lại mô hình đơn/promo |
| Chuyển TypeScript/Tailwind | Không thêm chức năng; chỉ làm khi có yêu cầu thiết kế mới |
| Đa ngôn ngữ, đa tiền tệ | Ngoài phạm vi |

## 7. Rủi ro

| Rủi ro | Giảm thiểu |
|---|---|
| Không có credential cổng thanh toán sandbox | Làm adapter + webhook giả lập trước; không giả lập production; chốt nhà cung cấp sớm |
| Webhook cộng tiền 2 lần | Bảng idempotency + transaction + test gửi trùng |
| Migration ảnh hưởng bản Node | Chỉ thêm bảng/cột/index; chạy thử bản Node đọc dữ liệu sau migration |
| E2E flaky vì dùng DB thật | DB test riêng hoặc cleanup theo prefix; selector ổn định |
| Hai backend cùng ghi DB | Tắt bản Node khi test; ghi rõ trong checklist deploy |
| Bundle tăng | Đo trước/sau, code-split, ngân sách 400 KB |
