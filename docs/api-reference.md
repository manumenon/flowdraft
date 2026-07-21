# FlowDraft API Gateway Reference & FastMCP Protocol

This document serves as the complete technical reference for the **FlowDraft Gateway REST API** and **Model Context Protocol (MCP)** integration.

All REST endpoints are available under the `/api/v1/` prefix (with `/api/` aliases maintained for backwards compatibility).

---

## 1. Authentication & Security

FlowDraft uses **OAuth2 with Password Bearer Tokens (JWT)**.

- **Header Format**: `Authorization: Bearer <access_token>`
- **Token Secret**: Configured via `SECRET_KEY` in `.env`.
- **Expiration**: Default 30 minutes (`ACCESS_TOKEN_EXPIRE_MINUTES`).

### `POST /api/v1/auth/signup`
Registers a new user account.
- **Request Body**:
  ```json
  {
    "email": "user@example.com",
    "password": "strongpassword123"
  }
  ```
- **Response**: `201 Created`
  ```json
  {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "email": "user@example.com",
    "is_active": true,
    "created_at": "2026-07-21T20:00:00Z"
  }
  ```

### `POST /api/v1/auth/token`
Exchanges credentials for an OAuth2 JWT access token. Form-encoded body (`application/x-www-form-urlencoded`).
- **Request Parameters**:
  - `username`: `user@example.com`
  - `password`: `strongpassword123`
- **Response**: `200 OK`
  ```json
  {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer"
  }
  ```

---

## 2. Diagram Repository Management (`/api/v1/diagrams`)

Requires authentication header.

### `POST /api/v1/diagrams`
Creates and validates a new diagram specification.
- **Request Body**:
  ```json
  {
    "title": "Data Pipeline Architecture",
    "description": "Kafka to PostgreSQL flow",
    "theme": "dark",
    "spec": {
      "version": "2.0",
      "elements": [...]
    }
  }
  ```
- **Response**: `201 Created` returning the created `DiagramResponse` object.

### `GET /api/v1/diagrams`
Lists all diagrams owned by the authenticated user.
- **Response**: `200 OK` array of `DiagramResponse` objects.

### `GET /api/v1/diagrams/{id}`
Retrieves a specific diagram by UUID.
- **Response**: `200 OK` or `404 Not Found` / `403 Forbidden`.

### `PUT /api/v1/diagrams/{id}`
Updates a diagram's title, description, theme, or JSON spec. If `spec` is present, it is re-validated against the FlowDraft V2 schema.
- **Response**: `200 OK` updated `DiagramResponse` object.

### `DELETE /api/v1/diagrams/{id}`
Deletes a diagram by UUID.
- **Response**: `204 No Content`.

---

## 3. Asynchronous Export Job Queue (`/api/v1/export`)

Handles video (MP4), animated GIF, and static PNG diagram exports.

### `POST /api/v1/export`
Submits a diagram render job to the background Redis queue.
- **Request Body** (Option A - DB Diagram Reference):
  ```json
  {
    "diagram_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "format": "mp4"
  }
  ```
- **Request Body** (Option B - Inline Spec Override):
  ```json
  {
    "spec_override": {
      "title": { "prefix": "Realtime", "highlight": "Stream" },
      "elements": [...]
    },
    "format": "gif"
  }
  ```
- **Response**: `200 OK`
  ```json
  {
    "job_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
    "status": "queued"
  }
  ```

### `GET /api/v1/export/{job_id}`
Checks status of an export job (`queued`, `processing`, `completed`, `failed`).
- **Response**: `200 OK`
  ```json
  {
    "job_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
    "status": "completed",
    "download_url": "/api/v1/export/9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d/download",
    "error_message": null
  }
  ```

### `GET /api/v1/export/{job_id}/download`
Streams the compiled MP4/GIF/PNG file directly from MinIO object storage. Publicly accessible by UUID to support direct browser downloads.

### `GET /api/v1/export/{job_id}/spec`
Internal/Worker endpoint returning the resolved JSON spec for headless rendering, bypassing long query parameter limits.

---

## 4. Model Context Protocol (MCP) Server

Mounted at `/api/v1/mcp` and `/api/mcp`. FastMCP framework providing Server-Sent Events (SSE) protocol access for AI tool execution, resources, and prompt templates.

### Authentication
Include the `X-MCP-API-Key` HTTP header or `?api_key=` URL parameter matching one of the keys in `settings.MCP_API_KEYS`.

### MCP Endpoints
- `GET /api/v1/mcp/sse`: Connects to FastMCP SSE transport stream.
- `POST /api/v1/mcp/messages/`: Sends MCP tool calls and JSON-RPC messages.

---

### Available MCP Tools

#### 1. `compile_diagram(spec: dict) -> str`
Validates a JSON spec against the FlowDraft V2 schema without queueing an export.
- **Returns**: Summary string with title, element count, connection count, and theme.

#### 2. `validate_diagram_spec(spec: dict) -> str`
Performs deep structural validation of a spec and returns JSON string with metrics, valid status, and warning array.

#### 3. `list_templates() -> str`
Lists built-in starter diagram templates (`dataflow`, `microservices`, `auth_flow`).

#### 4. `get_template(name: str) -> str`
Retrieves the complete JSON spec string for a starter template by name.

#### 5. `list_saved_diagrams(limit: int = 10) -> str`
Queries saved diagrams stored in PostgreSQL for the MCP system account (`mcp_system_user@flowdraft.local`).

#### 6. `get_saved_diagram(diagram_id: str) -> str`
Retrieves a stored diagram spec by UUID from the database.

#### 7. `save_diagram(title: str, spec: dict, description: str = None, theme: str = "dark") -> str`
Validates and persists a diagram specification into PostgreSQL.

#### 8. `delete_saved_diagram(diagram_id: str) -> str`
Deletes a diagram by UUID from PostgreSQL.

#### 9. `trigger_export(spec: dict, format: str = "mp4") -> str`
Enqueues an export job for headless rendering under system account `mcp_system_user@flowdraft.local`.
- **Returns**: `"Export job triggered successfully. job_id: <uuid>"`

#### 10. `get_export_status(job_id: str) -> str`
Queries execution status and returns both proxy download link and MinIO presigned URL upon completion.

---

### Available MCP Resources

#### 1. `flowdraft://schema/v2`
Exposes the FlowDraft V2 schema rules, valid element types (`card`, `diamond`, `panel`, `input`, `label`, `group`, `cylinder`, `cloud`), ports, themes, and icon sets as a readable resource.

#### 2. `flowdraft://templates/default`
Exposes the default real-time dataflow engine architecture spec JSON.

---

### Available MCP Prompts

#### 1. `create_architecture_diagram(topic: str)`
Returns a guided prompt template instructing AI models how to structure a valid FlowDraft V2 diagram spec for a given topic.

---

## 5. Health & Diagnostics

### `GET /health`
Validates connectivity to both Redis and PostgreSQL.
- **Healthy Response**: `200 OK` `{"status": "healthy"}`
- **Unhealthy Response**: `500 Internal Server Error`
