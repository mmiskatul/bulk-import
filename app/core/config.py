from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field


load_dotenv(Path(__file__).resolve().parents[2] / ".env")


class Settings(BaseModel):
    app_name: str = "Bulk Update AI"
    app_version: str = "0.1.0"
    host: str = "0.0.0.0"
    port: int = 8100
    max_upload_size_bytes: int = Field(default=10 * 1024 * 1024)
    max_request_size_bytes: int = Field(default=50 * 1024 * 1024)
    cors_origins: tuple[str, ...] = ("http://localhost:3000", "http://127.0.0.1:3000")
    openai_enabled: bool = False
    openai_api_key: str | None = None
    openai_model: str = "gpt-5"


def _csv_env(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    raw = os.getenv(name)
    if not raw:
        return default
    return tuple(value.strip() for value in raw.split(",") if value.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings(
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8100")),
        max_upload_size_bytes=int(os.getenv("MAX_UPLOAD_SIZE_BYTES", str(10 * 1024 * 1024))),
        max_request_size_bytes=int(os.getenv("MAX_REQUEST_SIZE_BYTES", str(50 * 1024 * 1024))),
        cors_origins=_csv_env("CORS_ORIGINS", ("http://localhost:3000", "http://127.0.0.1:3000")),
        openai_enabled=os.getenv("OPENAI_ENABLED", "false").lower() == "true",
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-5"),
    )
