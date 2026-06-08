from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.core.config import get_settings
from app.graphs.normalization_graph import run_bulk_update_graph
from app.schemas import BulkUpdateItem
from app.services.parser import parse_upload

router = APIRouter()


@router.get("/")
async def root() -> dict[str, bool | str]:
    return {
        "success": True,
        "message": "Bulk Import AI API is running successfully",
    }


@router.get("/health")
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/bulk-import", response_model=list[BulkUpdateItem], status_code=status.HTTP_200_OK)
async def bulk_import(
    file: UploadFile | None = File(default=None),
) -> list[BulkUpdateItem]:
    settings = get_settings()
    if file is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "Please upload a CSV, Excel, PDF, or image file.",
                "code": "missing_upload_file",
            },
        )

    parsed_files = [await parse_upload(file, settings.max_upload_size_bytes)]
    return await run_bulk_update_graph(parsed_files, marketplace="auto", use_ai=settings.openai_enabled)
