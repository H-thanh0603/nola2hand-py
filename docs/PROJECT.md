# Nola2Hand — Tài liệu dự án

## 1. Thông tin chung

| Mục | Nội dung |
|---|---|
| Tên dự án | Nola2Hand |
| Loại | Sàn thương mại điện tử đồ đã qua sử dụng |
| Repo | `H-thanh0603/nola2hand-py` |
| Bản cũ | `H-thanh0603/nola2hand-ft` (Node.js + Express + Prisma + frontend thuần) |
| Phiên bản | `v2.0-python-react` |
| Trạng thái | Backend đủ 143 endpoint; frontend React đủ màn hình; đang ở giai đoạn hoàn thiện và kiểm thử |
| Database | PostgreSQL trên Supabase, dùng chung với bản Node; xem `docs/DATABASE.md` |
| Ngôn ngữ | Python (backend), JavaScript/JSX (frontend) |

## 2. Mục tiêu và phạm vi

- Viết lại backend bằng FastAPI nhưng giữ nguyên đường dẫn, tham số và dạng JSON của 143 endpoint cũ.
- Viết lại giao diện bằng React, dùng lại CSS và luồng nghiệp vụ của bản cũ.
- Cho phép chạy song song về mặt dữ liệu với bản Node: cùng database, cùng quy ước tiền và thời gian.
- Không migrate dữ liệu, không đổi schema hiện có nếu không cần thiết.

Ngoài phạm vi hiện tại: ứng dụng mobile native, microservice, đa ngôn ngữ, đa tiền tệ.

## 3. Tech stack

### Backend

| Thành phần | Công nghệ |
|---|---|
| Ngôn ngữ | Python 3.14 |
| Web framework | FastAPI 0.146 + Uvicorn |
| ORM | SQLAlchemy 2.1 (sync) |
| Migration | Alembic 1.20, baseline `7c0952c8735d` |
| Validation | Pydantic 2.14 |
| Database | PostgreSQL 17 trên Supabase qua psycopg 3 |
| Xác thực | JWT (PyJWT), bcrypt |
| Google | google-auth |
| HTTP client | httpx (Resend, OpenAI) |
| Test | pytest, 125 test |
| Lưu file | đĩa cục bộ: `uploads/` công khai, `.local/evidence/` riêng tư |

### Frontend

| Thành phần | Công nghệ |
|---|---|
| Ngôn ngữ | JavaScript/JSX thuần, không TypeScript |
| Thư viện | React 19 |
| Build/dev | Vite 6 |
| Routing | React Router 7, `HashRouter` (URL `#/...`) |
| Biểu đồ | Chart.js 4 |
| Giao diện | CSS tự viết (`styles.css`, `design.css`), không Tailwind/UI library |
| Gọi API | `fetch`, token trong `localStorage` |
| State | React Context + hook cục bộ, không Redux/Zustand |

### Hạ tầng

- Dev: Vite cổng 5173, proxy `/api` và `/uploads` sang FastAPI cổng 4000.
- Production: FastAPI phục vụ `frontend/dist` tại cổng 4000, cùng origin với API.
- Chỉ **một** backend được ghi database tại mỗi thời điểm (bản Node và bản Python đều có sweeper 60 giây).

## 4. Kiến trúc

```
Trình duyệt
  │  React SPA (HashRouter)
  │  fetch + Bearer JWT
  ▼
FastAPI /api/v1
  ├── routers/       26 router: auth, listings, orders, wallet, admin...
  ├── services/      escrow, mail, AI, upload, phân quyền...
  ├── models.py      SQLAlchemy model sinh từ DB thật
  └── serialize.py   chuyển model → JSON giống Prisma
  ▼
PostgreSQL 17 trên Supabase (dùng chung với bản Node)
  ├── bảng/cột giữ kiểu Prisma: "User", "createdAt"
  └── enum PostgreSQL: OrderStatus, ListingStatus...
```

Luồng request:

1. React gọi `/api/v1/...` kèm `Authorization: Bearer <JWT>` nếu đã đăng nhập.
2. FastAPI xác thực, kiểm tra quyền theo role, đọc/ghi qua SQLAlchemy.
3. Response JSON giữ đúng tên field và định dạng ngày giờ của bản Node.
4. Với production, request không phải `/api` hoặc `/uploads` được trả `index.html` để SPA xử lý route.

## 5. Cấu trúc thư mục

