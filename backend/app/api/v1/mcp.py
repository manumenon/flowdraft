import os
import sys
import uuid
import json
import base64
from datetime import datetime
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
from scripts.flowdraft.compiler import compile_spec
from scripts.flowdraft.layout_engine import layout

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
    },
    "fintech_platform": {
        "version": "2.0",
        "theme": "dark",
        "title": { "prefix": "Global", "highlight": "FinTech Payment Backbone" },
        "signature": "@FlowDraft",
        "canvas": { "width": 2560, "height": 1440, "layoutDirection": "LR" },
        "elements": [
            { "id": "mobile_app", "type": "input", "title": "Mobile Banking", "icon": "file" },
            { "id": "api_gw", "type": "card", "title": "PCI Gateway", "body": "Enforces rate limiting & mTLS", "icon": "shield" },
            { "id": "ledger_db", "type": "cylinder", "title": "Immutable Ledger", "body": "PostgreSQL ACID ledger", "icon": "db" }
        ],
        "connections": [
            { "from": "mobile_app", "to": "api_gw", "label": "Encrypted Payload" },
            { "from": "api_gw", "to": "ledger_db", "label": "Commit Transaction" }
        ]
    },
    "global_ai_mesh": {
        "version": "2.0",
        "theme": "dark",
        "title": { "prefix": "Cognitive", "highlight": "AI Inference Mesh" },
        "signature": "@FlowDraft",
        "canvas": { "width": 2560, "height": 1440, "layoutDirection": "LR" },
        "elements": [
            { "id": "user_prompt", "type": "input", "title": "User Query", "icon": "file" },
            { "id": "router_agent", "type": "card", "title": "Agentic Router", "body": "Dispatches domain workflows", "icon": "scan" },
            { "id": "llm_cluster", "type": "card", "title": "vLLM Inference Cluster", "body": "Serves quantized model weights", "icon": "package" }
        ],
        "connections": [
            { "from": "user_prompt", "to": "router_agent", "label": "Stream Query" },
            { "from": "router_agent", "to": "llm_cluster", "label": "Parallel Prefill" }
        ]
    }
}

# ----------------------------------------------------------------------
# MCP Tools
# ----------------------------------------------------------------------

@mcp.tool()
async def compile_diagram(spec: dict) -> str:
    """
    Validates and compiles a raw diagram specification JSON into element layout positioning and bounding box details.
    Invokes the FlowDraft IR compiler and layout engine to return node coordinates, dimensions, ports, annotations, and connection routing metrics.
    Returns structured JSON.
    """
    try:
        norm_spec = validate_spec(spec)
        ir = compile_spec(norm_spec)
        canvas = norm_spec.get("canvas", {})
        cw = canvas.get("width", 1920)
        ch = canvas.get("height", 1440)
        layout_ir = layout(ir, cw, ch)

        nodes_summary = []
        min_x, min_y = float('inf'), float('inf')
        max_x, max_y = float('-inf'), float('-inf')

        for node in layout_ir.get("nodes", []):
            x = node.get("x", 0)
            y = node.get("y", 0)
            w = node.get("width", 0)
            h = node.get("height", 0)
            min_x = min(min_x, x)
            min_y = min(min_y, y)
            max_x = max(max_x, x + w)
            max_y = max(max_y, y + h)

            nodes_summary.append({
                "id": node.get("id"),
                "type": node.get("type"),
                "title": node.get("title", ""),
                "x": round(x, 2),
                "y": round(y, 2),
                "width": round(w, 2),
                "height": round(h, 2),
                "parent": node.get("parent"),
                "children": node.get("children", [])
            })

        connections_summary = []
        for conn in layout_ir.get("connections", []):
            connections_summary.append({
                "from": conn.get("from"),
                "to": conn.get("to"),
                "style": conn.get("style", "solid"),
                "points": conn.get("points", [])
            })

        annotations_summary = layout_ir.get("annotations", []) or norm_spec.get("annotations", [])

        bounding_box = {
            "min_x": round(min_x, 2) if min_x != float('inf') else 0,
            "min_y": round(min_y, 2) if min_y != float('inf') else 0,
            "max_x": round(max_x, 2) if max_x != float('-inf') else 0,
            "max_y": round(max_y, 2) if max_y != float('-inf') else 0,
            "width": round(max_x - min_x, 2) if min_x != float('inf') else 0,
            "height": round(max_y - min_y, 2) if min_y != float('inf') else 0,
        }

        title_obj = norm_spec.get("title", {})
        title_str = f"{title_obj.get('prefix', '')} {title_obj.get('highlight', '')}".strip()

        graph_density = round(len(connections_summary) / max(1, len(nodes_summary)), 2)
        aspect_ratio = f"{round(cw / max(1, ch), 2)}:1"

        result = {
            "status": "compiled",
            "title": title_str,
            "version": norm_spec.get("version"),
            "theme": norm_spec.get("theme"),
            "canvas_dimensions": f"{cw}x{ch}",
            "aspect_ratio": aspect_ratio,
            "element_count": len(nodes_summary),
            "connection_count": len(connections_summary),
            "graph_density": graph_density,
            "bounding_box": bounding_box,
            "nodes": nodes_summary,
            "connections": connections_summary,
            "annotations": annotations_summary
        }
        return json.dumps(result, indent=2)
    except SpecError as e:
        return json.dumps({
            "status": "error",
            "error": f"Compilation failed: {e.reason}",
            "path": getattr(e, 'path', None)
        }, indent=2)
    except Exception as e:
        return json.dumps({
            "status": "error",
            "error": f"Error during compilation: {str(e)}"
        }, indent=2)

