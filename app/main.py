from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version=settings.app_version)
    register_exception_handlers(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def reject_oversized_requests(request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                request_size = int(content_length)
            except ValueError:
                request_size = 0

            if request_size > settings.max_request_size_bytes:
                return JSONResponse(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    content={
                        "detail": "Upload request is too large.",
                        "code": "request_too_large",
                        "max_request_size_bytes": settings.max_request_size_bytes,
                        "received_size_bytes": request_size,
                    },
                )

        return await call_next(request)

    @app.get("/")
    async def root() -> dict[str, bool | str]:
        return {
            "success": True,
            "message": "Bulk Update AI API is running successfully",
        }

    app.include_router(router)
    return app


app = create_app()