```
backend/
  app/
    main.py            create_app, CORS, handler lỗi, mount /uploads, phục vụ dist
    config.py          đọc .env
    db.py              engine/session
    models.py          36 model + 17 enum
    serialize.py       JSON datetime, model → dict
    routers/           26 router, đủ 143 endpoint
    services/          escrow, mail, AI, assistant_search, upload, admin_permissions
    limits.py          rate limit trong bộ nhớ
  alembic/             baseline schema
  tests/               125 test pytest
  scripts/             gen_models, seed, công cụ phụ
frontend/
  src/
    main.jsx           provider + HashRouter
    App.jsx            khai báo route
    Layout.jsx         header, footer, mobile nav, compare tray
    api.js             fetch wrapper, token, upload
    session.jsx        context đăng nhập
    categories.jsx     context danh mục
    compare.jsx        so sánh sản phẩm
    ui.jsx             icon, toast, modal, card, pagination, evidence
    pages/             20 file trang
    components/        Header, Footer
    styles.css         CSS gốc
    design.css         CSS bổ sung
  public/assets/       ảnh seed
docs/
  API.md               danh sách 143 endpoint
  PROJECT.md           tài liệu này
  TASKS.md             kế hoạch 4 người
```

## 6. Vai trò và quyền

| Vai trò | Cách có | Quyền chính |
|---|---|---|
| Khách | Không đăng nhập | Xem trang chủ, danh mục, tìm/lọc/sắp xếp, chi tiết tin, gian hàng, so sánh, trợ lý, đăng ký/đăng nhập/quên mật khẩu |
| `BUYER` | Tự động khi đăng ký | Toàn bộ quyền khách + giỏ hàng, đặt hàng, ví, đơn mua, trả giá, chat, thông báo, yêu thích, theo dõi tìm kiếm, đánh giá sau khi hoàn tất, trả hàng, báo cáo |
| `SELLER` | Bấm "Mở gian hàng" (API become-seller) | Quyền buyer + đăng/sửa/ẩn/xoá tin, boost tin, quản lý đơn bán, nhận trả giá, doanh thu, biểu đồ, phân tích đánh giá, trả lời đánh giá |
| `ADMIN_CONTENT` | Admin cấp role | Quản trị nội dung: duyệt/từ chối tin, báo cáo, khuyến mãi, banner, danh mục, người dùng, nhật ký, phân tích đánh giá |
| `ADMIN_FINANCE` | Admin cấp role | Quản trị tiền: tổng quan, biểu đồ, phí, giao dịch, yêu cầu rút, tranh chấp, trả hàng, đơn hàng, đối soát |
| Người được cấp `canManageRoles` | Cờ riêng trên User | Đổi role của người khác; chỉ ADMIN_FINANCE có cờ này mới được thao tác |

Một người có thể có nhiều role. `SELLER` vẫn mua hàng bình thường.

## 7. Chức năng và trạng thái

Ký hiệu: ✅ có và dùng được; ⚠️ có nhưng cần cấu hình hoặc còn giới hạn; ❌ chưa có.

### 7.1 Checklist yêu cầu

