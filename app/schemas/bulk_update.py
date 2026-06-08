from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_serializer


ImportStatus = Literal["clean", "needs_review"]
SourceType = Literal["csv", "excel", "pdf", "image", "unknown"]


class ParsedFile(BaseModel):
    filename: str
    content_type: str
    source_type: SourceType
    rows: list[dict[str, str]] = Field(default_factory=list)
    text: str = ""


class BulkUpdateItem(BaseModel):
    title: str
    price: float | None = Field(default=None, ge=0)
    stock: int = Field(default=0, ge=0)
    description: str = ""
    color: str | None = None
    size: str | None = None
    brand: str = ""
    imageUrl: str | None = None
    status: ImportStatus = "needs_review"
    issues: list[str] | None = None

    @model_serializer(mode="wrap")
    def serialize_without_empty_issues(self, handler):
        data = handler(self)
        if data.get("issues") is None:
            data.pop("issues", None)
        return data
