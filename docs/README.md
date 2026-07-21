# FlowDraft Documentation Hub

Welcome to the official documentation for **FlowDraft**, a high-performance, multi-tier system for rendering and animating technical architecture and process diagrams. FlowDraft converts JSON diagram specifications into interactive React Flow canvases, editable Excalidraw files, static PNG/SVG images, and stutter-free animated GIF and H.264 MP4 videos.

---

## 📚 Documentation Directory

| Guide | Description | Target Audience |
| :--- | :--- | :--- |
| 🏗️ **[System Architecture](file:///c:/projects/2dmotion-flow-dataflow/docs/architecture.md)** | Deep dive into the 6-tier microservices architecture, data flow, Redis job queue, and Playwright rendering worker. | System Architects, Backend Engineers |
| 🔌 **[API Reference](file:///c:/projects/2dmotion-flow-dataflow/docs/api-reference.md)** | Comprehensive REST API endpoint definitions, request/response schemas, JWT auth, and Model Context Protocol (MCP) tool integration. | Integrators, API Consumers |
| 🤖 **[MCP Server Guide](file:///c:/projects/2dmotion-flow-dataflow/docs/mcp-server.md)** | Complete guide to FastMCP server tools, resources, prompts, SSE transport, and AI client configuration. | AI Engineers, LLM Integrators |
| 🎨 **[Rendering Engine](file:///c:/projects/2dmotion-flow-dataflow/docs/rendering-engine.md)** | Technical reference for `scripts/flowdraft` Python engine, JSON Spec V2 format, ELK/Graphviz layout routing, text fitting, and CLI tools. | Diagram Designers, Core Engine Developers |
| 💻 **[Frontend Guide](file:///c:/projects/2dmotion-flow-dataflow/docs/frontend-guide.md)** | Overview of the React 18 / Vite / TypeScript single page app, off-thread Web Worker layout, GSAP animation clock, and `/render-box` route. | Frontend Developers, UI Designers |
| 🚀 **[Deployment & Operations](file:///c:/projects/2dmotion-flow-dataflow/docs/deployment-and-operations.md)** | Containerized Docker Compose setup, environment variable configuration, MinIO S3 object storage policies, and startup orchestration. | DevOps, SREs, System Administrators |
| 🧪 **[Testing & Verification](file:///c:/projects/2dmotion-flow-dataflow/docs/testing-and-verification.md)** | E2E and unit testing framework guide, mock vs. real containerized execution modes, visual diffing, and output verification contracts. | QA Engineers, Test Automation Developers |

---

## ⚡ Quick Navigation & Command Reference

### Local Development Quick Start
```bash
# 1. Initialize DB migrations and MinIO S3 buckets
python -m scripts.wait_and_init

# 2. Run API Gateway (from backend directory)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 3. Run React Frontend (from frontend directory)
npm run dev

# 4. Start Render Worker Daemon (from project root)
python -m app.worker
```

### Docker Compose Multi-Container Stack
```bash
# Spin up all 6 services with volume persistence
docker compose up -d --build

# Run End-to-End Test Suite against live stack
$env:FLOWDRAFT_E2E_MODE="real"
python -m unittest tests.e2e.test_e2e_suite
```

### CLI Diagram Rendering
```bash
# Render diagram spec to PNG, GIF, and Excalidraw with contract verification
python scripts/render_flowdraft_diagram.py \
  --spec assets/default-spec.json \
  --outdir output \
  --basename arch_diagram \
  --verify
```

---

## 🛠️ System Technology Stack

- **Frontend**: React 18, Vite, TypeScript, XYFlow (React Flow), GSAP (`MotionPathPlugin`), Web Worker with `ELKjs`.
- **API Gateway**: FastAPI, Pydantic v2, Async SQLAlchemy 2.0, PostgreSQL (Asyncpg), OAuth2 with JWT.
- **Queue & Broker**: Redis list queue (`export-jobs`) with BullMQ-compatible JSON message structure.
- **Render Worker**: Async Python Playwright (Headless Chromium), GSAP clock freezing (`window.__CLOCK_CONTROLLER__`), FFmpeg image2pipe media encoder.
- **Object Storage**: MinIO S3-compatible object store with presigned download URL generation.
- **Protocol Extensions**: Model Context Protocol (FastMCP) with SSE transport (`/api/v1/mcp`).