| # | Chức năng | Trạng thái | Ghi chú |
|---|---|---|---|
| 1 | Đăng ký + gửi email xác nhận | ⚠️ | Có OTP + link xác nhận. Dev ghi mail ra `.local/mail/`; production cần `RESEND_API_KEY` + domain |
| 2 | Đăng nhập | ✅ | Email + mật khẩu, JWT 7 ngày |
| 3 | Đăng xuất | ✅ | Thu hồi session hiện tại; có "đăng xuất mọi thiết bị" |
| 4 | Lấy lại mật khẩu | ✅ | OTP qua email, đổi mật khẩu, link reset |
| 5 | Xem chi tiết sản phẩm | ✅ | Ảnh, mô tả, thông số, người bán, đánh giá, tin liên quan |
| 6 | Quản lý giỏ hàng | ⚠️ | Thêm/xoá/xoá tất cả. Mỗi tin là 1 dòng, không có số lượng (schema cũ không có cột quantity) |
| 7 | Đặt hàng | ✅ | Tạo đơn, địa chỉ, COD/ví, cọc SafePay |
| 8 | Thanh toán trực tuyến | ⚠️ | Có ví nội bộ + nạp demo. Chưa tích hợp cổng thật (MoMo/VNPay/webhook) |
| 9 | Lịch sử mua hàng | ✅ | Đơn mua, đơn bán, chi tiết, timeline, trạng thái |
| 10 | Biểu đồ cột theo khoảng thời gian | ✅ | Admin tài chính và seller, chọn `from`/`to` |
| 11 | Biểu đồ tròn | ✅ | Admin: trạng thái đơn |
| 12 | Admin quản lý người dùng/sản phẩm/đơn hàng | ✅ | Khoá/mở, xác minh, role, duyệt tin, xem đơn |
| 13 | Seller quản lý sản phẩm/doanh thu/đơn hàng | ✅ | Dashboard, tin đăng, đơn bán, biểu đồ, ví |
| 14 | Đăng nhập bằng Google | ⚠️ | Code backend + frontend đã có; cần `GOOGLE_CLIENT_ID` và `VITE_GOOGLE_CLIENT_ID` |
| 15 | Cập nhật thông tin cá nhân | ⚠️ | Sửa tên/điện thoại/bio, thêm/xoá địa chỉ; chưa sửa địa chỉ |
| 16 | Cập nhật trạng thái đơn hàng | ✅ | Seller/buyer/admin theo đúng luồng trạng thái |
| 17 | Huỷ đơn + hoàn tiền | ✅ | Huỷ trước khi giao; escrow hoàn về ví buyer |
| 18 | Đánh giá sản phẩm đã mua | ✅ | Sau đơn COMPLETED, 1 đánh giá/đơn, seller trả lời |
| 19 | Báo cáo gian hàng/khách hàng | ❌ | Chỉ báo tin, mô tả tin, bình luận, tin nhắn, avatar; chưa có target SHOP/USER |
| 20 | Lọc sản phẩm nhiều tiêu chí | ✅ | Từ khoá, danh mục, giá, tình trạng, thành phố, giao nhận, miễn phí |
| 21 | Sắp xếp sản phẩm | ⚠️ | Giá tăng/giảm, mới nhất; chưa sắp xếp theo bán chạy/lượt xem |
| 22 | Tìm kiếm gian hàng | ✅ | `/shops/search`, phân trang |
| 23 | Sản phẩm gợi ý | ✅ | Trang chủ: theo danh mục đã lưu, fallback phổ biến |
| 24 | Chatbot AI tư vấn/tìm sản phẩm | ⚠️ | Có AI khi cấu hình `OPENAI_API_KEY`; không có thì tìm từ khoá (mode LOCAL) |
| 25 | Lịch sử giá sản phẩm | ✅ | API + hiển thị trong trang tin |
| 26 | Phân tích cảm xúc bình luận | ⚠️ | Có ở seller/admin (`/reviews/insights`), chưa hiển thị trên trang sản phẩm |
| 27 | Trang chủ: sản phẩm bán chạy | ❌ | Chưa có section và chưa có truy vấn theo số đơn hoàn tất |
| 28 | Trang chủ: sản phẩm mới nhất | ❌ | Có sort `newest` trong catalog, chưa có section riêng trên trang chủ |
| 29 | Trang chủ: sản phẩm xem nhiều nhất | ❌ | Trang chủ mặc định ưu tiên boost + mới, chưa có section "xem nhiều" |
| 30 | Danh sách sản phẩm gợi ý | ✅ | Section "Gợi ý cho bạn" |

### 7.2 Nhóm chức năng đã có

**Tài khoản**
Đăng ký, đăng nhập, đăng xuất, quên/đổi mật khẩu, xác nhận email, OTP, Google login (khi cấu hình), hồ sơ, địa chỉ, trở thành seller, xác minh danh tính ở mức quản trị.

**Mua sắm**
Trang chủ, danh mục, tìm kiếm, lọc, sắp xếp, chi tiết tin, ảnh, thông số, lịch sử giá, tin liên quan, yêu thích, so sánh tối đa 3 sản phẩm, gợi ý, trợ lý tìm đồ, theo dõi tìm kiếm, gian hàng + uy tín shop.

**Giao dịch**
Trả giá, giỏ hàng, đặt hàng, cọc SafePay, thanh toán phần còn lại, COD, huỷ đơn, hoàn tiền, timeline, chat, thông báo.

**Ví và tài chính**
Ví, nạp demo, rút tiền, ngân hàng, giao dịch, phí sàn, ký quỹ, giải ngân, hoàn tiền, đối soát.

**Sau bán**
Trả hàng, tranh chấp, bằng chứng ảnh, đánh giá, trả lời đánh giá, phân tích cảm xúc.

**Người bán**
Dashboard, doanh thu theo ngày, tin đăng, đăng/sửa tin, upload ảnh, boost, ẩn/xoá, đơn bán, trả giá, phân tích đánh giá.

