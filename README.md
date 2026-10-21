# Nola2Hand (Python + React)

Bản viết lại của sàn thương mại điện tử đồ cũ **Nola2Hand** bằng **FastAPI** (backend) và **React** (frontend).

- Bản gốc đang chạy được (Node.js + Express + Prisma + frontend thuần): [H-thanh0603/nola2hand-ft](https://github.com/H-thanh0603/nola2hand-ft)
- Dùng chung **một database PostgreSQL trên Supabase** với bản gốc. Không cần nạp lại dữ liệu; xem [`docs/DATABASE.md`](docs/DATABASE.md).
- Mục tiêu: giữ nguyên toàn bộ 143 endpoint cũ để frontend có thể chuyển sang React từng bước.

## Trạng thái

- Backend FastAPI: đủ **143/143 endpoint** của bản Express, giữ nguyên đường dẫn và dạng JSON.
- Frontend React: đủ màn hình mua sắm, tài khoản, ví/đơn/ký quỹ, kênh người bán và quản trị.
- Đã đối chiếu JSON hai backend trên cùng database (70/72 ca khớp; 2 ca còn lại là lỗi sẵn có của bản Node)
  và chạy thử luồng tiền + quản trị qua giao diện React.

## Cấu trúc

```
backend/    FastAPI: router, model SQLAlchemy, service nghiệp vụ, migration Alembic
frontend/   React + Vite + React Router; bản build nằm ở `frontend/dist`
docs/       `PROJECT.md` (tổng quan), `API.md` (endpoint), `DATABASE.md` (Supabase), `TASKS.md` (kế hoạch), `KE-HOACH-TASK-4-NGUOI.xlsx` (bản Excel giao việc)
```

## Chạy thử

```bash
# Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env    # rồi sửa DATABASE_URL (Supabase), JWT_SECRET
uvicorn app.main:app --reload --port 4000

# Frontend (dev, proxy /api + /uploads sang cổng 4000)
cd frontend
npm install
npm run dev                # http://localhost:5173

# Bản build: backend tự phục vụ frontend/dist tại http://localhost:4000/
cd frontend && npm run build
```

## Database dùng chung

Database nằm trên Supabase. Thông tin kết nối và cách vào làm cùng: [`docs/DATABASE.md`](docs/DATABASE.md).
Connection string gửi riêng, không commit `backend/.env`.

## Lưu ý quan trọng

Chỉ chạy **một** backend chạm database tại mỗi thời điểm. Bản Node có vòng lặp 60 giây tự huỷ đơn quá hạn
(`nola2hand-ft/src/app.js:79`); chạy song song hai backend sẽ khiến cùng một đơn bị xử lý hai lần.
