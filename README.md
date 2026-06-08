# Bulk Import AI

Standalone FastAPI service for bulk product import normalization.

It accepts CSV, XLSX, PDF, and image uploads, runs a LangGraph normalization workflow, extracts product-like rows, and returns normalized JSON:

```json
[
  {
    "id": "b4f8f3f7e3d1",
    "source_file": "amazon-products.csv",
    "marketplace": "amazon",
    "status": "new",
    "title": "Smart Watch Series 7",
    "sku": "WTCH-S7-BLK",
    "asin": "",
    "barcode": "",
    "stock": 3,
    "price": 25.99,
    "currency": "USD",
    "category": "",
    "brand": "Acme",
    "description": "",
    "image_filename": "",
    "normalized": {},
    "warnings": []
  }
]
```

## Run

```bash
cd bulk-update-ai
copy .env.example .env
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8100
```

Open `http://127.0.0.1:8100/docs`.

## Endpoints

- `GET /health`
- `POST /bulk-import`

## Project Structure

```text
app/
  api/        FastAPI routes
  core/       settings and exception handlers
  graphs/     LangGraph workflows
  schemas/    Pydantic request/response models
  services/   parsing and normalization logic
  main.py     app factory and middleware
```

`bulk-import` form field:

- `file`: one CSV/XLSX/PDF/image upload

Direct upload:

```bash
curl -X POST http://127.0.0.1:8100/bulk-import \
  -F "file=@examples/sample-products.csv"
```

If a different file type is uploaded, the API returns:

```json
{
  "detail": {
    "message": "Only Excel, CSV, PDF, or image files are allowed.",
    "code": "unsupported_file_type",
    "filename": "notes.txt",
    "content_type": "text/plain",
    "allowed_file_types": ["excel", "csv", "pdf", "image"]
  },
  "code": "unsupported_file_type",
  "path": "/bulk-import"
}
```

Oversized uploads return JSON with `413` instead of breaking the service:

```json
{
  "detail": "Upload request is too large.",
  "code": "request_too_large",
  "max_request_size_bytes": 52428800,
  "received_size_bytes": 73400320
}
```

## AI

The service works without AI using deterministic parsing. To enable OpenAI normalization:

```env
OPENAI_ENABLED=true
OPENAI_API_KEY=sk-your-key
OPENAI_MODEL=gpt-5
```

Images and PDFs are accepted as evidence. Without an OCR/PDF extraction dependency, image rows are created as `needs_review`; PDFs use lightweight embedded text extraction.

## Docker

```bash
cd bulk-update-ai
copy .env.example .env
docker compose up --build
```

The API runs on `http://127.0.0.1:8100`.
