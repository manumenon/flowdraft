# Deployment, Operations, and Configuration Guide

This guide details containerized deployment, environment setup, database initialization hooks, object storage policies, and operational troubleshooting for **FlowDraft**.

---

## 1. Multi-Container Docker Compose Stack

The full FlowDraft platform runs as a 6-container decoupled stack managed via `docker-compose.yml`:

| Service | Container Name | Port Mapping | Description |
| :--- | :--- | :--- | :--- |
| `frontend` | `flowdraft-frontend` | `3000:80` | React Nginx static web application. |
| `backend` | `flowdraft-backend` | `8000:8000` | FastAPI Gateway REST & FastMCP API. |
| `postgres` | `flowdraft-postgres` | `5432:5432` | PostgreSQL database storing users, diagrams, and jobs. |
| `redis` | `flowdraft-redis` | `6379:6379` | Redis message broker & job queue (`export-jobs`). |
| `minio` | `flowdraft-minio` | `9000:9000`, `9001:9001` | MinIO S3 object store & web console. |
| `init-services` | `flowdraft-init` | Internal | Ephemeral startup container running DB migrations & MinIO bucket setup. |
| `worker` | `flowdraft-worker` | Internal | Playwright + FFmpeg media render daemon. |

---

## 2. Startup Sequence & Orchestration (`scripts/wait_and_init.py`)

To prevent microservices from boot-looping on uninitialized databases or object stores, startup dependency ordering is enforced via `init-services`:

1. **Port Probing**: Raw TCP socket checks verify PostgreSQL (`5432`) and MinIO (`9000`) are accepting network connections.
2. **Database Schema Migration**: Executes SQLAlchemy `Base.metadata.create_all()` to create `users`, `diagrams`, and `export_jobs` tables.
3. **Storage Bucket Provisioning**: Verifies the `exports` bucket exists in MinIO; creates it if missing.
4. **Service Launch**: `backend` and `worker` services wait on `init-services` with `condition: service_completed_successfully`.

```bash
# Spin up complete stack
docker compose up -d --build

# Inspect logs across all services
docker compose logs -f

# Inspect specific worker logs
docker compose logs -f worker
```

---

## 3. Environment Variables Reference (`.env`)

Configure system variables in `.env` at the root of the project:

```bash
# Gateway & Security
SECRET_KEY=supersecretjwtkey_replace_in_production
ACCESS_TOKEN_EXPIRE_MINUTES=30
FRONTEND_URL=http://localhost:3000

# PostgreSQL Database
DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/flowdraft

# Redis Broker
REDIS_URL=redis://redis:6379/0

# MinIO S3 Object Storage
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET_NAME=exports
MINIO_SECURE=false

# Model Context Protocol Security Keys
MCP_API_KEYS=default_mcp_key_123,dev_mcp_key_456
```

---

## 4. Teardown & Maintenance Operations

### Stop Containers (Preserve Storage Volumes)
```bash
docker compose down
```

### Reset System & Wipe All Persistent Volumes
```bash
docker compose down -v
```

### Manual Database / Storage Initialization (Non-Docker Local Dev)
```bash
python -m scripts.wait_and_init
```

---

## 5. Troubleshooting & Health Checking

### System Health Endpoint
Query `GET http://localhost:8000/health`:
- `status: "healthy"` indicates both Redis and PostgreSQL connections are functional.

### Worker Diagnostics
If export jobs remain in `queued` status:
1. Verify Redis is running: `docker compose exec redis redis-cli ping` (should respond `PONG`).
2. Inspect worker logs: `docker compose logs worker`.
3. Check FFmpeg availability inside worker: `docker compose exec worker ffmpeg -version`.
