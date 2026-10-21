# Database trên Supabase

Database dùng chung của nhóm đã được chuyển từ PostgreSQL local sang **Supabase**.

## 1. Thông tin kết nối

| Mục | Giá trị |
|---|---|
| Project | `nola2hand` |
| Project ref | `owhqybaqhunrhmnfltwt` |
| Region | `ap-southeast-1` (Singapore) |
| PostgreSQL | 17.11 |
| Dashboard | https://supabase.com/dashboard/project/owhqybaqhunrhmnfltwt |
| Host | `aws-0-ap-southeast-1.pooler.supabase.com` |
| Port | `5432` (session pooler) |
| Database | `postgres` |
| User | `postgres.owhqybaqhunrhmnfltwt` |

Mẫu `DATABASE_URL`:

```text
postgresql://postgres.owhqybaqhunrhmnfltwt:<MAT_KHAU>@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres?sslmode=require
```

- Dùng **session pooler cổng 5432** như trên. Không dùng transaction pooler `6543` cho Alembic/migration.
- Không dùng host direct `db.owhqybaqhunrhmnfltwt.supabase.co` nếu mạng của bạn không có IPv6.
- Mật khẩu **không nằm trong repo**. Người tạo project giữ trong `.local/SUPABASE-CONNECTION.txt` và gửi riêng qua password manager/chat riêng.
- Nếu quên mật khẩu: Supabase Dashboard → **Project Settings → Database → Reset database password**, sau đó cập nhật lại `backend/.env` và gửi lại cho nhóm.

## 2. Đồng nghiệp vào làm cùng

```bash
git clone https://github.com/H-thanh0603/nola2hand-py.git
cd nola2hand-py
cp .env.example backend/.env
# Mở backend/.env, thay DATABASE_URL bằng chuỗi được gửi riêng

cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 4000
```

Kiểm tra:

```bash
curl http://127.0.0.1:4000/health
curl http://127.0.0.1:4000/api/v1/listings?limit=1
```

Không commit `backend/.env`; file này đã nằm trong `.gitignore`.

## 3. Quy tắc an toàn

- Chỉ **một** backend được ghi database tại mỗi thời điểm. Bản Node và bản Python đều có sweeper tự huỷ đơn quá hạn.
- Không cấp lại quyền cho `anon` hoặc `authenticated`. Supabase Data API đã bị chặn ở tầng quyền bảng; chỉ backend dùng role `postgres` được đọc/ghi.
- RLS đã bật trên toàn bộ bảng `public` để phòng thủ nhiều lớp. Backend chạy bằng role `postgres` nên vẫn truy cập được.
- Không đưa mật khẩu, `service_role` key hay connection string vào mã nguồn, ảnh chụp, issue, PR.
- Free tier có thể tạm dừng project khi ít hoạt động. Nếu API báo lỗi kết nối, mở dashboard để resume project.

## 4. Backup và khôi phục

Tạo bản dump từ Supabase:

```bash
cd backend
set -a; . .env; set +a
pg_dump "$DATABASE_URL" --no-owner --no-privileges \
  --format=custom --file=../.local/nola2hand-supabase.dump
```

Khôi phục vào một database trống:

```bash
pg_restore --no-owner --no-privileges --single-transaction \
  --dbname="$DATABASE_URL" ../.local/nola2hand-supabase.dump
```

File `.dump` chứa dữ liệu thật (email, số điện thoại, hash mật khẩu), không commit và không gửi công khai.

## 5. Dữ liệu hiện tại

Tại thời điểm chuyển sang Supabase:

- 38 bảng, 17 enum.
- 16 user, 22 tin đăng, 17 đơn, 41 giao dịch ví, 124 thông báo.
- Đã đối chiếu số dòng toàn bộ bảng giữa local và Supabase: khớp 100%.

## 6. Migration

- Chạy Alembic bằng `DATABASE_URL` trên (session pooler).
- Trước khi migration: dump backup.
- Migration chỉ **thêm** bảng/cột/index; không đổi/xoá cột cũ vì bản Node có thể còn dùng.
- Sau migration, kiểm tra lại quyền: bảng mới không được tự cấp quyền cho `anon`/`authenticated`.
