# Bulk Import AI Structure

```text
app/
  api/        FastAPI routes
  core/       settings and exception handlers
  graphs/     LangGraph bulk normalization workflow
  schemas/    Pydantic request/response models
  services/   file parsing and product normalization
  main.py     app setup and request-size middleware
```

Compatibility shim modules remain at `app/config.py`, `app/exceptions.py`,
`app/routes.py`, `app/parser.py`, `app/normalizer.py`, and
`app/normalization_graph.py` so older imports still work while new code uses the
structured packages.
