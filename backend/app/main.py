"""API Nola2Hand — FastAPI, giữ nguyên hình dạng JSON của bản Node."""
import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.exc import IntegrityError

from .config import settings
from .db import SessionLocal, get_db
from .errors import ApiError, api_error_handler, integrity_handler, unhandled_handler, validation_handler
from .routers import admin_users as admin_users_router
from .routers import audit as audit_router
from .routers import auth as auth_router
from .routers import assistant as assistant_router
from .routers import banners as banners_router
from .routers import cart as cart_router
from .routers import chat as chat_router
from .routers import categories as categories_router
from .routers import disputes as disputes_router
from .routers import escrow as escrow_router
from .routers import finance as finance_router
from .routers import listings as listings_router
from .routers import notifications as notifications_router
from .routers import offers as offers_router
from .routers import orders as orders_router
from .routers import posts as posts_router
from .routers import promos as promos_router
from .routers import reports as reports_router
from .routers import returns as returns_router
from .routers import reviews as reviews_router
from .routers import saved_searches as saved_searches_router
from .routers import seller as seller_router
from .routers import upload as upload_router
from .routers import reviews as reviews_router
from .routers import shops as shops_router
from .routers import users as users_router
from .routers import wallet as wallet_router
from .routers.upload import UPLOAD_DIR
from .services.reservations import expire_reservations

logger = logging.getLogger("uvicorn.error")


def _expire_reservations() -> None:
    with SessionLocal() as db:
        expire_reservations(db)


async def _reservation_loop() -> None:
    """Như setInterval 60 giây của bản Node (src/app.js:79)."""
    while True:
        await asyncio.sleep(60)
        try:
            await asyncio.to_thread(_expire_reservations)
        except Exception:  # một lần lỗi DB không được làm chết bộ dọn
            logger.exception("Reservation cleanup")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    task = asyncio.create_task(_reservation_loop())
    yield
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task


def create_app() -> FastAPI:
    app = FastAPI(title="Nola2Hand API", docs_url=None, redoc_url=None, lifespan=lifespan)

    app.add_exception_handler(ApiError, api_error_handler)
    app.add_exception_handler(RequestValidationError, validation_handler)
    app.add_exception_handler(IntegrityError, integrity_handler)
    app.add_exception_handler(Exception, unhandled_handler)

    # Bản Node để origin: true (cho mọi origin) nên frontend React ở cổng 5173 gọi được.
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=".*",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health():
        # Bản Node trả new Date() → JSON dạng 2026-10-19T14:12:34.567Z
        now = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        return {"ok": True, "service": "nola2hand-backend", "time": now}

    app.include_router(auth_router.router, prefix="/api/v1/auth")
    app.include_router(users_router.router, prefix="/api/v1/users")
    app.include_router(admin_users_router.router, prefix="/api/v1/admin/users")
    app.include_router(categories_router.router, prefix="/api/v1/categories")
    app.include_router(listings_router.router, prefix="/api/v1/listings")
    app.include_router(posts_router.router, prefix="/api/v1/posts")
    app.include_router(shops_router.router, prefix="/api/v1/shops")
    app.include_router(offers_router.router, prefix="/api/v1/offers")
    app.include_router(orders_router.router, prefix="/api/v1/orders")
    app.include_router(cart_router.router, prefix="/api/v1/cart")
    app.include_router(escrow_router.router, prefix="/api/v1/escrow")
    app.include_router(wallet_router.router, prefix="/api/v1/wallet")
    app.include_router(finance_router.router, prefix="/api/v1/admin/finance")
    app.include_router(returns_router.router, prefix="/api/v1/returns")
    app.include_router(disputes_router.router, prefix="/api/v1/disputes")
    app.include_router(reports_router.router, prefix="/api/v1/reports")
    app.include_router(reviews_router.router, prefix="/api/v1/reviews")
    app.include_router(chat_router.router, prefix="/api/v1/chat")
    app.include_router(notifications_router.router, prefix="/api/v1/notifications")
    app.include_router(saved_searches_router.router, prefix="/api/v1/saved-searches")
    app.include_router(assistant_router.router, prefix="/api/v1/assistant")
    app.include_router(audit_router.router, prefix="/api/v1/admin/audit")
    app.include_router(seller_router.router, prefix="/api/v1/seller")
    app.include_router(upload_router.router, prefix="/api/v1/upload")
    app.include_router(promos_router.router, prefix="/api/v1/promos")
    app.include_router(banners_router.router, prefix="/api/v1/banners")

    # Ảnh sản phẩm công khai — như app.use('/uploads', express.static(...)) của bản Node.
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

    class PublicImageHeaders(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            response = await call_next(request)
            if request.url.path.startswith("/uploads/"):
                response.headers["X-Content-Type-Options"] = "nosniff"
            return response

    app.add_middleware(PublicImageHeaders)

    dist_dir = Path(__file__).resolve().parents[2] / "frontend" / "dist"

    async def not_found_body() -> JSONResponse:
        # Giống hệt thông báo của bản Node (src/app.js:75)
        return JSONResponse(
            status_code=404,
            content={"message": "Endpoint không tồn tại. Kiểm tra lại đường dẫn, mọi API đều bắt đầu bằng /api/v1/..."},
        )

    @app.exception_handler(404)
    async def not_found(request: Request, _exc: Exception) -> JSONResponse:
        # Bản build React: chỉ trả file tĩnh cho đường dẫn không phải API/ảnh.
        path = request.url.path
        if request.method == "GET" and not path.startswith(("/api/", "/uploads/")) and dist_dir.is_dir():
            target = (dist_dir / path.lstrip("/")).resolve()
            if target.is_file() and target.is_relative_to(dist_dir.resolve()):
                return FileResponse(target)
            return FileResponse(dist_dir / "index.html")
        return await not_found_body()

    @app.exception_handler(405)
    async def method_not_allowed(_request: Request, _exc: Exception) -> JSONResponse:
        # Express không có 405: sai method cũng rơi vào 404 của app.js.
        return await not_found_body()

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.port, reload=True)
