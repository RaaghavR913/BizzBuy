# DevModeConfig — Session Summary

## Phase 1 — Document Ingestion Auto-Classification with Claude Haiku 4.5

**Goal:** Rework Step 1 of the user flow so users simply upload files without labeling them. Claude Haiku 4.5 classifies each file automatically.

### Backend — New files

#### `backend/app/agents/document_classifier.py`

The core classification agent. Key characteristics:

- **Model:** `claude-haiku-4-5-20251001`
- **Approach:** Direct Anthropic API call with tool use (`classify_document` tool), not the pipeline's `call_agent` system. This is intentional — the classifier runs as a pre-pipeline step and needs different content block handling (PDF document blocks, image blocks) that `call_agent` doesn't support.
- **Content handling by file type:**
  - PDF → Anthropic document content block (base64, native PDF reading by Haiku)
  - Image (PNG/JPG/JPEG/WebP) → Image content block (base64)
  - CSV/TXT → Text preview (header + first ~30 rows, truncated to ~8K chars)
  - XLSX → Parsed via stdlib `zipfile`/`xml.etree` (reusing `intake_service._extract_xlsx_workbook`), rendered as text preview
- **Self-healing retry:** If Pydantic validation fails on the first attempt, the model is re-prompted once with the validation errors appended.
- **Fallback:** If all retries fail, returns `detectedType: "unknown"` with `confidence: 0.0`.
- **Output schema (`DocumentClassification`):**
  - `detectedType` — one of 15 canonical types (matching existing `DocumentType` enum + `unknown`)
  - `confidence` — 0.0–1.0
  - `rationale` — max 400 chars explaining the classification
  - `suggestedAlternatives` — up to 3 alternative types
  - `extractedMetadata` — `businessName`, `periodStart`, `periodEnd`, `currency` (nullable)
- **Deterministic fields computed in code, not by the model:** file size, MIME type, original filename.

#### `backend/app/api/routes/ingest_documents.py`

New route: `POST /api/documents/ingest`

- Accepts `multipart/form-data` with one or more files
- Generates a `runId` (UUID) per batch
- Writes each file to `uploads/<runId>/<originalName>`
- Classifies all files concurrently via `asyncio.gather` (each classification runs in a thread executor)
- Per-file error handling: one bad file does not fail the batch. Failed files get `detectedType: "unknown"` with the error message.
- Response shape:

```json
{
  "runId": "uuid",
  "files": [
    {
      "fileId": "uuid",
      "originalName": "tax-return-2023.pdf",
      "mimeType": "application/pdf",
      "sizeBytes": 245760,
      "detectedType": "tax_return_1120s",
      "confidence": 0.95,
      "rationale": "Contains IRS Form 1120-S header with corporation name and EIN...",
      "suggestedAlternatives": ["tax_return_1040"],
      "extractedMetadata": {
        "businessName": "Acme LLC",
        "periodStart": "2023-01-01",
        "periodEnd": "2023-12-31",
        "currency": "USD"
      }
    }
  ]
}
```

### Backend — Modified files

| File | Change |
|---|---|
| `backend/app/api/router.py` | Added `ingest_documents_router` under the `document-classification` tag. |

### Frontend — New files

#### `components/upload/ClassificationReview.tsx`

A table component shown after classification completes. For each file:

- **Filename** with rationale preview
- **Detected type** as a color-coded badge (accent for known types, yellow for `other`, red for `unknown`; ring highlight if overridden)
- **Confidence bar** — green (≥85%), yellow (≥65%), red (<65%)
- **Override dropdown** — "Looks wrong?" select using `CANONICAL_DOCUMENT_TYPES`. This is the user's escape hatch but not the primary interaction.

### Frontend — Modified files

#### `components/upload/FileDropZone.tsx` (replaced)

- **Removed:** The `<Select>` dropdown for manual document type assignment and the `updateDocumentType` callback. Users no longer label files manually.
- **Added:** Per-file `ClassificationStatus` indicator (queued → uploading → classifying → classified | error) with animated icons.
- **Updated:** Accepted file types now include `.webp`, `.xls`. Max files bumped from 6 to 10.
- **Added:** `disabled` prop to lock the dropzone during classification.
- **Changed:** `FileItem` interface — `documentType: string` (required) replaced with `classificationStatus: ClassificationStatus` (required) and `documentType?: string` (optional, set after classification).

#### `app/analyze/upload/page.tsx` (replaced)

Reworked into a two-phase flow:

1. **Upload & Classify** — User drops files, clicks "Upload & Classify". Files are sent to `POST /api/documents/ingest`. Status indicators animate through queued → uploading → classifying → classified.
2. **Review & Continue** — Classification results appear in the `ClassificationReview` table. User can override any type. Clicking "Continue with these classifications" sends files to the existing `POST /api/parse-documents` with the effective types (AI-detected or user-overridden).

