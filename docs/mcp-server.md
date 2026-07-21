# FlowDraft Model Context Protocol (MCP) Guide

FlowDraft embeds a native **Model Context Protocol (MCP)** server built on **FastMCP**. This server enables AI assistants (such as Claude Desktop, Antigravity, Cursor, or custom LLM agents) to programmatically compile diagram specs, perform structural schema validation, inspect starter templates, manage diagram persistence in PostgreSQL, and trigger asynchronous MP4/GIF/PNG rendering jobs via Server-Sent Events (SSE).

---

## 1. FastMCP Server Overview & Endpoints

The MCP server is mounted inside the FastAPI Gateway API under `/api/v1/mcp` and `/api/mcp`.

| Endpoint | Protocol | Description |
| :--- | :--- | :--- |
| `GET /api/v1/mcp/sse` | SSE (Server-Sent Events) | Establishes the persistent SSE connection stream for JSON-RPC messages. |
| `POST /api/v1/mcp/messages/` | HTTP POST | Receives tool invocations, resource queries, and prompt requests from the MCP client. |
| `GET /api/v1/mcp/health` | HTTP GET | Health check returning `{"status": "healthy"}`. |

---

## 2. Authentication & Configuration

Access to the MCP server is protected by API key authorization.

### Environment Variable Setup (`.env`)
Set comma-separated allowed keys in `.env`:
```bash
MCP_API_KEYS=default-mcp-key,client-key-production-123
```

### Passing API Keys
MCP clients must provide an authorized key using either:
1. **HTTP Header**: `X-MCP-API-Key: client-key-production-123`
2. **URL Query Parameter**: `http://localhost:8000/api/v1/mcp/sse?api_key=client-key-production-123`

---

## 3. Tool Reference

FlowDraft exposes **10 AI-callable tools**:

### 1. `compile_diagram`
- **Parameters**: `spec` (dict, required)
- **Description**: Validates and normalises a diagram spec JSON against the V2 schema.
- **Return Value**: Summary string containing title, element count, connection count, and active theme.

### 2. `validate_diagram_spec`
- **Parameters**: `spec` (dict, required)
- **Description**: Deep structural validation of a diagram spec.
- **Return Value**: Pretty-printed JSON string detailing valid status, version, theme, element count, connection count, canvas dimensions, FPS, duration, and structural warnings.

### 3. `list_templates`
- **Parameters**: None
- **Description**: Lists built-in starter diagram templates.
- **Return Value**: JSON string containing starter templates (`dataflow`, `microservices`, `auth_flow`) with element counts and themes.

### 4. `get_template`
- **Parameters**: `name` (string, required)
- **Description**: Fetches the complete JSON spec for a starter template (`dataflow`, `microservices`, `auth_flow`).
- **Return Value**: Complete spec JSON string.

### 5. `list_saved_diagrams`
- **Parameters**: `limit` (integer, default: 10)
- **Description**: Lists diagrams stored in PostgreSQL under system account `mcp_system_user@flowdraft.local`.
- **Return Value**: JSON array of diagram metadata (id, title, description, theme, updated_at).

### 6. `get_saved_diagram`
- **Parameters**: `diagram_id` (string UUID, required)
- **Description**: Fetches a stored diagram spec by UUID from PostgreSQL.
- **Return Value**: Diagram object JSON string.

### 7. `save_diagram`
- **Parameters**: `title` (string, required), `spec` (dict, required), `description` (string, optional), `theme` (string, default: "dark")
- **Description**: Validates and persists a diagram spec into PostgreSQL under system account `mcp_system_user@flowdraft.local`.
- **Return Value**: Confirmation string with assigned `diagram_id`.

### 8. `delete_saved_diagram`
- **Parameters**: `diagram_id` (string UUID, required)
- **Description**: Deletes a diagram by UUID from PostgreSQL.
- **Return Value**: Deletion confirmation string.

### 9. `trigger_export`
- **Parameters**: `spec` (dict, required), `format` (string: "mp4", "gif", or "png", default: "mp4")
- **Description**: Submits a diagram spec to the Redis queue (`export-jobs`) for Playwright/FFmpeg rendering.
- **Return Value**: Confirmation string containing queued `job_id`.

### 10. `get_export_status`
- **Parameters**: `job_id` (string UUID, required)
- **Description**: Queries execution status (`queued`, `processing`, `completed`, `failed`).
- **Return Value**: Status summary string containing both the backend proxy URL (`/api/v1/export/{job_id}/download`) and MinIO S3 presigned URL upon completion.

---

## 4. MCP Resources

FlowDraft exposes readable MCP resources for AI contextual grounding:

### 1. `flowdraft://schema/v2`
Provides V2 schema rules, supported node types (`card`, `diamond`, `panel`, `input`, `label`, `group`, `cylinder`, `cloud`), ports (`top`, `bottom`, `left`, `right`), themes (`dark`, `light`, `white`), icons (`folder`, `file`, `scan`, `shield`, `db`, `hash`, `package`), and copy guidelines.

### 2. `flowdraft://templates/default`
Exposes the default real-time dataflow engine diagram specification JSON.

---

## 5. MCP Prompts

### `create_architecture_diagram`
- **Arguments**: `topic` (string, default: "Distributed System Architecture")
- **Description**: Returns a structured prompt template guiding an AI model on how to generate valid FlowDraft V2 diagram specifications.

---

## 6. Client Configuration Example

To connect an SSE-compatible MCP client (e.g. Claude Desktop or custom agent runner):

```json
{
  "mcpServers": {
    "flowdraft": {
      "url": "http://localhost:8000/api/v1/mcp/sse?api_key=default-mcp-key",
      "transport": "sse"
    }
  }
}
```
