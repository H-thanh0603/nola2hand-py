# Nola2Hand (Python + React)

Bản viết lại của sàn thương mại điện tử đồ cũ **Nola2Hand** bằng **FastAPI** (backend) và **React** (frontend).

- Bản gốc đang chạy được (Node.js + Express + Prisma + frontend thuần): [H-thanh0603/nola2hand-ft](https://github.com/H-thanh0603/nola2hand-ft)
- Dùng chung **một database PostgreSQL** với bản gốc. Không cần nạp lại dữ liệu.
- Mục tiêu: giữ nguyên toàn bộ 143 endpoint cũ để frontend có thể chuyển sang React từng bước.

## Trạng thái

Đang ở giai đoạn dựng khung backend. Kế hoạch chi tiết theo từng phase nằm trong `PLAN.md` (file cục bộ, không commit).

## Cấu trúc

```
backend/    FastAPI: router, model SQLAlchemy, service nghiệp vụ, migration Alembic
frontend/   React + Vite + React Router
docs/       Tài liệu API và thiết kế
```

## Chạy thử

```bash
# Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env    # rồi sửa DATABASE_URL, JWT_SECRET
uvicorn app.main:app --reload --port 4000

# Frontend
cd frontend
npm install
npm run dev                # http://localhost:5173
```

## Lưu ý quan trọng

Chỉ chạy **một** backend chạm database tại mỗi thời điểm. Bản Node có vòng lặp 60 giây tự huỷ đơn quá hạn
(`nola2hand-ft/src/app.js:79`); chạy song song hai backend sẽ khiến cùng một đơn bị xử lý hai lần.
