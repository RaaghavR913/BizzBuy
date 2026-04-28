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

## Storage Defaults

Unless overridden with absolute paths, backend storage resolves from this `backend/` directory:

- `BIZBUY_ARTIFACT_DIR=.artifacts` writes to `backend/.artifacts`
- `BIZBUY_UPLOAD_DIR=uploads` writes to `backend/uploads`

The resolver also treats the legacy relative value `backend/.artifacts` as `backend/.artifacts`, which prevents duplicate `backend/backend/.artifacts` trees when tests or local servers run from inside this directory.

## Production Controls

Set these for a public Railway deployment:

```env
BIZBUY_ENV=production
FRONTEND_ORIGIN=https://<frontend-domain>
BIZBUY_REQUIRE_EXPENSIVE_ROUTE_AUTH=true
BIZBUY_API_BEARER_TOKEN=<strong-secret>
OPENROUTER_API_KEY=<secret>
MISTRAL_API_KEY=<secret>
OPENROUTER_REFERRER=https://<frontend-domain>
BIZBUY_API_DOCS_ENABLED=false
BIZBUY_PIPELINE_PROMPT_DEBUG_ARTIFACTS_ENABLED=false
BIZBUY_PIPELINE_PROMPT_DEBUG_INCLUDE_BODIES=false
BIZBUY_DELETE_UPLOADS_AFTER_INGEST=true
```

Production mode requires explicit non-local CORS origins and protects expensive routes with bearer-token auth by default. Do not expose `BIZBUY_API_BEARER_TOKEN` through `NEXT_PUBLIC_*` frontend variables. The Railway frontend should call this service through the Next.js server-side proxy at `/api/backend/*`; only the Next.js service should hold the bearer token.

Recommended Railway topology:

- `bizzbuy-web`: public Next.js service with `BIZBUY_BACKEND_URL=http://<backend-internal-host>:8000/api` and the same `BIZBUY_API_BEARER_TOKEN`.
- `bizzbuy-api`: FastAPI service, private/internal where Railway supports it. If it has a public URL, expensive routes still require the bearer token.

Abuse controls are intentionally conservative for a beta:

- Upload requests default to 10 files and 100 MB total.
- DOCX/XLSX parsing rejects archives with more than 256 entries or more than 50 MB decompressed content.
- Rate limits and SSE connection counters are in-memory. Use a trusted gateway or Redis-backed limiter before multi-instance production.
- The backend ignores arbitrary `x-forwarded-for` by default. Set `BIZBUY_TRUST_X_FORWARDED_FOR=true` only with a precise `BIZBUY_TRUSTED_PROXY_IPS` allowlist.

## Notes

- The risk engine is deterministic by design.
- OCR cache references returned to clients are opaque `ocr:<sha256>` tokens, not server filesystem paths.
- The frontend can stay in Next.js and call this service over HTTP through the BFF proxy.
