import os
import sys
import uuid
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
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

from scripts.flowdraft.schema import validate_spec

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models import Diagram, ExportJob, User
from app.schemas import ExportJobCreate
from app.services.redis_broker import RedisBroker
from app.services.storage import MinioStorage

router = APIRouter()

@router.post("", status_code=status.HTTP_200_OK)
async def create_export_job(
    payload: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Submit an export job.
    Accepts diagram_id or spec_override, and a format ('mp4' or 'gif').
    Creates database entry, initializes RedisBroker, and enqueues job details.
    """
    diagram_id = None
    spec_override = None
    fmt = None
    
    if "elements" in payload:
        # Raw spec format passed by tests
        spec_override = payload
        fmt = payload.get("canvas", {}).get("format", "mp4")
    else:
        # ExportJobCreate format
        diagram_id_str = payload.get("diagram_id")
        if diagram_id_str:
            try:
                diagram_id = uuid.UUID(str(diagram_id_str))
            except Exception:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid diagram_id format. Must be a valid UUID."
                )
        spec_override = payload.get("spec_override")
        fmt = payload.get("format", "mp4")

    if fmt not in ("mp4", "gif", "png"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported format. Must be 'mp4', 'gif', or 'png'"
        )

    spec = None
    if diagram_id is not None:
        # Load from database
        stmt = select(Diagram).where(Diagram.id == diagram_id)
        result = await db.execute(stmt)
        diagram = result.scalar_one_or_none()
        if not diagram:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diagram not found")
        if diagram.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to export this diagram"
            )
        spec = diagram.spec
    
    # If spec_override is supplied, it overrides diagram_id or serves as input.
    if spec_override is not None:
        # Validate the spec_override dictionary.
        validate_spec(spec_override)
        spec = spec_override

    if spec is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must provide either diagram_id or spec_override"
        )

    # Create export job in database
    job = ExportJob(
        diagram_id=diagram_id,
        spec_override=spec_override,
        format=fmt,
        status="queued",
        user_id=current_user.id
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    # Enqueue to Redis broker
    broker = RedisBroker()
    try:
        await broker.enqueue_export_job(str(job.id), spec, fmt)
    except Exception as e:
        # Mark as failed in DB if Redis enqueuing fails
        job.status = "failed"
        job.error_message = f"Failed to enqueue to broker: {e}"
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit export job: {e}"
        )

    return {
        "job_id": str(job.id),
        "status": "queued"
    }

@router.get("/{job_id}")
async def get_export_job_status(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve status of an export job.
    If job is completed, populates presigned download url via MinioStorage.
    """
    stmt = select(ExportJob).where(ExportJob.id == job_id)
    result = await db.execute(stmt)
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export job not found")
        
    if job.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this export job"
        )

    download_url = None
    if job.status == "completed":
        # Return backend download proxy URL instead of presigned S3 url to avoid Host header signature mismatch
        download_url = f"/api/v1/export/{job_id}/download"
        job.download_url = download_url
        await db.commit()
    else:
        download_url = job.download_url

    return {
        "job_id": str(job.id),
        "status": job.status,
        "download_url": download_url,
        "error_message": job.error_message
    }

@router.get("/{job_id}/download")
async def download_export_file(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Backend download proxy: Streams the exported video/GIF from MinIO.
    Allows anonymous downloads based on secure UUIDv4.
    """
    stmt = select(ExportJob).where(ExportJob.id == job_id)
    result = await db.execute(stmt)
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export job not found")
        
    if job.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Export job is not completed yet"
        )
        
    storage = MinioStorage()
    try:
        minio_response = storage.get_object(f"{job_id}.{job.format}")
        
        media_type = "video/mp4"
        if job.format == "gif":
            media_type = "image/gif"
        elif job.format == "png":
            media_type = "image/png"
            
        return StreamingResponse(
            minio_response,
            media_type=media_type,
            headers={
                "Content-Disposition": f'attachment; filename="{job_id}.{job.format}"'
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stream file from storage: {str(e)}"
        )
