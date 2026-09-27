# BizzBuy

An AI acquisition diligence co-pilot for small-business buyers.

Built in one month for a hackathon, BizzBuy won **2nd place** and was also recognized by investors with the **Most Market Ready** award.

## The Problem

Buying a small business is one of the biggest financial decisions most people will ever make, but the diligence process is still slow, expensive, and fragmented.

A buyer usually has to collect and review income statements, P&Ls, tax returns, leases, employee agreements, and supporting operating documents, then pay outside accountants, brokers, or auditors tens of thousands of dollars to interpret what those files actually mean. That process can take months, sometimes years, before a buyer feels confident enough to move forward or walk away.

The real product problem is not just "document review is annoying." It is that small-business acquisition diligence is too expert-dependent, too expensive, and too slow for the average buyer evaluating a real deal.

## Why I Built It

I built BizzBuy around a product decision: compress a months-long diligence workflow into a guided, reviewable system that gets a buyer to a defensible first-pass answer in minutes, not months.

Instead of building a generic "chat with your documents" demo, I designed BizzBuy as a structured acquisition workflow:

- ingest the diligence packet
- classify and parse the documents
- let the buyer review extracted data before analysis
- run specialist analysis across the business
- assemble a decision-ready report around affordability, transferability, and risk

That decision shaped the entire architecture. I did not want a single black-box LLM answer. I wanted a system that combined OCR, deterministic financial logic, targeted specialist agents, and a user review step so the output felt more like a real diligence process than a one-shot summary.

## What BizzBuy Does

BizzBuy helps buyers evaluate whether a small business is financially viable, transferable, and worth deeper diligence.

In the current product flow:

1. Upload diligence documents at `/analyze/upload`.
2. Review detected document types and extracted financial data at `/analyze/review`.
3. Answer targeted clarification questions at `/analyze/questions`.
4. Generate and review the acquisition report at `/analyze/report`.

At a high level, the system works like this:

1. The user uploads the diligence packet.
2. BizzBuy scans and extracts the underlying information with Mistral OCR.
3. The backend normalizes those files into structured review data.
4. Deterministic scoring and specialized analysis agents evaluate the business.
5. The app assembles a report focused on affordability, transferability, and material risks.

The frontend calls backend routes through the Next.js server-side proxy at `/api/backend/*`, so the browser does not need direct access to the FastAPI service or backend bearer token.

## YouTube Demo

[Watch the demo](https://youtu.be/9SoUmrGJKwY?si=B0KQRpTwsMiOE6yU)

## Technical Depth

This project was much deeper than a landing page with an API call.

Key technical decisions:

- **Next.js as the product surface and BFF layer**: I used Next.js 16 and React 18 for the user-facing workflow, but also as a server-side proxy so backend auth tokens stay off the client.
- **FastAPI for the analysis runtime**: I split the backend into a Python service that owns parsing, orchestration, scoring, schemas, and report assembly rather than mixing business logic into the frontend.
- **Mistral OCR for document ingestion**: The product depends on being able to handle messy real-world diligence files, so OCR was a first-class part of the pipeline instead of an afterthought.
- **Deterministic scoring plus agent synthesis**: I intentionally combined rule-based financial and risk calculations with OpenRouter-backed specialist analysis so the system had both consistency and breadth.
- **Human-in-the-loop review before final analysis**: I added an explicit review step because extraction is never perfect, and acquisition decisions should not rely on unverified parsed data.
- **Streaming analysis jobs**: The app supports analysis jobs and server-sent events so longer-running diligence work can feel responsive instead of blocking the UI.
- **Security and deployment separation**: The browser never needs direct access to expensive or sensitive backend routes; the frontend proxy and bearer-token boundary keep that control server-side.

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 16, React 18, TypeScript, Tailwind CSS |
| Backend | FastAPI, Pydantic v2, pytest |
| LLM runtime | OpenRouter via the OpenAI Python SDK |
| OCR | Mistral OCR |
| Reports | Deterministic scoring plus optional agent synthesis |
| PDF | `@react-pdf/renderer` |

## Clean Scope Of My Role

I owned every layer of this project end to end:

- product framing and deciding to focus on acquisition diligence instead of generic document Q&A
- workflow design for upload, review, clarifications, and final report generation
- frontend implementation in Next.js, React, TypeScript, and Tailwind
- backend architecture in FastAPI, including routes, schemas, services, orchestration, and tests
- OCR ingestion flow and document normalization pipeline
- deterministic financial and risk scoring logic
- multi-agent analysis flow and report assembly
- deployment architecture, including the server-side proxy pattern and production controls

In short: this was not just a concept or prototype screen. I built the application, the backend system design, the agent workflow, and the deployment/security model that made the product usable.

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
OPENROUTER_API_KEY=
MISTRAL_API_KEY=
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

Railway deployments should use two services:

| Service | Source / Dockerfile | Key variables |
|---|---|---|
| `bizzbuy-web` | Repo root, `Dockerfile` | `BIZBUY_BACKEND_URL=http://${{bizzbuy-api.RAILWAY_PRIVATE_DOMAIN}}:8000/api`, `BIZBUY_API_BEARER_TOKEN=<same-secret-as-api>`, `BIZBUY_FLOW_TOKEN_SECRET=<strong-secret>`, `NEXT_PUBLIC_APP_URL=https://<frontend-domain>` |
| `bizzbuy-api` | Root directory `backend`, Dockerfile path `Dockerfile` | `BIZBUY_ENV=production`, `BIZBUY_BIND_HOST=::`, `FRONTEND_ORIGIN=https://<frontend-domain>`, `BIZBUY_API_BEARER_TOKEN=<same-secret-as-web>`, `OPENROUTER_API_KEY=<secret>`, `MISTRAL_API_KEY=<secret>` |

If the API service is configured from the repo root instead of the `backend/` source root, Railway may build the Next.js Dockerfile for both services. A backend service showing `npm` or `next start` logs is misconfigured; it should show `uvicorn` / FastAPI startup logs. If the Python build fails on `COPY pyproject.toml README.md ./`, the build context is still not `backend`; set Root Directory to `backend` and leave Dockerfile Path as `Dockerfile`, not `backend/Dockerfile`. If the frontend proxy gets `ECONNREFUSED` while the API is running, confirm the API is bound to `::` for Railway private networking. Do not set `BIZBUY_BACKEND_URL` to `localhost` in Railway, because `localhost` points back to the same container.

Docker Compose files are provided as local/reference deployment guidance. Railway services should provide private writable directories or volumes for artifacts and uploads.

## Disclaimer

BizzBuy is for informational diligence support only. It is not financial, legal, tax, or investment advice. Buyers should verify outputs and consult qualified professionals before making acquisition decisions.
