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

In production, API docs are disabled by default. Set `BIZBUY_API_DOCS_ENABLED=true` only when public docs are intentional.

## Current Endpoints

- `GET /api/health`
- `POST /api/documents/ingest`
- `POST /api/parse-documents`
- `POST /api/analyze`
- `POST /api/analyses`
- `GET /api/analyses/{analysis_id}`
- `GET /api/analyses/{analysis_id}/events`
- `POST /api/pipeline`

## Production Controls

Set these for a public Railway deployment:

```env
BIZBUY_ENV=production
FRONTEND_ORIGIN=https://<frontend-domain>
BIZBUY_API_BEARER_TOKEN=<server-side-token>
BIZBUY_PIPELINE_PROMPT_DEBUG_ARTIFACTS_ENABLED=false
BIZBUY_PIPELINE_PROMPT_DEBUG_INCLUDE_BODIES=false
```

Production mode requires explicit non-local CORS origins and protects expensive routes with bearer-token auth by default. Do not expose `BIZBUY_API_BEARER_TOKEN` through `NEXT_PUBLIC_*` frontend variables; use a real auth layer, trusted gateway, or server-side proxy for public users.

## Notes

- The risk engine is deterministic by design.
- The document parsing route is scaffolded for the next phase and currently returns normalized placeholders and parsing notes.
- The frontend can stay in Next.js and call this service over HTTP.
