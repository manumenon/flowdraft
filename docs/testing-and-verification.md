# FlowDraft Testing & Quality Verification Guide

FlowDraft includes a multi-tiered automated test suite covering unit tests, service integration tests, challenger stress tests, and end-to-end integration tests.

---

## 1. Test Suite Organization

```
tests/
├── test_v2.py                         # Compiler, Schema V2, Layout Engine, & Excalidraw Unit Tests
├── test_backend_api.py                # FastAPI REST Endpoints, Auth & CRUD Operations
├── test_backend_foundations.py        # Database models & security utility unit tests
├── test_worker.py                     # Playwright worker frame capture & FFmpeg compilation tests
├── test_mcp_api.py                    # Model Context Protocol tool execution & SSE tests
├── test_services_integration.py       # Redis Broker & MinIO Storage integration tests
├── test_challenger_edge_cases.py      # Spec edge cases & boundary input validation
├── test_challenger_resilience.py      # API gateway error recovery tests
├── test_challenger_worker_resilience.py # Worker recovery on invalid frames or network drops
├── test_challenger_worker_stress.py   # High concurrency export load tests
└── e2e/
    └── test_e2e_suite.py             # Full End-to-End Integration Suite (50+ assertions)
```

---

## 2. Running Core Unit Tests

Execute core compiler and schema tests:
```bash
.\.venv\Scripts\python -m unittest tests/test_v2.py
```

Execute backend API and service tests:
```bash
python -m unittest tests/test_backend_api.py
python -m unittest tests/test_worker.py
python -m unittest tests/test_mcp_api.py
```

Run all unit and integration tests in `tests/`:
```bash
python -m unittest discover -s tests -p "test_*.py"
```

---

## 3. End-to-End (E2E) Test Suite Modes

The E2E test suite (`tests.e2e.test_e2e_suite`) supports two operational modes controlled by the `FLOWDRAFT_E2E_MODE` environment variable.

### Mode 1: Mock Mode (Default)
Boots lightweight in-process HTTP and Redis servers. Bypasses external Docker container dependencies for rapid local test execution.

```bash
python -m unittest tests.e2e.test_e2e_suite
```

### Mode 2: Real Mode (Live Docker Containers)
Executes HTTP requests and queue tasks against real running Docker Compose containers (`frontend`, `backend`, `postgres`, `redis`, `minio`, `worker`).

1. Ensure the Docker Compose stack is running:
   ```bash
   docker compose up -d --build
   ```
2. Set `FLOWDRAFT_E2E_MODE=real` and execute the suite:

   - **Windows PowerShell**:
     ```powershell
     $env:FLOWDRAFT_E2E_MODE="real"
     python -m unittest tests.e2e.test_e2e_suite
     ```
   - **Linux / macOS**:
     ```bash
     export FLOWDRAFT_E2E_MODE=real
     python -m unittest tests.e2e.test_e2e_suite
     ```

---

## 4. Visual Verification Contracts (`--check` / `--verify`)

When rendering diagrams via CLI (`scripts/render_v2.py` or `scripts/render_flowdraft_diagram.py`), supply the `--verify` flag to automatically validate output quality contracts:

```bash
python scripts/render_flowdraft_diagram.py \
  --spec assets/default-spec.json \
  --outdir /tmp/output \
  --basename test_render \
  --verify
```

### Verification Checks Performed
1. **Dimensions**: Verifies output PNG preview matches canvas width/height.
2. **GIF Properties**: Verifies GIF frame count and FPS match specification.
3. **Motion Check**: Performs pixel frame-diffing across adjacent GIF frames to confirm visual flow highlights are moving.
4. **Excalidraw Format**: Verifies output `.excalidraw` file contains valid JSON, unique element IDs, and `fontFamily: 5`.
