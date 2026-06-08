from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from openai import AsyncOpenAI

from app.core.config import get_settings
from app.schemas import BulkUpdateItem, ParsedFile


FIELD_ALIASES = {
    "title": ("title", "name", "product", "product name", "item name", "item"),
    "sku": ("sku", "seller sku", "merchant sku", "item sku"),
    "asin": ("asin", "amazon asin"),
    "barcode": ("barcode", "upc", "ean", "gtin"),
    "stock": ("stock", "qty", "quantity", "inventory", "available"),
    "price": ("price", "amount", "sale price", "selling price", "cost"),
    "category": ("category", "product category", "type", "product type"),
    "brand": ("brand", "vendor", "manufacturer"),
    "description": ("description", "body", "details", "summary"),
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


def _marketplace(filename: str, requested: str) -> str:
    if requested != "auto":
        return requested
    lowered = filename.lower()
    for marketplace in ("amazon", "ebay", "tiktok", "shopify"):
        if marketplace in lowered:
            return marketplace
    return "unknown"


def _id(source_file: str, index: int, title: str, sku: str) -> str:
    return hashlib.sha1(f"{source_file}:{index}:{title}:{sku}".encode("utf-8")).hexdigest()[:12]


def mark_duplicates(items: list[BulkUpdateItem]) -> list[BulkUpdateItem]:
    seen: set[str] = set()
    for item in items:
        key = (item.sku or item.asin or item.barcode or item.title).strip().lower()
        if key and key in seen:
            item.status = "duplicate"
            if "Possible duplicate import row." not in item.warnings:
                item.warnings.append("Possible duplicate import row.")
        elif item.status == "new" and item.warnings:
            item.status = "needs_review"
        seen.add(key)
    return items


def deterministic_normalize(parsed_files: list[ParsedFile], marketplace: str) -> list[BulkUpdateItem]:
    items: list[BulkUpdateItem] = []
    for parsed in parsed_files:
        detected_marketplace = _marketplace(parsed.filename, marketplace)
        if not parsed.rows:
            title = parsed.filename.rsplit(".", 1)[0].replace("-", " ").replace("_", " ").strip()
            items.append(
                BulkUpdateItem(
                    id=_id(parsed.filename, 0, title, ""),
                    source_file=parsed.filename,
                    marketplace=detected_marketplace,  # type: ignore[arg-type]
                    status="needs_review",
                    title=title or parsed.filename,
                    image_filename=parsed.filename if parsed.source_type == "image" else "",
                    warnings=[f"{parsed.source_type.upper()} evidence needs AI review before publishing."],
                )
            )
            continue

        for index, row in enumerate(parsed.rows):
            title = _field(row, "title") or f"Imported product {index + 1}"
            sku = _field(row, "sku")
            item = BulkUpdateItem(
                id=_id(parsed.filename, index, title, sku),
                source_file=parsed.filename,
                marketplace=detected_marketplace,  # type: ignore[arg-type]
                status="new",
                title=title,
                sku=sku,
                asin=_field(row, "asin"),
                barcode=_field(row, "barcode"),
                stock=_int(_field(row, "stock")),
                price=_float(_field(row, "price")),
                category=_field(row, "category"),
                brand=_field(row, "brand"),
                description=_field(row, "description"),
                normalized={key: value for key, value in row.items() if value},
            )
            if not item.sku and not item.asin and not item.barcode:
                item.warnings.append("Missing SKU, ASIN, or barcode.")
            if item.title.startswith("Imported product"):
                item.warnings.append("Missing product title.")
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
                        "id": {"type": "string"},
                        "source_file": {"type": "string"},
                        "marketplace": {"type": "string", "enum": ["amazon", "ebay", "tiktok", "shopify", "unknown"]},
                        "status": {"type": "string", "enum": ["new", "duplicate", "needs_review"]},
                        "title": {"type": "string"},
                        "sku": {"type": "string"},
                        "asin": {"type": "string"},
                        "barcode": {"type": "string"},
                        "stock": {"type": "integer", "minimum": 0},
                        "price": {"type": "number", "minimum": 0},
                        "currency": {"type": "string"},
                        "category": {"type": "string"},
                        "brand": {"type": "string"},
                        "description": {"type": "string"},
                        "image_filename": {"type": "string"},
                        "normalized": {
                            "type": "object",
                            "additionalProperties": {
                                "anyOf": [
                                    {"type": "string"},
                                    {"type": "number"},
                                    {"type": "integer"},
                                    {"type": "array", "items": {"type": "string"}},
                                ]
                            },
                        },
                        "warnings": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": [
                        "id",
                        "source_file",
                        "marketplace",
                        "status",
                        "title",
                        "sku",
                        "asin",
                        "barcode",
                        "stock",
                        "price",
                        "currency",
                        "category",
                        "brand",
                        "description",
                        "image_filename",
                        "normalized",
                        "warnings",
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