The "Skip — I'll enter data manually" and "Load Demo" buttons are preserved.

**Previous behavior removed:** The upload button was disabled until every file had a manually selected document type. This gate is gone.

#### `lib/api-client.ts`

- Added `ingestDocuments(files: File[]): Promise<IngestResponse>` — calls `POST /api/documents/ingest` with multipart form data.
- Added `IngestResponse` to imports.

#### `lib/types.ts`

- Added `ClassificationStatus` type: `'queued' | 'uploading' | 'classifying' | 'classified' | 'error'`
- Added `ClassifiedFileResult` interface matching the backend response
- Added `IngestResponse` interface: `{ runId: string; files: ClassifiedFileResult[] }`
- Added `'unknown'` to `CanonicalDocumentType` union

#### `lib/constants.ts`

- Added `{ value: 'unknown', label: 'Unknown' }` to `CANONICAL_DOCUMENT_TYPES` array.

#### `.env.example`

- Added `BIZBUY_UPLOAD_DIR` env var (default: `uploads`).

### Pipeline wiring

The classification does **not** require changes to any existing pipeline agent, schema, or runner. The boundary adaptation works as follows:

1. Frontend sends the AI-detected `detectedType` (or user override) as the file type when calling `POST /api/parse-documents`.
2. The existing `parse_documents_route` → `document_parser.parse_documents` → `intake_service.normalize_document_payload` chain reads `document_type` / `canonical_type` from the document dict.
3. The `canonical_type` becomes the `document_type` on each `DocumentInfo` in the `IngestionOutput`.
4. Downstream agents filter documents by `document_type` — unchanged.

### Documentation

`docs/CODEBASE_AUDIT.md` updated with Section 11: Document Ingestion Flow, including:

- Mermaid sequence diagram showing the full flow from user drop → storage → classification → review → downstream routing
- File inventory table
- Pipeline wiring explanation
- Design decisions table
- Test plan with 3 sample files and expected classifications

---

## Complete file manifest

### Created (8 files)

| File | Phase |
|---|---|
| `docs/CODEBASE_AUDIT.md` | 1 |
| `backend/Dockerfile` | 2 |
| `Dockerfile` (repo root) | 2 |
| `docker-compose.yml` | 2 |
| `backend/.dockerignore` | 2 |
| `.env.example` | 2 |
| `backend/app/agents/document_classifier.py` | 3 |
| `backend/app/api/routes/ingest_documents.py` | 3 |
| `components/upload/ClassificationReview.tsx` | 3 |

### Replaced (3 files)

| File | Phase | What changed |
|---|---|---|
| `.dockerignore` (root) | 2 | Replaced with comprehensive exclusion list |
| `components/upload/FileDropZone.tsx` | 3 | Removed manual type picker, added classification status |
| `app/analyze/upload/page.tsx` | 3 | Removed manual labeling flow, added auto-classify + review |

### Modified (6 files)

| File | Phase | What changed |
|---|---|---|
| `.gitignore` | 2 | Added `sample company*/`, `uploads/`, `backend/.artifacts/` |
| `docs/CODEBASE_AUDIT.md` | 2, 3 | Added Sections 9, 10, 11 |
| `backend/app/api/router.py` | 3 | Registered `ingest_documents` router |
| `lib/api-client.ts` | 3 | Added `ingestDocuments()` function |
| `lib/types.ts` | 3 | Added classification types, `'unknown'` to document types |
| `lib/constants.ts` | 3 | Added `'unknown'` to canonical document types |
| `.env.example` | 3 | Added `BIZBUY_UPLOAD_DIR` |

### Not modified (by design)

- `backend/app/agents/runners.py` — No changes to existing pipeline agents
- `backend/app/agents/schemas.py` — No changes to Pydantic schemas
- `backend/app/agents/prompts.py` — Classifier prompt lives in its own module
- `backend/app/agents/registry.py` — Classifier is not a pipeline agent
- `backend/app/agents/orchestrator.py` — Pipeline orchestration unchanged
- `backend/app/services/ingestion_service.py` — Ingestion logic unchanged
- `backend/app/services/intake_service.py` — Document normalization unchanged
- `context/AnalysisContext.tsx` — State management unchanged
- `app/analyze/review/page.tsx` — Review page unchanged

---

## How to run (Docker)

All local development and testing described here assumes the stack is running via **Docker Compose** at the repository root.

### Prerequisites

- **Docker Desktop** (or Docker Engine + Compose v2) running
- **Anthropic API key** in `.env.local` (classification and the 10-agent pipeline need it)

### One-time setup