**Quản trị**
Nội dung: duyệt tin, báo cáo, khuyến mãi, banner, người dùng, audit, phân tích đánh giá. CRUD danh mục có API nhưng chưa có tab trong admin UI.
Tài chính: tổng quan, biểu đồ cột/tròn, đơn hàng, giao dịch, phí, rút tiền, phân quyền, tranh chấp, trả hàng, audit.

## 8. Luồng nghiệp vụ chính

### 8.1 Đăng ký / đăng nhập

1. Đăng ký tạo user `PENDING_VERIFICATION`, gửi OTP + link xác nhận.
2. Xác nhận email → tài khoản hoạt động, nhận role `BUYER`.
3. Đăng nhập trả JWT chứa `sub` (string), `sessionVersion`. Đổi mật khẩu hoặc logout-all tăng `sessionVersion` → token cũ mất hiệu lực.

### 8.2 Tin đăng

`DRAFT → PENDING_REVIEW → ACTIVE → RESERVED → SOLD_OUT`

- Seller đăng tin → `PENDING_REVIEW`.
- Admin nội dung duyệt → `ACTIVE` hoặc từ chối kèm lý do.
- Có đơn → `RESERVED`; hoàn tất → `SOLD_OUT`.
- Seller có thể ẩn/hiện, boost, xoá mềm.

### 8.3 Đơn hàng và ký quỹ

`PENDING_DEPOSIT → DEPOSITED → CONFIRMED → SHIPPING → DELIVERED → COMPLETED`

- Buyer tạo đơn, chọn COD hoặc cọc qua ví.
- Seller xác nhận, gửi hàng, đánh dấu đã giao.
- Buyer xác nhận đã nhận → escrow giải ngân cho seller, trừ phí sàn.
- Huỷ trước khi giao → hoàn escrow về ví buyer.
- COD: seller xác nhận đã thu tiền trước khi buyer hoàn tất.
- Đơn `PENDING_DEPOSIT` quá 30 phút bị sweeper tự huỷ.

### 8.4 Ví và rút tiền

- Nạp tiền (hiện là demo, cộng ngay).
- Buyer cọc/thanh toán từ ví.
- Seller nhận tiền vào ví sau khi đơn hoàn tất.
- Tạo yêu cầu rút → admin tài chính duyệt → chuyển khoản → đánh dấu PAID/FAILED/REJECTED.

### 8.5 Trả hàng / tranh chấp

- Buyer yêu cầu trả hàng trong 7 ngày sau khi giao.
- Seller duyệt/từ chối; buyer gửi trả; seller nhận hàng; admin hoặc seller hoàn tiền.
- Tranh chấp do buyer mở, admin tài chính xử lý và quyết định hoàn tiền.

### 8.6 Đánh giá

- Chỉ đơn `COMPLETED`, mỗi đơn một đánh giá.
- Buyer chấm sao + nhận xét; seller trả lời.
- `/reviews/insights` tổng hợp cảm xúc bằng AI nếu bật, không thì dùng từ khoá cục bộ.

## 9. Dữ liệu và quy ước

- Bảng/cột giữ tên Prisma: `"User"`, `"createdAt"`, `"listingId"`.
- Tiền là **số nguyên VND**, không dùng số thực.
- Thời gian lưu UTC dạng naive trong DB; JSON trả `Z` kèm 3 chữ số mili giây.
- Enum PostgreSQL map tường minh trong SQLAlchemy.
- Model sinh tự động từ DB thật, không có relationship/ForeignKey; phải `flush()` trước khi insert bản ghi con.
- `User.updatedAt` và nhiều bảng có `updatedAt` kiểu Prisma `@updatedAt`: ứng dụng phải tự đặt, DB không tự cập nhật.
- Xoá cascade do database xử lý.
- Ảnh sản phẩm: `uploads/`; ảnh bằng chứng: `.local/evidence/` và phải có quyền mới đọc.

## 10. API

- Base URL: `/api/v1`.
- Danh sách đầy đủ: [`docs/API.md`](./API.md) (143 endpoint + `/health`).
- Xác thực: `Authorization: Bearer <JWT>`.
- Lỗi: `{"message": "..."}`; 401 sai token, 403 sai quyền, 404 sai đường dẫn, 429 quá giới hạn.
- Rate limit: assistant 10 lượt/phút/IP; một số hành động nhạy cảm dùng `ActionQuota`.
- Ngày giờ: ISO 8601 UTC, ví dụ `2026-10-20T08:00:00.000Z`.

