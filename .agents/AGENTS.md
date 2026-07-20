# FlowDraft Codebase Rules & Style Guidelines

This file defines guidelines and rules for working with the FlowDraft interactive diagramming and video export codebase.

## 1. Technology Stack Conventions

* **Frontend**: Built using React Flow (XYFlow), TypeScript, and CSS. Layout calculations must be performed off the main thread inside the background Web Worker running `ELKjs` to prevent UI thread blocking.
* **Backend**: FastAPI with SQLAlchemy models, PostgreSQL persistence, and Redis for the BullMQ-compatible background job queue.
* **Render Worker**: Playwright-based headless Chromium runner controlling the GSAP tick clock deterministically, taking frame screenshots, and compiling them via FFmpeg.

## 2. Technical Diagram Rendering Guidelines

* **Script Names**:
  - The main rendering script is [scripts/render_v2.py](file:///c:/projects/2dmotion-flow-dataflow/scripts/render_v2.py).
  - A compatibility wrapper is provided at [scripts/render_flowdraft_diagram.py](file:///c:/projects/2dmotion-flow-dataflow/scripts/render_flowdraft_diagram.py).
* **CLI Validation**:
  - When rendering diagrams locally, always run with `--check` or `--verify` to ensure output contracts (GIF frame counts, FPS, unique Excalidraw IDs, and non-empty motion frame-diffs) are fully validated.
* **Themes & Design**:
  - Keep node labels short (under 22 characters per line, max 2 lines for core card body) to fit in fixed visual cards.
  - Default theme is `dark`, but standard `light` and `white` must be supported.
  - Rely on the built-in icon set: `folder`, `file`, `scan`, `shield`, `db`, `hash`, `package`.

## 3. Verification & Testing Practices

* **Unit Testing**:
  - Validate compiler, schema, layout engine, and rendering pipeline by running:
    ```bash
    .\.venv\Scripts\python -m unittest tests/test_v2.py
    ```
* **E2E Testing**:
  - Validate the entire stack (FastAPI, Redis, PostgreSQL, Playwright, MinIO) in mock mode by running:
    ```bash
    python -m unittest tests.e2e.test_e2e_suite
    ```
  - In `real` mode, spin up the Docker Compose containers and set `FLOWDRAFT_E2E_MODE=real` before running the suite.