@mcp.tool()
async def validate_diagram_spec(spec: dict) -> str:
    """
    Performs thorough structural validation of a FlowDraft V2 diagram spec JSON.
    Returns details on element count, connection count, canvas metrics, and diagnostic warnings (orphan nodes, invalid status).
    """
    try:
        norm_spec = validate_spec(spec)
        elements = norm_spec.get("elements", [])
        connections = norm_spec.get("connections", [])
        canvas = norm_spec.get("canvas", {})
        
        warnings = []
        element_ids = {e.get("id") for e in elements}
        connected_ids = set()

        for c in connections:
            from_id = c.get("from")
            to_id = c.get("to")
            if from_id not in element_ids:
                warnings.append(f"Connection 'from' ID '{from_id}' not found in elements.")
            else:
                connected_ids.add(from_id)
            if to_id not in element_ids:
                warnings.append(f"Connection 'to' ID '{to_id}' not found in elements.")
            else:
                connected_ids.add(to_id)
                
        # Check for orphan elements (unconnected nodes)
        if len(elements) > 1:
            for e in elements:
                eid = e.get("id")
                if eid and eid not in connected_ids and not e.get("parent"):
                    warnings.append(f"Element '{eid}' ({e.get('title', '')}) is an orphan node (0 connections).")

        # Validate status enum if specified
        valid_statuses = {"healthy", "active", "streaming", "warning", "idle", "disabled"}
        for e in elements:
            status = e.get("status")
            if status and status not in valid_statuses:
                warnings.append(f"Element '{e.get('id')}' has unrecognized status '{status}'. Allowed: {sorted(list(valid_statuses))}")

        # Validate layoutDirection if specified
        layout_dir = canvas.get("layoutDirection")
        valid_dirs = {"DOWN", "RIGHT", "LR", "TB", "HORIZONTAL", "VERTICAL"}
        if layout_dir and str(layout_dir).upper() not in valid_dirs:
            warnings.append(f"Canvas layoutDirection '{layout_dir}' is unrecognized. Recommended: 'LR' or 'DOWN'.")

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
    Lists available built-in starter diagram templates ('dataflow', 'microservices', 'auth_flow', 'fintech_platform', 'global_ai_mesh') with descriptions and visual themes.
    """
    descriptions = {
        "dataflow": "Realtime Dataflow Engine processing Kafka streams with Timescale DB storage",
        "microservices": "Cloud Microservices Topology showing API Gateway and OAuth2 Auth Service",
        "auth_flow": "OAuth2 Authentication Sequence between SPA Client and Identity Provider",
        "fintech_platform": "Global FinTech Payment Backbone with PCI Gateway and Immutable Ledger",
        "global_ai_mesh": "Cognitive AI Inference Mesh with Agentic Router and vLLM Cluster"
    }
    return json.dumps({
        "templates": [
            {
                "name": name,
                "title": f"{tmpl.get('title', {}).get('prefix', '')} {tmpl.get('title', {}).get('highlight', '')}".strip(),
                "description": descriptions.get(name, ""),
                "theme": tmpl.get("theme"),
                "element_count": len(tmpl.get("elements", []))
            }
            for name, tmpl in STARTER_TEMPLATES.items()
        ]
    }, indent=2)

@mcp.tool()
async def get_template(name: str) -> str:
    """
    Retrieves the complete JSON spec for a starter diagram template by name.
    """
    if name not in STARTER_TEMPLATES:
        return json.dumps({
            "error": f"Template '{name}' not found.",
            "available_templates": list(STARTER_TEMPLATES.keys())
        }, indent=2)
    return json.dumps(STARTER_TEMPLATES[name], indent=2)

@mcp.tool()
async def list_saved_diagrams(limit: int = 10, query: Optional[str] = None) -> str:
    """
    Lists diagrams stored in the database for the MCP system user, with optional title keyword search.
    """
    async with async_session_maker() as db:
        user = await get_or_create_mcp_user(db)
        stmt = select(Diagram).where(Diagram.user_id == user.id)
        if query and query.strip():
            stmt = stmt.where(Diagram.title.ilike(f"%{query.strip()}%"))
        stmt = stmt.limit(limit)
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
        return json.dumps({
            "status": "error",
            "error": "Invalid diagram_id format. Must be a valid UUID."
        }, indent=2)
        
    async with async_session_maker() as db:
        stmt = select(Diagram).where(Diagram.id == diag_uuid)
        res = await db.execute(stmt)
        diagram = res.scalar_one_or_none()
        
        if not diagram:
            return json.dumps({
                "status": "error",
                "error": f"Diagram '{diagram_id}' not found."
            }, indent=2)
            
        return json.dumps({
            "id": str(diagram.id),
            "title": diagram.title,
            "description": diagram.description,
            "theme": diagram.theme,
            "spec": diagram.spec
        }, indent=2)

@mcp.tool()
async def save_diagram(title: str, spec: dict, description: Optional[str] = None, theme: str = "dark", diagram_id: Optional[str] = None) -> str:
    """
    Validates and persists or updates a diagram specification into the database under the MCP system user account.
    If diagram_id is provided, updates the existing record (upsert).
    Returns structured JSON with diagram_id, status, title, and timestamps.
    """
    try:
        validate_spec(spec)
    except SpecError as e:
        return json.dumps({
            "status": "error",
            "error": f"Validation failed: {e.reason}",
            "path": getattr(e, 'path', None)
        }, indent=2)

    # Auto-extract title if title argument is empty or generic
    if not title or not title.strip():
        if isinstance(spec.get("title"), dict):
            title = f"{spec['title'].get('prefix', '')} {spec['title'].get('highlight', '')}".strip()
        if not title:
            title = "Untitled FlowDraft Diagram"

    async with async_session_maker() as db:
        user = await get_or_create_mcp_user(db)
        diagram = None
        
        if diagram_id:
            try:
                diag_uuid = uuid.UUID(diagram_id)
                stmt = select(Diagram).where(Diagram.id == diag_uuid, Diagram.user_id == user.id)
                res = await db.execute(stmt)
                diagram = res.scalar_one_or_none()
            except Exception:
                diagram = None

        if diagram:
            diagram.title = title
            if description is not None:
                diagram.description = description
            diagram.spec = spec
            diagram.theme = theme
            diagram.updated_at = datetime.utcnow()
            status_str = "updated"
        else:
            diagram = Diagram(
                title=title,
                description=description,
                spec=spec,
                theme=theme,
                user_id=user.id
            )
            db.add(diagram)
            status_str = "saved"
            
        await db.commit()
        await db.refresh(diagram)
        
        return json.dumps({
            "status": status_str,
            "diagram_id": str(diagram.id),
            "title": diagram.title,
            "description": diagram.description,
            "theme": diagram.theme,
            "created_at": diagram.created_at.isoformat() if diagram.created_at else None,
            "updated_at": diagram.updated_at.isoformat() if diagram.updated_at else None
        }, indent=2)

@mcp.tool()
async def delete_saved_diagram(diagram_id: str) -> str:
    """
    Deletes a stored diagram by UUID from the database.
    """
    try:
        diag_uuid = uuid.UUID(diagram_id)
    except Exception:
        return json.dumps({
            "status": "error",
            "error": "Invalid diagram_id format. Must be a valid UUID."
        }, indent=2)

    async with async_session_maker() as db:
        stmt = select(Diagram).where(Diagram.id == diag_uuid)
        res = await db.execute(stmt)
        diagram = res.scalar_one_or_none()
        
        if not diagram:
            return json.dumps({
                "status": "error",
                "error": f"Diagram '{diagram_id}' not found."
            }, indent=2)
            
        await db.delete(diagram)
        await db.commit()
        return json.dumps({
            "status": "deleted",
            "diagram_id": str(diagram_id)
        }, indent=2)

@mcp.tool()
async def trigger_export(spec: dict, format: str = "gif") -> str:
    """
    Submits a diagram spec and media format (mp4, gif, png, svg, or excalidraw) to the video export queue.
    Returns structured JSON with job_id, format, and status.
    """
    try:
        norm_spec = validate_spec(spec)
        ir = compile_spec(norm_spec)
        layout(ir)
        if "canvas" in ir and isinstance(ir["canvas"], dict):
            if "canvas" not in norm_spec or not isinstance(norm_spec["canvas"], dict):
                norm_spec["canvas"] = {}
            norm_spec["canvas"]["width"] = max(norm_spec["canvas"].get("width", 1920), ir["canvas"].get("width", 1920))
            norm_spec["canvas"]["height"] = max(norm_spec["canvas"].get("height", 1440), ir["canvas"].get("height", 1440))
        spec = norm_spec
    except SpecError as e:
        return json.dumps({
            "status": "failed",
            "error": f"Validation failed: {e.reason}",
            "path": getattr(e, 'path', None)
        }, indent=2)
    except Exception as e:
        pass

    if format not in ("mp4", "gif", "png", "svg", "excalidraw"):
        return json.dumps({
            "status": "failed",
            "error": "Unsupported format. Must be 'mp4', 'gif', 'png', 'svg', or 'excalidraw'."
        }, indent=2)

    # Check duration cap for animated exports
    duration = spec.get("canvas", {}).get("duration", 2.0)
    if format in ("mp4", "gif") and duration > 30.0:
        return json.dumps({
            "status": "failed",
            "error": f"Export duration ({duration}s) exceeds maximum allowed limit of 30.0 seconds."
        }, indent=2)

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
        return json.dumps({
            "status": "queued",
            "job_id": str(job.id),
            "format": format
        }, indent=2)
    except Exception as e:
        async with async_session_maker() as db:
            stmt = select(ExportJob).where(ExportJob.id == job.id)
            res = await db.execute(stmt)
            j = res.scalar_one_or_none()
            if j:
                j.status = "failed"
                j.error_message = f"Failed to enqueue to broker: {e}"
                await db.commit()
        return json.dumps({
            "status": "failed",
            "job_id": str(job.id),
            "error": f"Failed to trigger export: {str(e)}"
        }, indent=2)

@mcp.tool()
async def get_export_status(job_id: str, include_base64: bool = False) -> str:
    """
    Queries the status of an export job by its UUID.
    Returns structured JSON with job_id, status, download_url, presigned_url, error_message, file size metadata, and optional base64 image content when requested.
    """
    try:
        job_uuid = uuid.UUID(job_id)
    except Exception:
        return json.dumps({
            "status": "error",
            "error": "Invalid job_id format. Must be a valid UUID."
        }, indent=2)

    async with async_session_maker() as db:
        stmt = select(ExportJob).where(ExportJob.id == job_uuid)
        result = await db.execute(stmt)
        job = result.scalar_one_or_none()

        if not job:
            return json.dumps({
                "status": "error",
                "error": f"Export job '{job_id}' not found."
            }, indent=2)

        presigned_url = None
        proxy_url = None
        file_size = None
        base64_data = None

        if job.status == "completed":
            proxy_url = f"/api/v1/export/{job_id}/download"
            storage = MinioStorage()
            object_name = f"{job_id}.{job.format}"
            try:
                raw_presigned = storage.get_download_url(object_name)
                # Replace internal Docker hostname minio:9000 with localhost:9000 for host client access
                presigned_url = raw_presigned.replace("http://minio:9000", "http://localhost:9000")
                job.download_url = proxy_url
                await db.commit()
            except Exception as e:
                presigned_url = f"Error generating presigned link: {str(e)}"
            try:
                if storage.client:
                    stat = storage.client.stat_object(storage.bucket_name, object_name)
                    file_size = stat.size
                    
                    if include_base64 and job.format in ("png", "svg", "excalidraw"):
                        response = storage.client.get_object(storage.bucket_name, object_name)
                        img_bytes = response.read()
                        response.close()
                        response.release_conn()
                        base64_data = base64.b64encode(img_bytes).decode("utf-8")
            except Exception:
                file_size = None

        out_dict = {
            "job_id": str(job.id),
            "status": job.status,
            "download_url": proxy_url,
            "presigned_url": presigned_url,
            "error_message": job.error_message,
            "file_size": file_size
        }
        if include_base64 and base64_data:
            out_dict["base64_data"] = base64_data

        return json.dumps(out_dict, indent=2)

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
