"""API Nola2Hand — FastAPI, giữ nguyên hình dạng JSON của bản Node."""
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from .config import settings
from .errors import ApiError, api_error_handler, integrity_handler, unhandled_handler, validation_handler


def create_app() -> FastAPI:
    app = FastAPI(title="Nola2Hand API", docs_url=None, redoc_url=None)

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

    @app.exception_handler(404)
    async def not_found(_request: Request, _exc: Exception) -> JSONResponse:
        # Giống hệt thông báo của bản Node (src/app.js:75)
        return JSONResponse(
            status_code=404,
            content={"message": "Endpoint không tồn tại. Kiểm tra lại đường dẫn, mọi API đều bắt đầu bằng /api/v1/..."},
        )

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.port, reload=True)
