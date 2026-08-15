# ---------------------------------------------------------------------------
# Stage 1: build the TypeScript layout engine's self-contained CLI bundle
# (frontend/dist-cli/layout-cli.cjs). backend/app/services/ts_layout_bridge.py
# subprocess-invokes this bundle at runtime for the compile_diagram MCP tool
# -- see that module's docstring for why there's no pure-Python fallback.
# ---------------------------------------------------------------------------
FROM node:20-slim AS frontend-builder

WORKDIR /build/frontend

# Copy manifests first so `npm ci` is cached independently of source changes.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build:layout-cli

# ---------------------------------------------------------------------------
# Stage 2: the backend runtime image
# ---------------------------------------------------------------------------
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

WORKDIR /app

# Install system dependencies, including a Node.js runtime: this image
# previously had no Node.js at all, which meant the legacy
# scripts/flowdraft/elk_layout.py ELK subprocess bridge was silently falling
# back to a lower-quality pure-Python layout in production, undetected
# (_find_node() -> None -> route_with_elk() -> False -> caller falls back
# quietly). ts_layout_bridge.py, the bridge that now backs compile_diagram,
# has no such fallback -- it raises TsLayoutError with a clear message when
# "node" isn't found on PATH (also logged server-side) instead of silently
# producing different output, so skipping this step would turn every
# compile_diagram call into a loud, immediate error rather than a quiet
# wrong answer, but it would still be broken. Installing nodejs here is what
# actually makes the bridge work end-to-end in the deployed container.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    nodejs \
    && rm -rf /var/lib/apt/lists/*

# Copy backend requirements first to leverage Docker cache
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# Copy backend source and scripts
COPY backend /app/backend
COPY scripts /app/scripts

# Copy the bundled TS layout CLI built in the frontend-builder stage above.
# ts_layout_bridge.py's _find_bundle() looks for it at exactly
# <repo_root>/frontend/dist-cli/layout-cli.cjs by default (repo_root here
# being /app, the first ancestor of this file containing a "frontend" dir --
# the same relative layout backend/scripts already have in this image),
# mirroring how elk_bridge.js is located relative to elk_layout.py's own
# directory.
COPY --from=frontend-builder /build/frontend/dist-cli/layout-cli.cjs /app/frontend/dist-cli/layout-cli.cjs

# Set workdir to backend to match uvicorn module path
WORKDIR /app/backend

# Expose API port
EXPOSE 8000

# Start app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
