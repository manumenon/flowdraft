import os
import sys
import uuid
import json
from typing import Dict, Any, List, Optional
from sqlalchemy.future import select
from sqlalchemy import delete

# Dynamically resolve project root containing the 'scripts' directory and add it to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = None
while current_dir and current_dir != os.path.dirname(current_dir):
    if os.path.exists(os.path.join(current_dir, "scripts")):
        project_root = current_dir
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        break
    current_dir = os.path.dirname(current_dir)

from scripts.flowdraft.schema import validate_spec, SpecError, SUPPORTED_ELEMENT_TYPES, SUPPORTED_CONNECTION_STYLES, SUPPORTED_THEMES, SUPPORTED_PORTS

from app.core.database import async_session_maker
from app.models import ExportJob, Diagram, User
from app.services.redis_broker import RedisBroker
from app.services.storage import MinioStorage

from mcp.server.fastmcp import FastMCP
from mcp.server.sse import SseServerTransport
from fastapi import FastAPI, Response

# Initialize FastMCP application
mcp = FastMCP("FlowDraft MCP Server")

# Helper to get or create MCP system user
async def get_or_create_mcp_user(db) -> User:
    stmt = select(User).where(User.email == "mcp_system_user@flowdraft.local")
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        user = User(
            email="mcp_system_user@flowdraft.local",
            hashed_password="mcp_system_user_no_password"
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    return user

# Built-in Templates Dictionary
STARTER_TEMPLATES: Dict[str, dict] = {
    "dataflow": {
        "version": "2.0",
        "theme": "dark",
        "title": { "prefix": "Realtime", "highlight": "Dataflow Engine" },
        "signature": "@FlowDraft",
        "canvas": { "width": 1920, "height": 1440, "fps": 30, "duration": 2.0 },
        "elements": [
            { "id": "src_events", "type": "input", "title": "Kafka Stream", "icon": "hash" },
            { "id": "proc_core", "type": "card", "title": "Stream Processor", "body": "Filters and enriches event stream", "icon": "scan" },
            { "id": "dec_valid", "type": "diamond", "title": "Valid Event?" },
            { "id": "storage_db", "type": "cylinder", "title": "Timescale DB", "body": "Persists time series records", "icon": "db" }
        ],
        "connections": [
            { "from": "src_events", "to": "proc_core", "label": "Ingest", "style": "solid" },
            { "from": "proc_core", "to": "dec_valid", "style": "solid" },
            { "from": "dec_valid", "to": "storage_db", "label": "Yes", "style": "solid" }
        ]
    },
    "microservices": {
        "version": "2.0",
        "theme": "dark",
        "title": { "prefix": "Cloud", "highlight": "Microservices Topology" },
        "signature": "@FlowDraft",
        "canvas": { "width": 1920, "height": 1440, "fps": 30, "duration": 2.0 },
        "elements": [
            { "id": "gw", "type": "card", "title": "API Gateway", "body": "Routes HTTP requests and terminates TLS", "icon": "shield" },
            { "id": "auth", "type": "card", "title": "Auth Service", "body": "Validates OAuth2 JWT tokens", "icon": "shield" },
            { "id": "user_db", "type": "db", "title": "Users DB", "icon": "db" }
        ],
        "connections": [
            { "from": "gw", "to": "auth", "label": "Validate Token", "style": "solid" },
            { "from": "auth", "to": "user_db", "label": "Fetch Profile", "style": "dashed" }
        ]
    },
    "auth_flow": {
        "version": "2.0",
        "theme": "light",
        "title": { "prefix": "OAuth2", "highlight": "Authentication Sequence" },
        "signature": "@FlowDraft",
        "canvas": { "width": 1920, "height": 1440, "fps": 30, "duration": 2.0 },
        "elements": [
            { "id": "client", "type": "input", "title": "SPA Client", "icon": "file" },
            { "id": "idp", "type": "card", "title": "Identity Provider", "body": "Generates signed claims", "icon": "shield" }
        ],
        "connections": [
            { "from": "client", "to": "idp", "label": "POST /token", "style": "solid" }
        ]
    }
}

# ----------------------------------------------------------------------
# MCP Tools
# ----------------------------------------------------------------------

@mcp.tool()
async def compile_diagram(spec: dict) -> str:
    """
    Validates and compiles a raw diagram specification JSON.
    Returns a success message with normalized spec summary, or details of any syntax/structural errors.
    """
    try:
        norm_spec = validate_spec(spec)
        elem_count = len(norm_spec.get("elements", []))
        conn_count = len(norm_spec.get("connections", []))
        return f"Diagram compiled successfully. Title: '{norm_spec.get('title', {}).get('prefix', '')} {norm_spec.get('title', {}).get('highlight', '')}'. Elements: {elem_count}, Connections: {conn_count}, Theme: {norm_spec.get('theme', 'dark')}."
    except SpecError as e:
        return f"Compilation failed: {e.reason} (at path: {getattr(e, 'path', None)})"
    except Exception as e:
        return f"Error during compilation: {str(e)}"

@mcp.tool()
async def validate_diagram_spec(spec: dict) -> str:
    """
    Performs thorough structural validation of a FlowDraft V2 diagram spec JSON.
    Returns details on element count, connection count, canvas metrics, and any warnings.
    """
    try:
        norm_spec = validate_spec(spec)
        elements = norm_spec.get("elements", [])
        connections = norm_spec.get("connections", [])
        canvas = norm_spec.get("canvas", {})
        
        warnings = []
        element_ids = {e.get("id") for e in elements}
        for c in connections:
            if c.get("from") not in element_ids:
                warnings.append(f"Connection 'from' ID '{c.get('from')}' not found in elements.")
            if c.get("to") not in element_ids:
                warnings.append(f"Connection 'to' ID '{c.get('to')}' not found in elements.")
                
        summary = {
            "valid": True,
            "version": norm_spec.get("version"),
            "theme": norm_spec.get("theme"),
            "element_count": len(elements),
            "connection_count": len(connections),
            "canvas_dimensions": f"{canvas.get('width', 1920)}x{canvas.get('height', 1440)}",
            "fps": canvas.get("fps", 30),
            "duration": canvas.get("duration", 2.0),
            "warnings": warnings
        }
        return json.dumps(summary, indent=2)
    except SpecError as e:
        return json.dumps({
            "valid": False,
            "error": e.reason,
            "path": getattr(e, 'path', None)
        }, indent=2)
    except Exception as e:
        return json.dumps({"valid": False, "error": str(e)}, indent=2)

@mcp.tool()
async def list_templates() -> str:
    """
    Lists available built-in starter diagram templates (e.g., 'dataflow', 'microservices', 'auth_flow').
    """
    return json.dumps({
        "templates": [
            { "name": name, "title": f"{tmpl.get('title', {}).get('prefix', '')} {tmpl.get('title', {}).get('highlight', '')}", "theme": tmpl.get("theme"), "element_count": len(tmpl.get("elements", [])) }
            for name, tmpl in STARTER_TEMPLATES.items()
        ]
    }, indent=2)

@mcp.tool()
async def get_template(name: str) -> str:
    """
    Retrieves the complete JSON spec for a starter diagram template by name ('dataflow', 'microservices', 'auth_flow').
    """
    if name not in STARTER_TEMPLATES:
        return f"Error: Template '{name}' not found. Available templates: {list(STARTER_TEMPLATES.keys())}"
    return json.dumps(STARTER_TEMPLATES[name], indent=2)

@mcp.tool()
async def list_saved_diagrams(limit: int = 10) -> str:
    """
    Lists diagrams stored in the database for the MCP system user.
    """
    async with async_session_maker() as db:
        user = await get_or_create_mcp_user(db)
        stmt = select(Diagram).where(Diagram.user_id == user.id).limit(limit)
        res = await db.execute(stmt)
        diagrams = res.scalars().all()
        
        result = [
            {
                "id": str(d.id),
                "title": d.title,
                "description": d.description,
                "theme": d.theme,
                "updated_at": d.updated_at.isoformat() if d.updated_at else None
            }
            for d in diagrams
        ]
        return json.dumps(result, indent=2)

@mcp.tool()
async def get_saved_diagram(diagram_id: str) -> str:
    """
    Retrieves a stored diagram specification by UUID from the database.
    """
    try:
        diag_uuid = uuid.UUID(diagram_id)
    except Exception:
        return "Error: Invalid diagram_id format. Must be a valid UUID."
        
    async with async_session_maker() as db:
        stmt = select(Diagram).where(Diagram.id == diag_uuid)
        res = await db.execute(stmt)
        diagram = res.scalar_one_or_none()
        
        if not diagram:
            return f"Error: Diagram '{diagram_id}' not found."
            
        return json.dumps({
            "id": str(diagram.id),
            "title": diagram.title,
            "description": diagram.description,
            "theme": diagram.theme,
            "spec": diagram.spec
        }, indent=2)

@mcp.tool()
async def save_diagram(title: str, spec: dict, description: Optional[str] = None, theme: str = "dark") -> str:
    """
    Validates and persists a diagram specification into the database under the MCP system user account.
    """
    try:
        validate_spec(spec)
    except SpecError as e:
        return f"Validation failed: {e.reason} (at path: {getattr(e, 'path', None)})"

    async with async_session_maker() as db:
        user = await get_or_create_mcp_user(db)
        
        diagram = Diagram(
            title=title,
            description=description,
            spec=spec,
            theme=theme,
            user_id=user.id
        )
        db.add(diagram)
        await db.commit()
        await db.refresh(diagram)
        
        return f"Diagram saved successfully. diagram_id: {diagram.id}"

@mcp.tool()
async def delete_saved_diagram(diagram_id: str) -> str:
    """
    Deletes a stored diagram by UUID from the database.
    """
    try:
        diag_uuid = uuid.UUID(diagram_id)
    except Exception:
        return "Error: Invalid diagram_id format. Must be a valid UUID."

    async with async_session_maker() as db:
        stmt = select(Diagram).where(Diagram.id == diag_uuid)
        res = await db.execute(stmt)
        diagram = res.scalar_one_or_none()
        
        if not diagram:
            return f"Error: Diagram '{diagram_id}' not found."
            
        await db.delete(diagram)
        await db.commit()
        return f"Diagram '{diagram_id}' deleted successfully."

@mcp.tool()
async def trigger_export(spec: dict, format: str = "mp4") -> str:
    """
    Submits a diagram spec and media format (mp4, gif, or png) to the video export queue.
    Returns the job_id of the queued task.
    """
    try:
        validate_spec(spec)
    except SpecError as e:
        return f"Validation failed: {e.reason} (at path: {getattr(e, 'path', None)})"

    if format not in ("mp4", "gif", "png"):
        return "Error: Unsupported format. Must be 'mp4', 'gif', or 'png'."

    async with async_session_maker() as db:
        user = await get_or_create_mcp_user(db)

        job = ExportJob(
            spec_override=spec,
            format=format,
            status="queued",
            user_id=user.id
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)

    broker = RedisBroker()
    try:
        await broker.enqueue_export_job(str(job.id), spec, format)
        return f"Export job triggered successfully. job_id: {job.id}"
    except Exception as e:
        async with async_session_maker() as db:
            stmt = select(ExportJob).where(ExportJob.id == job.id)
            res = await db.execute(stmt)
            j = res.scalar_one_or_none()
            if j:
                j.status = "failed"
                j.error_message = f"Failed to enqueue to broker: {e}"
                await db.commit()
        return f"Failed to trigger export: {str(e)}"

@mcp.tool()
async def get_export_status(job_id: str) -> str:
    """
    Queries the status of an export job by its UUID.
    If completed, returns status, backend proxy URL, and S3 presigned link.
    """
    try:
        job_uuid = uuid.UUID(job_id)
    except Exception:
        return "Error: Invalid job_id format. Must be a valid UUID."

    async with async_session_maker() as db:
        stmt = select(ExportJob).where(ExportJob.id == job_uuid)
        result = await db.execute(stmt)
        job = result.scalar_one_or_none()

        if not job:
            return f"Error: Export job '{job_id}' not found."

        presigned_url = None
        proxy_url = None
        if job.status == "completed":
            proxy_url = f"/api/v1/export/{job_id}/download"
            storage = MinioStorage()
            try:
                presigned_url = storage.get_download_url(f"{job_id}.{job.format}")
                job.download_url = proxy_url
                await db.commit()
            except Exception as e:
                presigned_url = f"Error generating presigned link: {str(e)}"

        return f"Job ID: {job.id}\nStatus: {job.status}\nProxy Download URL: {proxy_url or 'Pending/None'}\nPresigned S3 URL: {presigned_url or 'Pending/None'}\nError Message: {job.error_message or 'None'}"

# ----------------------------------------------------------------------
# MCP Resources & Prompts
# ----------------------------------------------------------------------

@mcp.resource("flowdraft://schema/v2")
def get_schema_resource() -> str:
    """
    Provides the FlowDraft V2 JSON specification schema rules and valid element types as a readable MCP resource.
    """
    schema_info = {
        "title": "FlowDraft V2 Diagram Specification Schema",
        "version": "2.0",
        "supported_element_types": list(SUPPORTED_ELEMENT_TYPES),
        "supported_connection_styles": list(SUPPORTED_CONNECTION_STYLES),
        "supported_themes": list(SUPPORTED_THEMES),
        "supported_ports": list(SUPPORTED_PORTS),
        "icons": ["folder", "file", "scan", "shield", "db", "hash", "package"],
        "canvas_defaults": { "width": 1920, "height": 1440, "fps": 30, "duration": 2.0 },
        "guidelines": [
            "Keep card titles short (1-3 words).",
            "Keep card body copy under 2 lines, max 22 chars per line.",
            "Use unique alphanumeric element IDs.",
            "Connections must reference existing element IDs in 'from' and 'to'."
        ]
    }
    return json.dumps(schema_info, indent=2)

@mcp.resource("flowdraft://templates/default")
def get_default_template_resource() -> str:
    """
    Exposes the default architecture diagram template as a readable MCP resource.
    """
    return json.dumps(STARTER_TEMPLATES["dataflow"], indent=2)

@mcp.prompt("create_architecture_diagram")
def create_architecture_diagram_prompt(topic: str = "Distributed System Architecture") -> str:
    """
    Generates a prompt guiding an AI assistant to structure a valid FlowDraft V2 spec.
    """
    return f"""You are creating a FlowDraft V2 diagram spec for: '{topic}'.
Ensure the output JSON follows the V2 schema:
- Set top-level 'version': '2.0', 'theme': 'dark'.
- Provide a clear 'title' object with 'prefix' and 'highlight'.
- Define elements using valid types: 'card', 'diamond', 'input', 'panel', 'cylinder'.
- Connect elements logically using 'from' and 'to' fields matching element IDs.
- Keep text copy short and punchy for compact technical rendering.
"""

# ----------------------------------------------------------------------
# ASGI Application Generator
# ----------------------------------------------------------------------

def make_mcp_asgi_app(prefix: str) -> FastAPI:
    """
    Generates a mounted FastAPI sub-application for FastMCP using SSE transport.
    """
    sse = SseServerTransport(f"{prefix}/messages/")

    async def handle_sse(request):
        # Establish the persistent SSE connection stream
        async with sse.connect_sse(
            request.scope, request.receive, request._send
        ) as streams:
            # Run the underlying MCP protocol engine
            await mcp._mcp_server.run(
                streams[0],
                streams[1],
                mcp._mcp_server.create_initialization_options(),
            )
        return Response()

    sub_app = FastAPI()
    sub_app.add_route("/sse", handle_sse, methods=["GET"])
    sub_app.mount("/messages/", sse.handle_post_message)

    @sub_app.get("/health")
    async def mcp_health():
        return {"status": "healthy"}

    return sub_app
