# FlowDraft: Technical Architecture Diagram Rendering & Animation Engine

FlowDraft is a high-performance, multi-container system designed to render premium, professional technical diagrams and animate step-by-step path flows. The platform translates interactive canvas specifications into editable Excalidraw files, static PNG/SVG previews, and high-fidelity, stutter-free animated GIF/MP4 workflows.

---

## 1. Technical Overview

FlowDraft is structured as a decoupled, multi-tier microservices application composed of six main components:

1. **Frontend (React + Vite + TypeScript)**:
   - Provides an interactive canvas for editing diagram layouts using **XYFlow (React Flow)**.
   - Leverages a custom background **Web Worker running ELKjs** for collision-free hierarchy layout calculations.
   - Uses **GSAP (GreenSock Animation Platform)** with the `MotionPathPlugin` to animate telemetry pulses along path connections.
   - Exposes a dedicated, read-only viewer route at `/render-box` which isolates the animated diagram, omitting grids, handles, or toolbars for frame capture.
   
2. **API Gateway (FastAPI)**:
   - Serves as the central entry point, offering endpoints for user registration, authentication, saving/loading diagram specifications, and queueing video export requests.
   - Includes custom exception mapping (e.g., converting spec validation failures into 400 Bad Request responses) and automatic default user provisioning for testing.

3. **Database (PostgreSQL)**:
   - Stores persistence data including user profiles, hashed passwords, diagram schemas, and export job states.

4. **Redis Broker & Job Queue**:
   - Acts as the asynchronous job distributor. Incoming media export requests are enqueued as JSON payloads onto a Redis list, facilitating smooth decoupling of the HTTP gateway from CPU/GPU-intensive browser rendering.

5. **MinIO Object Storage**:
   - A containerized S3-compatible object store. Stores the compiled MP4 and GIF output files and provides secure presigned download URLs with expiration configurations.

6. **Headless Render Worker (Playwright + FFmpeg)**:
   - A Python daemon that polls Redis for export tasks.
   - Spawns headless Chromium instances via **Playwright** to load the `/render-box` route with base64 encoded diagram specs.
   - Controls the timeline deterministically by freezing the GSAP ticker and seeking through frames millisecond-by-millisecond.
   - Captures PNG screenshots and pipes them directly into **FFmpeg** to compile high-quality H.264 MP4 videos or optimized 256-color palette GIFs.

---

## 2. Docker Compose Deployment

The quickest way to spin up the entire FlowDraft stack (including database migrations and bucket setup) is using Docker Compose.

### Prerequisites
- Docker and Docker Compose installed.
- Ensure ports `8000`, `3000`, `9000`, `9001`, and `5432` are not occupied.

### Command Execution
To build and start all containers in detached mode:
```bash
docker compose up -d --build
```

### Startup Initialization Mechanism
The stack uses a specialized **wait-and-init** script (`scripts/wait_and_init.py`) inside the `init-services` container to guarantee clean startup sequencing:
- **Port Probing**: The script checks raw TCP socket connections to confirm PostgreSQL and MinIO are accepting traffic.
- **Database Migrations**: Once PostgreSQL is reachable, it runs the SQLAlchemy table migrations to initialize `users`, `diagrams`, and `export_jobs` tables.
- **Bucket Creation**: It verifies the existence of the `exports` bucket in MinIO, creating it if missing.
- **Dependency Ordering**: The `backend` and `worker` services declare a `depends_on` condition requiring `init-services` to complete successfully, preventing them from boot-looping on uninitialized databases or storage.

To stop and tear down the stack (retaining persistent volumes):
```bash
docker compose down
```

To clean up persistent database and object storage volumes:
```bash
docker compose down -v
```

---

## 3. Local Running (Development Mode)

If you wish to run the backend and worker services locally outside of Docker, follow these instructions.

### Prerequisites
- **Python**: Python 3.10+ (recommend creating a virtual environment).
- **Node.js**: Node 18+ for building the React frontend.
- **FFmpeg**: Must be installed and available on your system `PATH`.
- **Playwright**: Browser binaries must be installed (`playwright install chromium`).
- **Redis & PostgreSQL**: Running instances configured via environment variables.

### Environment Setup
Create a `.env` file in the root directory or set the following environment variables:
```bash
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/flowdraft
REDIS_URL=redis://localhost:6379/0
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
FRONTEND_URL=http://localhost:3000
```

### Steps to Run

1. **Initialize Database and Storage**:
   ```bash
   python -m scripts.wait_and_init
   ```

2. **Start the API Gateway (FastAPI)**:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```
   *(Run from the `backend` directory, or append backend to your python path)*

3. **Start the React Frontend**:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

4. **Start the Render Worker**:
   ```bash
   python -m app.worker
   ```
   *(Run from the `backend` directory or project root with backend/app on python path)*

---

## 4. Testing Instructions

FlowDraft includes an extensive test suite comprising 50 E2E and integration test cases covering authentication, diagram CRUD operations, canvas schema validation, and job queuing.

### Running with E2E Mock Environment (Default)
The E2E test suite defaults to a mock environment which boots in-process HTTP and Redis servers, bypassing external docker dependencies:
```bash
python -m unittest tests.e2e.test_e2e_suite
```

### Running Against Live Container Environment
To execute E2E tests against the real containerized stack:
1. Spin up the containers:
   ```bash
   docker compose -f docker-compose.yml up -d --build
   ```
2. Configure your shell to run in `real` mode and execute unittest:
   - **Windows Powershell**:
     ```powershell
     $env:FLOWDRAFT_E2E_MODE="real"
     python -m unittest tests.e2e.test_e2e_suite
     ```
   - **Windows CMD**:
     ```cmd
     set FLOWDRAFT_E2E_MODE=real
     python -m unittest tests.e2e.test_e2e_suite
     ```
   - **Linux / macOS**:
     ```bash
     export FLOWDRAFT_E2E_MODE=real
     python -m unittest tests.e2e.test_e2e_suite
     ```

---

## 5. Directory Layout

- `backend/` - FastAPI gateway codebase, security rules, dependency injection, and MinIO clients.
- `backend/app/worker.py` - Playwright browser automation, timeline clock manipulation, and FFmpeg media compiler.
- `frontend/` - React SPA (Vite, TypeScript, React Flow, GSAP).
- `frontend/src/workers/layout.worker.ts` - GWT ELKjs layout synchronization worker.
- `scripts/` - Administrative and startup hooks, including the schema validation and database initializers.
- `tests/e2e/` - End-to-end integration and mock harness scripts.
