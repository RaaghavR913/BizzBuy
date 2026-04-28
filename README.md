# BizzBuy - AI Acquisition Diligence Co-Pilot

BizzBuy helps buyers evaluate whether a small business is financially viable, transferable, and worth deeper diligence. The app combines document ingestion, deterministic financial/risk scoring, and OpenRouter-backed report synthesis into a four-step acquisition review flow.

## Current Flow

1. Upload diligence documents at `/analyze/upload`.
2. Review detected document types and extracted financial data at `/analyze/review`.
3. Answer targeted clarification questions at `/analyze/questions`.
4. Generate and review the acquisition report at `/analyze/report`.

The frontend calls backend routes through the Next.js server-side proxy at `/api/backend/*`. The browser does not need direct access to the FastAPI service or backend bearer token.

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 16, React 18, TypeScript, Tailwind CSS |
| Backend | FastAPI, Pydantic v2, pytest |
| LLM runtime | OpenRouter via the OpenAI Python SDK |
| OCR | Mistral OCR |
| Reports | Deterministic scoring plus optional agent synthesis |
| PDF | `@react-pdf/renderer` |

## Repository Layout

| Path | Purpose |
|---|---|
| `app/` | Next.js app routes and BFF proxy routes |
| `components/` | UI and workflow components |
| `context/` | Analysis wizard state |
| `lib/` | Frontend API client, types, calculations, and helpers |
| `backend/app/` | FastAPI app, agents, services, schemas, and routes |
| `backend/tests/` | Backend unit and integration tests |
| `backend/tests/fixtures/peakair/` | Synthetic PeakAir parser fixture documents |
| `docs/` | Current planning, security, and implementation notes |
| `docs/archive/` | Historical plans and audits kept for reference only |

## Local Setup

Prerequisites:

- Node.js 18+
- Python 3.11+
- OpenRouter API key for LLM agent calls
- Mistral API key for OCR

Install frontend dependencies:

```bash
npm install
```

Install backend dependencies:

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
```

Create local environment variables at the repo root:

```bash
cp .env.example .env.local
```

Minimum useful values:

```env
OPENROUTER_API_KEY=sk-or-v1-...
MISTRAL_API_KEY=...
BIZBUY_BACKEND_URL=http://localhost:8000/api
BIZBUY_FLOW_TOKEN_SECRET=replace_with_a_long_random_local_secret
```

Run the backend:

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

Run the frontend in a second terminal:

```bash
npm run dev
```

Open `http://localhost:3000`.

## Storage Defaults

Runtime storage is local and ignored by git:

| Variable | Default | Notes |
|---|---|---|
| `BIZBUY_ARTIFACT_DIR` | `backend/.artifacts` | Analysis jobs, reports, prompt debug artifacts, OCR cache |
| `BIZBUY_UPLOAD_DIR` | `backend/uploads` | Temporary upload storage for classification |

Relative defaults and legacy `backend/.artifacts` values are resolved from the backend project root, so running commands from either the repo root or `backend/` does not create `backend/backend/.artifacts`.

## Useful Commands

```bash
npm run build
npm run lint
```

```bash
cd backend
python -m pytest -q
python -m pytest -q tests/test_parse_documents_route.py
python -m pytest -q tests/test_analysis_jobs.py
```

## Backend Endpoints

All backend endpoints are mounted under `/api`:

| Endpoint | Purpose |
|---|---|
| `GET /api/health` | Health check |
| `POST /api/documents/ingest` | Classify uploaded files and create OCR cache refs |
| `POST /api/parse-documents` | Normalize uploaded documents into pipeline documents and review data |
| `POST /api/analyze` | Legacy deterministic analysis path |
| `POST /api/analyses` | Start an analysis job |
| `GET /api/analyses/{analysis_id}` | Read analysis job status/report |
| `GET /api/analyses/{analysis_id}/events` | Stream analysis job updates by SSE |
| `POST /api/pipeline` | Run the pipeline directly |

## Production Notes

For public deployments, set `BIZBUY_ENV=production`, explicit `FRONTEND_ORIGIN`, `BIZBUY_API_BEARER_TOKEN`, `OPENROUTER_API_KEY`, and `MISTRAL_API_KEY`. The Next.js service should keep `BIZBUY_API_BEARER_TOKEN` server-side and call FastAPI through `BIZBUY_BACKEND_URL`; do not expose backend secrets with `NEXT_PUBLIC_*`.

Docker Compose files are provided as local/reference deployment guidance. Railway deployments should run separate frontend and backend services and provide private writable directories or volumes for artifacts and uploads.

## Disclaimer

BizzBuy is for informational diligence support only. It is not financial, legal, tax, or investment advice. Buyers should verify outputs and consult qualified professionals before making acquisition decisions.
