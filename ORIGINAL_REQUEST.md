# Original User Request

## Initial Request — 2026-07-16T01:32:20Z

An interactive canvas layout and architecture diagram animator that lets users design pipelines and export animated GIF/MP4 videos of them.

Working directory: C:\projects\2dmotion-flow-dataflow
Integrity mode: benchmark

## Requirements

### R1. Frontend Interactive Canvas & Layout Engine
- Build an interactive editor canvas using React Flow (XYFlow) with TypeScript.
- Nodes should render as customizable React DOM components, and edges as SVG curves.
- Use ELKjs (Eclipse Layout Kernel) inside a background Web Worker to compute collision-free layouts off the main DOM thread.
- Animate telemetry packets/icons moving along edge paths using GSAP (GreenSock) with the MotionPathPlugin.
- A clean, read-only viewer route (`/render-box`) that renders only the pure animated architecture diagram without gridlines, toolbars, or editing handles.

### R2. Backend Orchestration & Message Broker
- A Python API gateway (e.g., FastAPI) handling diagram schema storage, authentication, and exporting jobs.
- Use PostgreSQL (containerized) to store user and diagram schemas.
- A BullMQ (Redis-backed) job queue or Python equivalent (like Celery/RQ, or using BullMQ if matching Node workers, or a standard Python Redis-backed queue compatible with the worker) to manage video generation jobs asynchronously. Since the worker is Node.js/Playwright/BullMQ, a Redis-backed message queue that bridges Python and Node (like BullMQ compatible Python client, or a shared Redis queue protocol) is preferred, or the team can design the queue mechanism cleanly.

### R3. Headless Rendering & Encoding Worker
- A worker that runs Playwright to load the `/render-box` viewer route, freezes the browser clock, advances the GSAP timeline in deterministic steps (e.g. 16.67ms), and captures PNG screenshots.
- Use FFmpeg to compile captured frames into MP4 (libx264) or optimized 256-color GIF (using palettegen/paletteuse filters).
- Upload completed exports to a local containerized MinIO S3-compatible service and update the job status with a download link.

### R4. Multi-Container Docker Architecture
- Define a Docker Compose setup orchestrating:
  - Frontend (React + Vite + TS)
  - API Gateway (Python)
  - PostgreSQL Database
  - Redis (Queue backend)
  - MinIO (S3-compatible object storage)
  - Headless Render Worker (Playwright + FFmpeg)

## Acceptance Criteria

### Diagram Editing & Layout
- [ ] Users can add, connect, and position nodes in the editor.
- [ ] Layout engine calculates coordinates in a Web Worker without locking the UI.
- [ ] Animated packets flow along SVG paths smoothly.

### Job Orchestration & Storage
- [ ] Export requests to `/api/export` generate a job ID and queue the task in Redis.
- [ ] The Render Worker picks up the job, launches Playwright, captures frames, and compiles them via FFmpeg.
- [ ] Output files (MP4/GIF) are successfully uploaded to MinIO and accessible via a signed/public downloadable URL.
- [ ] All containers spin up successfully via `docker compose up`.

## Follow-up — 2026-07-16T19:51:59Z

Update the project documentation to match our implemented multi-container architecture and GWT Web Worker layout engine.

Working directory: c:\projects\2dmotion-flow-dataflow
Integrity mode: development

## Requirements

### R1. Developer README (README.md and PROJECT.md)
- Update/create `README.md` and `PROJECT.md` to comprehensively explain the architecture of the project.
- Document all containers and services: PostgreSQL database, Redis queue, MinIO object storage, FastAPI gateway, React Flow frontend, and Playwright worker.
- Provide clear local running, testing, and Docker Compose deployment instructions.

### R2. API Reference Guide (API_REFERENCE.md)
- Create or update the API reference detailing all endpoints exposed by the Python API gateway (e.g., authentication, diagram schema storage, and export job queue).
- Detail the exact JSON schemas for saving diagrams and requesting video export.
- Document the state transitions of the export job queue.

### R3. Web Worker & Playwright Setup Guide (TROUBLESHOOTING.md)
- Detail how the ELKjs GWT layout engine is loaded synchronously inside the Web Worker thread using message intercepting.
- Document the headless Playwright capture worker environment, dependencies (like Chromium, FFmpeg), and the clock freeze/advance mechanism.
- Provide troubleshooting steps for layout overlapping or rendering failures.

## Acceptance Criteria

### Documentation Coverage
- [ ] `README.md`, `PROJECT.md`, `API_REFERENCE.md`, and `TROUBLESHOOTING.md` are updated or created in the project repository.
- [ ] Documentation includes complete, non-placeholder instructions for launching the stack with `docker compose up --build`.
- [ ] API guide defines exact JSON schemas for saving schemas and requesting MP4/GIF exports.
- [ ] Web worker layout section explains the custom GWT worker interception synchronization mechanism.

### Documentation Quality
- [ ] All files are formatted in clean Markdown with zero "TBD" or placeholder sections.
