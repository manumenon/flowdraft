# FlowDraft System Architecture & Project Specifications

This document defines the architecture, component relationships, data flow patterns, module boundaries, and interface contracts for the FlowDraft system.

---

## 1. System Architecture & Component Relationships

FlowDraft is organized as a set of decoupled services working together to provide interactive diagram editing and high-fidelity video/GIF rendering.

```
┌────────────────────────────────────────────────────────────────────────┐
│                              FRONTEND (React)                          │
│  ┌───────────────────────┐          ┌───────────────────────────────┐  │
│  │   Canvas Editor UI    │◄────────►│  GWT Web Worker (ELKjs)       │  │
│  │   (XYFlow / ReactFlow)│          │  (Synchronous Layout Engine)  │  │
│  └───────────┬───────────┘          └───────────────────────────────┘  │
│              │ (Base64 spec params)                                    │
│              ▼                                                         │
│  ┌───────────────────────┐                                             │
│  │     /render-box       │                                             │
│  │ (Read-only viewport)  │                                             │
│  └───────────▲───────────┘                                             │
└──────────────┼─────────────────────────────────────────────────────────┘
               │                                      ▲
               │ (Playwright loads page)              │ (Signed MinIO URL)
               │                                      │
┌──────────────┴──────────────────────────────────────┴──────────────────┐
│                             BACKEND SERVICES                           │
│                                                                        │
│  ┌───────────────────────┐     API Requests     ┌───────────────────┐  │
│  │  FastAPI Gateway API  │◄────────────────────►│    PostgreSQL     │  │
│  │  (Auth, Diagrams,     │                      │ (Users, Diagrams, │  │
│  │   Export Requests)    │                      │  Export Jobs)     │  │
│  └───────────┬───────────┘                      └───────────────────┘  │
│              │                                                         │
│              │ (LPUSH job payload)                                     │
│              ▼                                                         │
│  ┌───────────────────────┐                                             │
│  │     Redis Queue       │                                             │
│  │    (export-jobs)      │                                             │
│  └───────────┬───────────┘                                             │
│              │                                                         │
│              │ (BRPOP job payload)                                     │
│              ▼                                                         │
│  ┌───────────────────────┐                      ┌───────────────────┐  │
│  │ Headless Render Worker│◄────────────────────►│   MinIO Storage   │  │
│  │ (Playwright + FFmpeg) │   Upload MP4/GIF     │ (exports bucket)  │  │
│  └───────────────────────┘                      └───────────────────┘  │
└────────────────────────────────────────────────────────────────────────┘
```

### Component Details
1. **API Gateway (FastAPI)**: Serves HTTP endpoints. Handles security verification, database transactions, spec validation using the Python schema engine, and submits rendering jobs.
2. **PostgreSQL Database**: Holds schema-defined relational data for Users, Diagrams, and ExportJobs, enabling full state persistence.
3. **Redis Broker**: Connects the gateway to the worker. It hosts the `export-jobs` FIFO queue list.
4. **MinIO Object Store**: Stores generated MP4/GIF assets. Generates short-lived presigned URLs for client-side downloading.
5. **Headless Render Worker**: Polls Redis, spawns headless Chromium via Playwright, points it to the frontend `/render-box` route, manipulates the GSAP clock timeline, and captures/compiles frames.
6. **Frontend Web (React/Vite)**: Runs the React diagram editor app. Implements Web Worker-based layout calculations and the GSAP-controlled clock interface.

---

## 2. End-to-End Data Flow

The lifecycle of an export job spans multiple components in a strict, asynchronous sequence:

```
[ Client ]          [ Gateway ]          [ Redis ]          [ Worker ]          [ Playwright ]          [ MinIO ]
    │                    │                   │                  │                     │                    │
    │ 1. POST /api/auth  │                   │                  │                     │                    │
    ├───────────────────►│                   │                  │                     │                    │
    │ 2. POST /api/diag  │                   │                  │                     │                    │
    ├───────────────────►│ (Validate spec)   │                  │                     │                    │
    │                    │                   │                  │                     │                    │
    │ 3. POST /api/export│                   │                  │                     │                    │
    ├───────────────────►│──┐ 4. Create      │                  │                     │                    │
    │                    │  │   ExportJob in │                  │                     │                    │
    │                    │◄─┘   DB (queued)  │                  │                     │                    │
    │                    │                   │                  │                     │                    │
    │                    │ 5. LPUSH payload  │                  │                     │                    │
    │                    ├──────────────────►│                  │                     │                    │
    │                    │                   │                  │                     │                    │
    │                    │                   │ 6. BRPOP         │                     │                    │
    │                    │                   │◄─────────────────┤                     │                    │
    │                    │                   │                  │ 7. Update status to │                    │
    │                    │                   │                  │    "processing" in DB                    │
    │                    │                   │                  ├────────────────────┐│                    │
    │                    │                   │                  │ 8. Launch headless  │                    │
    │                    │                   │                  │    Chromium        │                     │
    │                    │                   │                  ├────────────────────►│                    │
    │                    │                   │                  │                     │ 9. Load            │
    │                    │                   │                  │                     │    /render-box?spec│                    │
    │                    │                   │                  │                     │◄───────────────────┤
    │                    │                   │                  │                     │ 10. Wait for       │
    │                    │                   │                  │                     │     layout ready   │
    │                    │                   │                  │                     ├───────────────────┐│
    │                    │                   │                  │                     │ 11. Freeze clock  ││
    │                    │                   │                  │                     │     and seek      ││
    │                    │                   │                  │                     │     frame-by-frame││
    │                    │                   │                  │                     │ 12. Pipe PNGs into │
    │                    │                   │                  │                     │     FFmpeg         │
    │                    │                   │                  │◄────────────────────┤                    │
    │                    │                   │                  │                     │                    │
    │                    │                   │                  │ 13. Upload output bytes                  │
    │                    │                   │                  ├─────────────────────────────────────────►│
    │                    │                   │                  │ 14. Get presigned GET URL                │
    │                    │                   │                  ├─────────────────────────────────────────►│
    │                    │                   │                  │◄─────────────────────────────────────────┤
    │                    │                   │                  │                     │                    │
    │                    │                   │                  │ 15. Set status to "completed" + URL      │
    │                    │                   │                  ├────────────────────┐                     │
    │                    │                   │                  │◄───────────────────┘                     │
    │ 16. GET /api/export│                   │                  │                                          │
    │     /{job_id}      │                   │                  │                                          │
    ├───────────────────►│ (Reads DB)        │                  │                                          │
    │                    │◄──────────────────┼──────────────────┼──────────────────────────────────────────┘
    │   (Download URL)   │                   │                  │
```

1. **User Authentication**: The client submits email/password credentials to `/api/auth/token` to receive a JWT access token.
2. **Diagram Spec Persistence**: The client registers a diagram by posting a canvas spec JSON to `/api/diagrams`. The gateway validates the spec dictionary structure.
3. **Submit Export Job**: The client requests an animation render by submitting the `diagram_id` (or direct `spec_override`) along with the target format (`mp4` or `gif`) to the `/api/export` endpoint.
4. **Queue Submission**: The gateway writes an `ExportJob` row to PostgreSQL with status `"queued"`. It pushes the job payload (`{job_id, spec, format}`) into the Redis list named `export-jobs` via `LPUSH`.
5. **Worker Pickup**: The worker daemon performing a blocking `BRPOP` on `export-jobs` pulls the payload. It updates the database job status to `"processing"`.
6. **Playwright Navigation**: The worker initiates an async Playwright instance, opens Chromium, and navigates to `FRONTEND_URL/render-box?spec={base64_encoded_spec}&theme={theme}`.
7. **Animation Capture Loop**: The worker waits for layout synchronization, freezes the browser-level GSAP clock, and steps through the timeline frame-by-frame. A PNG screenshot is captured at each step.
8. **FFmpeg Compilation**: The screenshot stream is written directly to the stdin pipe of an FFmpeg subprocess, compiling the frames into a `.mp4` or `.gif` file in transient storage.
9. **MinIO Persistence**: The worker uploads the compiled binary to the MinIO `exports` bucket. It then queries a short-lived presigned download URL.
10. **State Settlement**: The database job entry is updated to `"completed"`, writing the presigned `download_url`. If any step fails, the status is updated to `"failed"` with the error message.

