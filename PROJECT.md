# Project: Interactive Architecture Diagram Animator with Video Export

## Architecture
The system consists of six main services:
1. **Frontend (React + Vite + TS)**:
   - Interactive canvas using XYFlow (React Flow) for editing.
   - Background Web Worker running ELKjs for collision-free layout calculations.
   - GSAP with MotionPathPlugin for telemetry animation.
   - A clean, read-only viewer route `/render-box` showing only the pure animated architecture diagram without gridlines, toolbars, or editing handles.
2. **API Gateway (Python FastAPI)**:
   - Handling diagram schema storage, authentication, and exporting jobs.
3. **Database (PostgreSQL)**:
   - Storing user schemas and diagram schemas.
4. **Redis Broker & Job Queue**:
   - Manages video generation jobs asynchronously.
5. **MinIO Object Storage**:
   - Containerized S3-compatible service to store exported MP4 and GIF animations.
6. **Headless Render Worker (Playwright + FFmpeg)**:
   - Runs Playwright to load `/render-box` viewer.
   - Freezes the browser clock and advances GSAP timeline in deterministic steps.
   - Captures PNG screenshots.
   - Uses FFmpeg to compile captured frames into MP4 (libx264) or optimized 256-color GIF.
   - Uploads completed exports to MinIO and updates job status.

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | E2E Testing Track | Design E2E test infra, write Tier 1-4 test cases, publish `TEST_READY.md` | None | DONE (a9c3f411-80d8-48c3-8ba2-551871d32ed4) |
| 2 | Backend API & DB Services | Implement FastAPI gateway, PostgreSQL models, Redis queue API, MinIO client | None | DONE (98ac60e5-7556-4062-a49a-da1afdab63f9) |
| 3 | Frontend Canvas & Layout | Implement React Flow canvas, ELKjs web worker, GSAP path animation, `/render-box` | None | DONE (a2bcd8e5-6aa1-4222-a360-a5f57177fd79) |
| 4 | Headless Render Worker | Implement Playwright worker, deterministic frame capture, FFmpeg compiler, MinIO upload | M2, M3 | DONE (2414d5fa-5060-4ae9-9948-ebbcd00b36d1) |
| 5 | Docker Compose & E2E Validation | Create docker-compose.yml, launch services, run full E2E tests, pass 100% | M1, M4 | DONE (39e857bd-6f59-4d44-89f2-25a867be6c96) |
| 6 | Adversarial Hardening (Tier 5) | Perform white-box gap analysis, challenge edge cases, run Forensic Auditor | M5 | DONE (e890f001-ebbb-4e33-a0ae-393ea4f046b5) |

## Interface Contracts
### API Gateway ↔ Headless Render Worker (via Redis & PostgreSQL)
- **Job Endpoint**: POST `/api/export` returns `{ "job_id": "uuid", "status": "queued" }`.
- **Redis Queue**: Queue name `export-jobs`. Payload: `{ "job_id": "uuid", "spec": { ... }, "format": "mp4" | "gif" }`.
- **Job Status**: Status stored in PostgreSQL: `queued`, `processing`, `completed`, `failed`.
- **Object Storage**: Worker uploads files to MinIO bucket `exports` with path `exports/{job_id}.[mp4|gif]`.
- **Download Endpoint**: GET `/api/export/{job_id}` returns `{ "job_id": "uuid", "status": "completed", "download_url": "http://localhost:9000/exports/{job_id}.mp4" }` (or similar signed/public URL).

### Frontend `/render-box` ↔ Headless Render Worker
- **Route**: GET `/render-box?spec={...}` or `/render-box?job_id={uuid}` to fetch from database.
- **Clock Hooking**: React app must expose hooks or respect browser-level clock overrides (like Playwright `clock.install()`) or GSAP control flags so that the Playwright worker can advance time deterministically.

## Code Layout
- `backend/` - Python API gateway code.
- `frontend/` - React frontend code.
- `worker/` - Playwright + FFmpeg render worker.
- `docker-compose.yml` - Multi-container orchestrator.
- `tests/e2e/` - E2E tests.
