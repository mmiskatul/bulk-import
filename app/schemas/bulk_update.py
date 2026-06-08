from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


Marketplace = Literal["amazon", "ebay", "tiktok", "shopify", "unknown"]
ImportStatus = Literal["new", "duplicate", "needs_review"]
SourceType = Literal["csv", "excel", "pdf", "image", "unknown"]


class ParsedFile(BaseModel):
    filename: str
    content_type: str
    source_type: SourceType
    rows: list[dict[str, str]] = Field(default_factory=list)
    text: str = ""


class BulkUpdateItem(BaseModel):
    id: str
    source_file: str
    marketplace: Marketplace = "unknown"
    status: ImportStatus = "needs_review"
    title: str
    sku: str = ""
    asin: str = ""
    barcode: str = ""
    stock: int = Field(default=0, ge=0)
    price: float = Field(default=0.0, ge=0.0)
    currency: str = "USD"
    category: str = ""
    brand: str = ""
    description: str = ""
    image_filename: str = ""
    normalized: dict[str, str | int | float | list[str]] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class BulkUpdateSummary(BaseModel):
    files_received: int
    rows_detected: int
    items_generated: int
    duplicates: int
    needs_review: int


class BulkUpdateResponse(BaseModel):
    summary: BulkUpdateSummary
    items: list[BulkUpdateItem]


class BulkUpdateValidateRequest(BaseModel):
    items: list[BulkUpdateItem]
