# Bulk Update AI

Standalone FastAPI service for bulk product import normalization.

It accepts CSV, XLSX, PDF, and image uploads, runs a LangGraph normalization workflow, extracts product-like rows, and returns normalized JSON:

```json
{
  "summary": {
    "files_received": 1,
    "rows_detected": 2,
    "items_generated": 2,
    "duplicates": 0,
    "needs_review": 0
  },
  "items": [
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
}
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

- `GET /api/health`
- `POST /api/bulk-update/normalize`
- `POST /api/bulk-update/validate`

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

`normalize` form fields:

- `files`: one or more files, CSV/XLSX/PDF/image
- `marketplace`: `auto`, `amazon`, `ebay`, `tiktok`, or `shopify`
- `use_ai`: `true` or `false`

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