```bash
cd /path/to/BizzBuy

# Copy env template (if you do not already have .env.local)
cp .env.example .env.local

# Edit .env.local and set:
#   ANTHROPIC_API_KEY=sk-ant-...
# Optional: NEXT_PUBLIC_BACKEND_URL=http://localhost:8000/api (compose sets this for the frontend service)
```

### Start the stack

```bash
docker compose up --build
```

- **Frontend:** http://localhost:3000  
- **Backend API base:** http://localhost:8000/api  
- The frontend container waits until the backend health check passes before starting.

### Stop the stack

```bash
# In the terminal where compose is running: Ctrl+C

# Or from another terminal:
docker compose down

# Remove anonymous volumes (clean node_modules / .next in containers):
docker compose down -v
```

---

## How to test the application (Docker)

Use these checks in order. Everything hits **localhost** from your machine; the browser talks to the backend on `localhost:8000`, not the Docker internal service name.

### 1. Confirm both services are up

```bash
docker compose ps
```

Expect **bizbuy-backend** with status including **healthy**, and **bizbuy-frontend** running.

### 2. Backend health endpoint

```bash
curl -s http://localhost:8000/api/health | python3 -m json.tool
```

You should see JSON with `"ok": true`, the service name, environment, and CORS-related fields. If this fails, classification and parsing will not work from the UI either.

### 3. Document classification API (Haiku)

Requires a valid `ANTHROPIC_API_KEY` in `.env.local` (loaded into the backend container).

```bash
curl -s -X POST http://localhost:8000/api/documents/ingest \
  -F "files=@/absolute/path/to/your-file.pdf"
```

**Success:** JSON with `runId` and a `files` array. Each item should include `detectedType`, `confidence`, `rationale`, and optional `error` if that file failed.

**On disk:** Files are written under `./uploads/<runId>/` on the host (bind-mounted into the backend container).

**Multi-file:** Append more `-F "files=@..."` lines to the same request.

### 4. Parse documents API (after classification types are known)

This mirrors what the UI does on “Continue with these classifications.” You need real files and a JSON array of types aligned with upload order (same values the classifier returns, e.g. `profit_and_loss`, `tax_return_1120s`).

```bash
curl -s -X POST http://localhost:8000/api/parse-documents \
  -F "files=@/path/to/file1.pdf" \
  -F "files=@/path/to/file2.csv" \
  -F 'fileTypes=["profit_and_loss","ar_aging_report"]'
```

**Success:** JSON with `success: true`, `extractedData`, optional `analysisId`, and `pipelineDocuments`.

### 5. End-to-end in the browser (recommended)

With `docker compose up` running:

1. Open **http://localhost:3000/analyze/upload**
2. Drop one or more supported files (PDF, PNG, JPG, JPEG, WebP, CSV, XLSX, XLS)
3. Click **Upload & Classify** and wait for per-file status to reach **Classified** (or **Error** for a bad file)
4. Review the **Classification results** table: badges, confidence bars, optional **Looks wrong?** override
5. Click **Continue with these classifications**
6. On **Review** (step 2), confirm extracted numbers and deal info, then continue through questionnaire and report as usual

**Demo without uploads:** Use **Load Demo — Sunny's HVAC Services** on the upload page (skips classification).

**Without API usage:** Use **Skip — I'll enter data manually** and fill the review form.

### 6. Sample files to validate classification (optional)

| What you upload | Rough expectation for `detectedType` |
|---|---|
| PDF of an IRS Form 1120-S | `tax_return_1120s` |
| Photo or scan of a balance sheet | `balance_sheet` |
| CSV with AR aging–style columns (buckets 0–30, 31–60, …) | `ar_aging_report` |

Results depend on document quality and content; use overrides on the upload page if the model mislabels.

### 7. Logs and debugging inside containers

```bash
# Follow all service logs
docker compose logs -f

# Backend only
docker compose logs -f backend

# Frontend only
docker compose logs -f frontend
```

```bash
# Shell into backend (Python / uvicorn)
docker compose exec backend bash

# Shell into frontend (Alpine)
docker compose exec frontend sh
```

### 8. Rebuild after dependency or Dockerfile changes

```bash
docker compose build --no-cache
docker compose up
```

### Common issues

| Symptom | What to check |
|---|---|
| Frontend never starts | `docker compose ps` — backend must become **healthy** first |
| Classification returns errors or `unknown` | `ANTHROPIC_API_KEY` in `.env.local`, quota, and network from container |
| Browser cannot reach API | `NEXT_PUBLIC_BACKEND_URL` should be `http://localhost:8000/api` for browser calls; confirm in compose `environment` for `frontend` |
| Empty or stale UI after code edits | Hot reload should apply; if not, restart `docker compose` or rebuild frontend image |
