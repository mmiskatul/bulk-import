from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, File, Form, UploadFile, status

from app.core.config import get_settings
from app.graphs.normalization_graph import run_bulk_update_graph
from app.schemas import BulkUpdateResponse, BulkUpdateValidateRequest
from app.services.normalizer import validate
from app.services.parser import parse_upload

router = APIRouter(prefix="/api")


@router.get("/")
async def root() -> dict[str, bool | str]:
    return {
        "success": True,
        "message": "Bulk Update AI API is running successfully",
    }


@router.get("/health")
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/bulk-update/normalize", response_model=BulkUpdateResponse, status_code=status.HTTP_200_OK)
async def normalize_bulk_update(
    files: list[UploadFile] = File(...),
    marketplace: Literal["auto", "amazon", "ebay", "tiktok", "shopify"] = Form("auto"),
    use_ai: bool = Form(True),
) -> BulkUpdateResponse:
    settings = get_settings()
    parsed_files = [await parse_upload(file, settings.max_upload_size_bytes) for file in files]
    return await run_bulk_update_graph(parsed_files, marketplace=marketplace, use_ai=use_ai)


@router.post("/bulk-update/validate", response_model=BulkUpdateResponse, status_code=status.HTTP_200_OK)
async def validate_bulk_update(payload: BulkUpdateValidateRequest) -> BulkUpdateResponse:
    return validate(payload.items)
