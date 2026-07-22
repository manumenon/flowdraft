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

### Ready-to-Use Client Configurations (`docs/mcp_config.json`)
Client configuration snippets for **Cursor**, **Claude Desktop**, and **Antigravity (AGY)** are available in `docs/mcp_config.json`:

```json
{
  "cursor": {
    "mcpServers": {
      "flowdraft": {
        "url": "http://localhost:8000/api/v1/mcp/sse",
        "transport": "sse",
        "headers": {
          "X-MCP-API-Key": "default-mcp-key"
        }
      }
    }
  },
  "claude_desktop": {
    "mcpServers": {
      "flowdraft": {
        "url": "http://localhost:8000/api/v1/mcp/sse?api_key=default-mcp-key",
        "transport": "sse"
      }
    }
  },
  "antigravity": {
    "mcpServers": {
      "flowdraft": {
        "url": "http://localhost:8000/api/v1/mcp/sse",
        "transport": "sse",
        "headers": {
          "X-MCP-API-Key": "default-mcp-key"
        }
      }
    }
  }
}
```

---

## 3. Step-by-Step AI Agent Flow for Creating Diagrams

External AI agents should follow this 7-step interaction workflow to create, validate, and export technical architecture diagrams using FlowDraft MCP tools:

1. **Connect & Authenticate**:
   - Establish SSE connection to `http://localhost:8000/api/v1/mcp/sse` passing `X-MCP-API-Key` or `api_key` query param.
2. **Retrieve Starter Templates**:
   - Call `list_templates()` to list available starter templates (`dataflow`, `microservices`, `auth_flow`).
   - Call `get_template(name="dataflow")` to retrieve the base specification JSON.
3. **Customize Spec**:
   - Modify elements, titles, icons, and connection flows according to user requirements while adhering to the schema rules from resource `flowdraft://schema/v2`.
4. **Validate Spec**:
   - Call `validate_diagram_spec(spec)` to ensure top-level version `2.0`, valid element types (`card`, `input`, `diamond`, `cylinder`), and matching connection target IDs.
5. **Compile Spec**:
   - Call `compile_diagram(spec)` to invoke the IR layout engine and obtain node positions, element bounding boxes, canvas dimensions, and routing paths.
6. **Trigger Export**:
   - Call `trigger_export(spec, format="gif")` (or `"png"`, `"mp4"`) to submit the export job to the render queue.
   - Receive the JSON response containing `job_id` and status (`queued`).
7. **Poll Status & Fetch Output**:
   - Poll `get_export_status(job_id)` until status transitions to `completed`.
   - Retrieve `download_url` (`/api/v1/export/{job_id}/download`), presigned S3 URL, and file size metadata.

---

## 4. Tool Reference

FlowDraft exposes **10 AI-callable tools**:

### 1. `compile_diagram`
- **Parameters**: `spec` (dict, required)
- **Description**: Validates and normalises a diagram spec JSON, running the FlowDraft IR compiler and layout engine.
- **Return Value**: Structured JSON string containing status, title, version, theme, canvas dimensions, bounding box (`min_x`, `min_y`, `max_x`, `max_y`, `width`, `height`), node list with `(x, y, width, height)` coordinates, and connection routing points.

### 2. `validate_diagram_spec`
- **Parameters**: `spec` (dict, required)
- **Description**: Deep structural validation of a diagram spec.
- **Return Value**: Structured JSON string detailing valid status, version, theme, element count, connection count, canvas dimensions, FPS, duration, and structural warnings.

### 3. `list_templates`
- **Parameters**: None
- **Description**: Lists built-in starter diagram templates (`dataflow`, `microservices`, `auth_flow`) with descriptions and visual themes.
- **Return Value**: Structured JSON object containing templates array.

### 4. `get_template`
- **Parameters**: `name` (string, required)
- **Description**: Fetches the complete JSON spec for a starter template (`dataflow`, `microservices`, `auth_flow`).
- **Return Value**: Complete starter spec JSON string.

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
- **Return Value**: Structured JSON string containing `status`, `diagram_id`, `title`, and timestamps.

### 8. `delete_saved_diagram`
- **Parameters**: `diagram_id` (string UUID, required)
- **Description**: Deletes a diagram by UUID from PostgreSQL.
- **Return Value**: Structured JSON string containing `status` and `diagram_id`.

### 9. `trigger_export`
- **Parameters**: `spec` (dict, required), `format` (string: "mp4", "gif", or "png", default: "gif")
- **Description**: Submits a diagram spec to the Redis queue (`export-jobs`) for Playwright/FFmpeg rendering.
- **Return Value**: Structured JSON string containing `status`, `job_id`, and `format`.

### 10. `get_export_status`
- **Parameters**: `job_id` (string UUID, required)
- **Description**: Queries execution status (`queued`, `processing`, `completed`, `failed`).
- **Return Value**: Structured JSON string containing `job_id`, `status`, `download_url` (`/api/v1/export/{job_id}/download`), `presigned_url`, `error_message`, and `file_size` (bytes).

---

## 5. MCP Resources

FlowDraft exposes readable MCP resources for AI contextual grounding:

### 1. `flowdraft://schema/v2`
Provides V2 schema rules, supported node types (`card`, `diamond`, `panel`, `input`, `label`, `group`, `cylinder`, `cloud`), ports (`top`, `bottom`, `left`, `right`), themes (`dark`, `light`, `white`), icons (`folder`, `file`, `scan`, `shield`, `db`, `hash`, `package`), and copy guidelines.

### 2. `flowdraft://templates/default`
Exposes the default real-time dataflow engine diagram specification JSON.

---

## 6. MCP Prompts

### `create_architecture_diagram`
- **Arguments**: `topic` (string, default: "Distributed System Architecture")
- **Description**: Returns a structured prompt template guiding an AI model on how to generate valid FlowDraft V2 diagram specifications.
