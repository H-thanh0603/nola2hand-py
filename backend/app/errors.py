"""Lỗi trả về — giữ nguyên thông báo của bản Node (src/middleware.js)."""
import logging

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError


class ApiError(Exception):
    """Lỗi nghiệp vụ có chủ đích — tương đương err.status bên Node."""

    def __init__(self, status: int, message: str, details: list | None = None, headers: dict | None = None):
        self.status = status
        self.message = message
        self.details = details
        self.headers = headers
        super().__init__(message)


def _body(message: str, details=None) -> dict:
    return {"message": message, "details": details} if details else {"message": message}


async def api_error_handler(_request: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse(status_code=exc.status, content=_body(exc.message, exc.details), headers=exc.headers)


async def validation_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    # Giống middleware.validate của bản Node: 400 + danh sách { field, message }
    details = [
        {"field": ".".join(str(p) for p in err["loc"][1:]), "message": err["msg"]}
        for err in exc.errors()
    ]
    return JSONResponse(status_code=400, content=_body("Dữ liệu không hợp lệ", details))


async def integrity_handler(_request: Request, exc: IntegrityError) -> JSONResponse:
    # Prisma P2002 → 409 trùng dữ liệu
    if "unique" in str(exc.orig).lower() or "duplicate key" in str(exc.orig).lower():
        return JSONResponse(status_code=409, content=_body("Dữ liệu đã tồn tại (trùng lặp)"))
    return JSONResponse(status_code=500, content=_body("Lỗi hệ thống, vui lòng thử lại sau"))


async def unhandled_handler(_request: Request, exc: Exception) -> JSONResponse:
    # Bản Node trả err.message cho lỗi không lường trước (src/middleware.js:62).
    # Giữ đúng như vậy để hành vi khớp; thông báo lỗi ghi ra log.
    logging.exception("Lỗi không lường trước")
    return JSONResponse(status_code=500, content=_body(str(exc) or "Lỗi hệ thống, vui lòng thử lại sau"))
