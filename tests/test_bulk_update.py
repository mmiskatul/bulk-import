from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_healthcheck() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_csv_normalize_returns_items() -> None:
    response = client.post(
        "/bulk-import",
        files={
            "file": (
                "amazon-products.csv",
                b"title,sku,stock,price,brand\nSmart Watch Series 7,WTCH-S7-BLK,3,25.99,Acme\n",
                "text/csv",
            )
        },
    )

    body = response.json()
    assert response.status_code == 200
    assert len(body) == 1
    assert body[0]["title"] == "Smart Watch Series 7"
    assert body[0]["marketplace"] == "amazon"
    assert body[0]["price"] == 25.99


def test_image_normalize_returns_review_item() -> None:
    response = client.post(
        "/bulk-import",
        files={"file": ("blue-shirt.png", b"\x89PNG\r\n\x1a\n" + (b"\x00" * 32), "image/png")},
    )

    body = response.json()
    assert response.status_code == 200
    assert body[0]["status"] == "needs_review"
    assert body[0]["title"] == "blue shirt"
    assert body[0]["image_filename"] == "blue-shirt.png"


def test_oversized_file_returns_json_413() -> None:
    response = client.post(
        "/bulk-import",
        files={"file": ("large.csv", b"a" * (10 * 1024 * 1024 + 1), "text/csv")},
    )

    body = response.json()
    assert response.status_code == 413
    assert body["detail"]["code"] == "file_too_large"
    assert body["detail"]["filename"] == "large.csv"


def test_invalid_xlsx_returns_json_400() -> None:
    response = client.post(
        "/bulk-import",
        files={"file": ("broken.xlsx", b"not a valid zip", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )

    body = response.json()
    assert response.status_code == 400
    assert body["code"] == "file_parse_error"
    assert body["detail"]["code"] == "file_parse_error"


def test_missing_upload_files_returns_validation_error() -> None:
    response = client.post(
        "/bulk-import",
    )

    body = response.json()
    assert response.status_code == 422
    assert body["code"] == "missing_upload_file"
    assert body["path"] == "/bulk-import"


def test_empty_upload_file_returns_clear_error() -> None:
    response = client.post(
        "/bulk-import",
        files={"file": ("empty.csv", b"", "text/csv")},
    )

    body = response.json()
    assert response.status_code == 400
    assert body["detail"]["code"] == "empty_upload_file"


def test_unsupported_file_type_returns_allowed_types() -> None:
    response = client.post(
        "/bulk-import",
        files={"file": ("notes.txt", b"not product data", "text/plain")},
    )

    body = response.json()
    assert response.status_code == 415
    assert body["code"] == "unsupported_file_type"
    assert body["detail"]["message"] == "Only Excel, CSV, PDF, or image files are allowed."
    assert body["detail"]["allowed_file_types"] == ["excel", "csv", "pdf", "image"]
