from __future__ import annotations

import csv
import io
import re
import zipfile
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree

from fastapi import HTTPException, UploadFile, status

from app.schemas import ParsedFile


IMAGE_MIME_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
PDF_MIME_TYPES = {"application/pdf"}
CSV_MIME_TYPES = {"text/csv", "application/csv", "application/vnd.ms-excel"}
XLSX_MIME_TYPES = {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}


def get_source_type(filename: str, content_type: str) -> str:
    suffix = Path(filename).suffix.lower()
    if content_type in IMAGE_MIME_TYPES or suffix in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
        return "image"
    if content_type in PDF_MIME_TYPES or suffix == ".pdf":
        return "pdf"
    if content_type in XLSX_MIME_TYPES or suffix == ".xlsx":
        return "excel"
    if content_type in CSV_MIME_TYPES or suffix == ".csv":
        return "csv"
    return "unknown"


def parse_csv(data: bytes) -> list[dict[str, str]]:
    try:
        text = data.decode("utf-8-sig", errors="replace")
        sample = text[:2048]
        dialect = csv.Sniffer().sniff(sample) if sample.strip() else csv.excel
    except csv.Error:
        dialect = csv.excel
    except UnicodeError as exc:
        raise ValueError("CSV file could not be decoded as text.") from exc

    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    return [
        {str(key or "").strip(): (value or "").strip() for key, value in row.items() if str(key or "").strip()}
        for row in reader
    ]


def _cell_text(cell: ElementTree.Element, shared_strings: list[str], ns: dict[str, str]) -> str:
    value = cell.find("x:v", ns)
    inline = cell.find("x:is/x:t", ns)
    if inline is not None and inline.text:
        return inline.text.strip()
    if value is None or value.text is None:
        return ""
    if cell.attrib.get("t") == "s":
        index = int(value.text)
        return shared_strings[index] if 0 <= index < len(shared_strings) else ""
    return value.text.strip()


def parse_xlsx(data: bytes) -> list[dict[str, str]]:
    ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            shared_strings: list[str] = []
            if "xl/sharedStrings.xml" in archive.namelist():
                root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
                shared_strings = ["".join(node.itertext()).strip() for node in root.findall("x:si", ns)]

            sheet_name = next((name for name in archive.namelist() if name.startswith("xl/worksheets/sheet")), None)
            if sheet_name is None:
                return []

            root = ElementTree.fromstring(archive.read(sheet_name))
            table = [
                [_cell_text(cell, shared_strings, ns) for cell in row.findall("x:c", ns)]
                for row in root.findall(".//x:sheetData/x:row", ns)
            ]
    except (zipfile.BadZipFile, ElementTree.ParseError, KeyError, ValueError) as exc:
        raise ValueError("Excel file could not be parsed. Upload a valid .xlsx file.") from exc

    table = [row for row in table if any(row)]
    if not table:
        return []

    headers = [header.strip() or f"column_{index + 1}" for index, header in enumerate(table[0])]
    rows: list[dict[str, str]] = []
    for raw_row in table[1:]:
        row = {headers[index]: raw_row[index].strip() for index in range(min(len(headers), len(raw_row)))}
        if any(row.values()):
            rows.append(row)
    return rows


def parse_pdf_text(data: bytes) -> str:
    decoded = data.decode("latin-1", errors="ignore")
    chunks = re.findall(r"\(([^()]{2,})\)", decoded)
    if chunks:
        text = " ".join(chunk.replace("\\)", ")").replace("\\(", "(") for chunk in chunks)
        return re.sub(r"\s+", " ", text).strip()
    printable = "".join(char if char.isprintable() else " " for char in decoded)
    return re.sub(r"\s+", " ", printable).strip()[:8000]


def rows_to_text(rows: Iterable[dict[str, str]]) -> str:
    return "\n".join("; ".join(f"{key}: {value}" for key, value in row.items() if value) for row in rows)


async def parse_upload(upload: UploadFile, max_size_bytes: int) -> ParsedFile:
    data = await upload.read()
    filename = upload.filename or "upload.bin"
    content_type = upload.content_type or "application/octet-stream"

    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": f"{filename} is empty. Please upload a file with data.",
                "code": "empty_upload_file",
                "filename": filename,
            },
        )
    if len(data) > max_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={
                "message": f"{filename} is too large.",
                "code": "file_too_large",
                "filename": filename,
                "max_file_size_bytes": max_size_bytes,
                "received_size_bytes": len(data),
            },
        )

    source_type = get_source_type(filename, content_type)
    rows: list[dict[str, str]] = []
    text = ""

    try:
        if source_type == "csv":
            rows = parse_csv(data)
            text = rows_to_text(rows)
        elif source_type == "excel":
            rows = parse_xlsx(data)
            text = rows_to_text(rows)
        elif source_type == "pdf":
            text = parse_pdf_text(data)
        elif source_type == "image":
            text = f"Image evidence uploaded: {filename}"
        else:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail={
                    "message": "Only Excel, CSV, PDF, or image files are allowed.",
                    "code": "unsupported_file_type",
                    "filename": filename,
                    "content_type": content_type,
                    "allowed_file_types": ["excel", "csv", "pdf", "image"],
                },
            )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": str(exc),
                "code": "file_parse_error",
                "filename": filename,
            },
        ) from exc

    return ParsedFile(
        filename=filename,
        content_type=content_type,
        source_type=source_type,  # type: ignore[arg-type]
        rows=rows,
        text=text[:12000],
    )
