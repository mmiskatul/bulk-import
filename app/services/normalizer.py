from __future__ import annotations

import json
import re
from typing import Any

from openai import AsyncOpenAI

from app.core.config import get_settings
from app.schemas import BulkUpdateItem, ParsedFile


FIELD_ALIASES = {
    "title": ("title", "name", "product", "product name", "item name", "item"),
    "stock": ("stock", "qty", "quantity", "inventory", "available"),
    "price": ("price", "amount", "sale price", "selling price", "cost"),
    "brand": ("brand", "vendor", "manufacturer"),
    "description": ("description", "body", "details", "summary"),
    "color": ("color", "colour", "variant color", "variant colour"),
    "size": ("size", "variant size", "option size"),
    "imageUrl": ("imageurl", "image url", "image", "image_url", "photo", "photo url", "thumbnail", "thumbnail url"),
}


def _field(row: dict[str, str], name: str) -> str:
    lowered = {key.strip().lower(): value for key, value in row.items()}
    for alias in FIELD_ALIASES[name]:
        value = lowered.get(alias, "")
        if value:
            return value
    return ""


def _int(value: str) -> int:
    match = re.search(r"\d+", value.replace(",", ""))
    return int(match.group(0)) if match else 0


def _float(value: str) -> float:
    match = re.search(r"\d+(?:\.\d+)?", value.replace(",", ""))
    return float(match.group(0)) if match else 0.0


def _nullable(value: str) -> str | None:
    return value if value else None


def mark_duplicates(items: list[BulkUpdateItem]) -> list[BulkUpdateItem]:
    seen: set[str] = set()
    for item in items:
        key = item.title.strip().lower()
        if key and key in seen:
            item.status = "needs_review"
            item.issues = [*(item.issues or []), "duplicate_title"]
        elif item.issues:
            item.status = "needs_review"
        seen.add(key)
    return items


def deterministic_normalize(parsed_files: list[ParsedFile], marketplace: str) -> list[BulkUpdateItem]:
    del marketplace
    items: list[BulkUpdateItem] = []
    for parsed in parsed_files:
        if not parsed.rows:
            title = parsed.filename.rsplit(".", 1)[0].replace("-", " ").replace("_", " ").strip()
            items.append(
                BulkUpdateItem(
                    title=title or parsed.filename,
                    price=None,
                    stock=0,
                    description=f"{parsed.source_type.upper()} upload requires product detail review.",
                    color=None,
                    size=None,
                    brand="",
                    imageUrl=parsed.filename if parsed.source_type == "image" else None,
                    status="needs_review",
                    issues=["needs_ai_review", "missing_price"],
                )
            )
            continue

        for index, row in enumerate(parsed.rows):
            title = _field(row, "title") or f"Imported product {index + 1}"
            raw_price = _field(row, "price")
            price = _float(raw_price) if raw_price else None
            issues: list[str] = []
            if not _field(row, "title"):
                issues.append("missing_title")
            if price is None:
                issues.append("missing_price")

            item = BulkUpdateItem(
                title=title,
                price=price,
                stock=_int(_field(row, "stock")),
                description=_field(row, "description"),
                color=_nullable(_field(row, "color")),
                size=_nullable(_field(row, "size")),
                brand=_field(row, "brand"),
                imageUrl=_nullable(_field(row, "imageUrl")),
                status="needs_review" if issues else "clean",
                issues=issues or None,
            )
            items.append(item)
    return mark_duplicates(items)


def _schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "title": {"type": "string"},
                        "price": {"anyOf": [{"type": "number", "minimum": 0}, {"type": "null"}]},
                        "stock": {"type": "integer", "minimum": 0},
                        "description": {"type": "string"},
                        "color": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                        "size": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                        "brand": {"type": "string"},
                        "imageUrl": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                        "status": {"type": "string", "enum": ["clean", "needs_review"]},
                        "issues": {"anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}]},
                    },
                    "required": [
                        "title",
                        "price",
                        "stock",
                        "description",
                        "color",
                        "size",
                        "brand",
                        "imageUrl",
                        "status",
                        "issues",
                    ],
                },
            }
        },
        "required": ["items"],
    }


async def ai_normalize(parsed_files: list[ParsedFile], marketplace: str, fallback: list[BulkUpdateItem]) -> list[BulkUpdateItem]:
    settings = get_settings()
    if not settings.openai_enabled or not settings.openai_api_key:
        return fallback

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    response = await client.responses.create(
        model=settings.openai_model,
        input=[
            {
                "role": "system",
                "content": (
                    "Normalize ecommerce bulk import data into product items. "
                    "Use source rows as truth, infer fields only when clear, and mark uncertain items as needs_review."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "marketplace": marketplace,
                        "files": [file.model_dump() for file in parsed_files],
                        "fallback": [item.model_dump() for item in fallback],
                    },
                    ensure_ascii=True,
                ),
            },
        ],
        text={"format": {"type": "json_schema", "name": "bulk_update_items", "schema": _schema(), "strict": True}},
    )

    parsed = json.loads(response.output_text or "{}")
    return mark_duplicates([BulkUpdateItem.model_validate(item) for item in parsed.get("items", [])])


async def normalize(parsed_files: list[ParsedFile], marketplace: str, use_ai: bool) -> list[BulkUpdateItem]:
    fallback = deterministic_normalize(parsed_files, marketplace)
    items = fallback
    if use_ai:
        try:
            items = await ai_normalize(parsed_files, marketplace, fallback)
        except Exception:
            items = fallback

    return items