## 11. Cấu hình

Sao chép `.env.example` thành `.env` trong `backend/`.

| Biến | Bắt buộc | Ý nghĩa |
|---|---|---|
| `DATABASE_URL` | Có | PostgreSQL trên Supabase (session pooler), xem `docs/DATABASE.md` |
| `JWT_SECRET` | Có | Phải trùng bản Node nếu muốn dùng chung token |
| `JWT_EXPIRES_IN` | Không | Mặc định `7d` |
| `PORT` | Không | Mặc định 4000 |
| `NODE_ENV` | Không | `development` ghi mail ra file; `production` gửi thật |
| `CLIENT_URL` | Không | Origin frontend dev |
| `APP_URL` | Không | URL công khai của backend |
| `RESEND_API_KEY`, `MAIL_FROM` | Không | Gửi email thật |
| `GOOGLE_CLIENT_ID` | Không | Google login backend; phải khớp frontend |
| `OPENAI_API_KEY`, `OPENAI_MODEL` | Không | Trợ lý AI + phân tích cảm xúc |
| `AI_REVIEW_ANALYSIS` | Không | Bật phân tích cảm xúc bằng AI |

Frontend dev dùng `VITE_GOOGLE_CLIENT_ID` (tạo file `frontend/.env`).

Không commit `.env`, `uploads/`, `.local/`.

## 12. Chạy và kiểm thử

```bash
# Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env
uvicorn app.main:app --reload --port 4000

# Frontend dev
cd frontend
npm install
npm run dev        # http://localhost:5173

# Build production, FastAPI phục vụ tại http://localhost:4000
cd frontend && npm run build
```

```bash
# Test backend
cd backend
PYTHONPATH=. .venv/bin/pytest tests/ -q -p no:warnings
```

Đã kiểm thử:

- 125 test pytest pass.
- Đối chiếu JSON với Express: 70/72 tổ hợp đọc khớp; 2 ca lệch là lỗi sẵn có của bản Node.
- Chrome headless: 35 route React không lỗi console.
- Luồng tiền qua UI: giỏ → đơn → nạp ví → cọc → seller xác nhận/gửi → buyer nhận/hoàn tất → mở đánh giá.
- Chat hai chiều, đăng tin có upload ảnh, admin duyệt tin.

## 13. Bảo mật

- Mật khẩu băm bcrypt; JWT có `sessionVersion` để thu hồi phiên.
- Phân quyền theo role ở từng router; kiểm tra chủ sở hữu ở tầng nghiệp vụ.
- Ảnh bằng chứng không public, đọc qua API có xác thực.
- Upload giới hạn MIME và dung lượng; tên file sinh bằng UUID.
- Rate limit cho trợ lý và một số hành động nhạy cảm.
- CORS hiện mở rộng giống bản Node (`allow_origin_regex=".*"`); production nên siết theo origin thật.
- Không trả chi tiết lỗi nội bộ ra client.

Lưu ý: token lưu `localStorage` giống bản cũ; nếu cần chống XSS mạnh hơn, chuyển sang cookie HttpOnly + CSRF.

## 14. Hạn chế đã biết

- Thanh toán trực tuyến mới ở mức demo/ví nội bộ.
- Google login và email thật phụ thuộc biến môi trường.
- Chatbot AI và phân tích cảm xúc cần OpenAI key; thiếu key thì dùng fallback cục bộ.
- Giỏ hàng không có số lượng; khuyến mãi chỉ áp cho giỏ một món vì mỗi tin tạo một đơn riêng.
- Chưa sửa địa chỉ, chỉ thêm/xoá.
- Chưa báo cáo được shop/người dùng.
- Chưa có section bán chạy/mới nhất/xem nhiều trên trang chủ.
- Chưa sắp xếp theo bán chạy/lượt xem.
- API CRUD danh mục đã có nhưng admin UI chưa có màn hình quản lý danh mục.
- Bundle JS khoảng 705 KB, chưa code-split.
- Chưa có bộ E2E tự động trong repo và CI.
- URL ảnh seed chứa `localhost:4000`; khi deploy domain khác cần chuẩn hoá.
- Supabase free tier có thể tạm dừng project khi ít hoạt động; cần resume trên dashboard.

## 15. Việc còn thiếu

Xem kế hoạch chi tiết và phân công 4 người tại [`docs/TASKS.md`](./TASKS.md).