---

## 3. Directory Layout & Module Boundaries

The code is structured as follows:

```
.
├── backend/                  # FastAPI web services and db configurations
│   ├── Dockerfile            # Container build instructions for Gateway and Worker
│   ├── requirements.txt      # Python dependencies (fastapi, sqlalchemy, playwright, etc.)
│   └── app/                  # Application core
│       ├── main.py           # Application entrypoint, routers, and CORS middleware
│       ├── models.py         # SQLAlchemy definitions for User, Diagram, and ExportJob
│       ├── schemas.py        # Pydantic schemas for request/response serialization
│       ├── worker.py         # Playwright render daemon and FFmpeg compiler
│       ├── api/              # API endpoints organized by version
│       │   ├── deps.py       # Authentication and DB session injection dependencies
│       │   └── v1/           # v1 API routers (auth, diagrams, exports)
│       └── services/         # Internal API helper services
│           ├── redis_broker.py  # LPUSH wrapper interface for Redis
│           └── storage.py       # MinIO bucket upload and URL generation client
├── frontend/                 # React frontend client
│   ├── Dockerfile            # Container build instructions for frontend SPA
│   ├── package.json          # Node dependencies (react, @xyflow/react, gsap, elkjs)
│   ├── vite.config.ts        # Vite building configuration
│   └── src/                  # React source code
│       ├── hooks/            # Custom hooks
│       │   └── useClockHook.ts  # Timeline clock interceptor hook for GSAP
│       └── workers/          # Web Workers
│           └── layout.worker.ts  # Synchronous layout calculation worker for ELKjs
├── scripts/                  # Scripts for maintenance, validation, and initialization
│   ├── wait_and_init.py      # Multi-container startup sync hook
│   └── flowdraft/            # Rendering engine core schema definition library
│       └── schema.py         # Canvas, elements, and connections schema validator
└── tests/                    # Test suites
    └── e2e/                  # End-to-end integration and mock tests
        ├── mock_services.py  # Mock HTTP and Redis environment setup
        └── test_e2e_suite.py # 50 E2E integration test cases
```

---

## 4. Interface Contracts

### Gateway ↔ Headless Worker Contract
- **Redis Queue Structure**:
  - List key: `export-jobs`.
  - Enqueue Command: `LPUSH export-jobs payload`
  - Dequeue Command: `BRPOP export-jobs timeout`
  - Payload Format (JSON):
    ```json
    {
      "job_id": "uuid-string",
      "spec": { ... },
      "format": "mp4" | "gif" | "png"
    }
    ```
- **Object Storage Bucket**:
  - Target Bucket: `exports`.
  - Object Path Name: `{job_id}.{format}` (e.g. `e890f001-ebbb-4e33-a0ae-393ea4f046b5.mp4`).
  - Presigned URL Expiration: 3600 seconds (1 hour).

### Frontend `/render-box` ↔ Headless Worker Contract
- **URL Parameters**:
  - `spec`: Base64 encoded representation of the validated diagram spec JSON.
  - `theme`: Theme choice (`"dark"`, `"light"`, or `"white"`).
- **Layout Completion Flag**:
  - The page writes `window.__LAYOUT_COMPLETE__ = true` to the global scope when the ELKjs Web Worker layout calculation finishes.
  - The worker awaits this state via `page.wait_for_function("window.__LAYOUT_COMPLETE__ === true")` before initiating frame capture.
- **GSAP Clock Control Interface**:
  - The frontend exposes a `window.__CLOCK_CONTROLLER__` object with the following interface:
    ```typescript
    interface ClockController {
      freeze: () => void;      // Pauses GSAP ticker, resets timelines to 0
      seek: (ms: number) => void; // Seeks GSAP root timeline directly to ms
      advance: (ms: number) => void; // Increments current time by ms
      unfreeze: () => void;    // Restores standard GSAP ticker loops
    }
    ```
  - If `window.__CLOCK_CONTROLLER__` is present, the worker invokes `freeze()` followed by sequential `seek(ms)` calls. If absent, it falls back to executing `window.step(delta_ms)`.
