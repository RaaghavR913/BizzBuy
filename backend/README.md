# BizBuy Python Backend

This service is the deterministic backend for BizBuy. It owns:

- financial calculations
- risk scoring
- recommendation policy
- report assembly

## Run Locally

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
uvicorn app.main:app --reload --port 8000
```

Open the docs at `http://localhost:8000/docs`.

## Current Endpoints

- `GET /api/health`
- `POST /api/parse-documents`
- `POST /api/analyze`

## Notes

- The risk engine is deterministic by design.
- The document parsing route is scaffolded for the next phase and currently returns normalized placeholders and parsing notes.
- The frontend can stay in Next.js and call this service over HTTP.
