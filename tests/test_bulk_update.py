from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_healthcheck() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_csv_normalize_returns_items() -> None:
    response = client.post(
        "/api/bulk-update/normalize",
        data={"marketplace": "amazon", "use_ai": "false"},
        files={
            "files": (
                "amazon-products.csv",
                b"title,sku,stock,price,brand\nSmart Watch Series 7,WTCH-S7-BLK,3,25.99,Acme\n",
                "text/csv",
            )
        },
    )

    body = response.json()
    assert response.status_code == 200
    assert body["summary"]["items_generated"] == 1
    assert body["items"][0]["title"] == "Smart Watch Series 7"
    assert body["items"][0]["marketplace"] == "amazon"
    assert body["items"][0]["price"] == 25.99


def test_image_normalize_returns_review_item() -> None:
    response = client.post(
        "/api/bulk-update/normalize",
        data={"marketplace": "auto", "use_ai": "false"},
        files={"files": ("blue-shirt.png", b"\x89PNG\r\n\x1a\n" + (b"\x00" * 32), "image/png")},
    )

    body = response.json()
    assert response.status_code == 200
    assert body["summary"]["needs_review"] == 1
    assert body["items"][0]["title"] == "blue shirt"
    assert body["items"][0]["image_filename"] == "blue-shirt.png"


def test_oversized_file_returns_json_413() -> None:
    response = client.post(
        "/api/bulk-update/normalize",
        data={"marketplace": "auto", "use_ai": "false"},
        files={"files": ("large.csv", b"a" * (10 * 1024 * 1024 + 1), "text/csv")},
    )

    body = response.json()
    assert response.status_code == 413
    assert body["detail"]["code"] == "file_too_large"
    assert body["detail"]["filename"] == "large.csv"


def test_invalid_xlsx_returns_json_400() -> None:
    response = client.post(
        "/api/bulk-update/normalize",
        data={"marketplace": "auto", "use_ai": "false"},
        files={"files": ("broken.xlsx", b"not a valid zip", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )

    body = response.json()
    assert response.status_code == 400
    assert body["code"] == "file_parse_error"
    assert body["detail"]["code"] == "file_parse_error"


def test_validation_error_returns_consistent_shape() -> None:
    response = client.post("/api/bulk-update/validate", json={"items": [{"stock": -1}]})

    body = response.json()
    assert response.status_code == 422
    assert body["code"] == "validation_error"
    assert body["path"] == "/api/bulk-update/validate"
