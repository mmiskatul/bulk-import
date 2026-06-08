from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class BulkUpdateAPIError(RuntimeError):
    def __init__(self, message: str, *, code: str = "bulk_update_error", status_code: int = 500) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(BulkUpdateAPIError)
    async def bulk_update_error_handler(request: Request, exc: BulkUpdateAPIError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "detail": exc.message,
                "code": exc.code,
                "path": request.url.path,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "detail": "Request validation failed.",
                "code": "validation_error",
                "path": request.url.path,
                "errors": exc.errors(),
            },
        )

    @app.exception_handler(HTTPException)
    async def http_error_handler(request: Request, exc: HTTPException) -> JSONResponse:
        detail = exc.detail
        code = "http_error"
        if isinstance(detail, dict):
            code = str(detail.get("code") or code)

        return JSONResponse(
            status_code=exc.status_code,
            content={
                "detail": detail,
                "code": code,
                "path": request.url.path,
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        del exc
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Bulk update service failed unexpectedly.",
                "code": "internal_error",
                "path": request.url.path,
            },
        )
