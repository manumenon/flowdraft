import os
import sys
import uuid
from typing import Dict, Any
from sqlalchemy.future import select

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

from scripts.flowdraft.schema import validate_spec, SpecError

from app.core.database import async_session_maker
from app.models import ExportJob, User
from app.services.redis_broker import RedisBroker
from app.services.storage import MinioStorage

from mcp.server.fastmcp import FastMCP
from mcp.server.sse import SseServerTransport
from fastapi import FastAPI, Response

# Initialize FastMCP application
mcp = FastMCP("FlowDraft MCP Server")

@mcp.tool()
async def compile_diagram(spec: dict) -> str:
    """
    Validates and compiles a raw diagram specification JSON.
    Returns a success message with the spec, or details of any syntax/structural errors.
    """
    try:
        validate_spec(spec)
        return f"Diagram compiled successfully: {spec}"
    except SpecError as e:
        return f"Compilation failed: {e.reason} (at path: {getattr(e, 'path', None)})"
    except Exception as e:
        return f"Error during compilation: {str(e)}"

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
        # Resolve/provision default system user for MCP API actions
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
    If the job is completed, returns the status and download link.
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

        download_url = None
        if job.status == "completed":
            storage = MinioStorage()
            try:
                 download_url = storage.get_download_url(f"{job_id}.{job.format}")
                 job.download_url = download_url
                 await db.commit()
            except Exception as e:
                 download_url = f"Error generating presigned link: {str(e)}"
        else:
            download_url = job.download_url

        return f"Job ID: {job.id}\nStatus: {job.status}\nDownload URL: {download_url or 'Pending/None'}\nError Message: {job.error_message or 'None'}"

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
    return sub_app
