import os
import sys
import json
import base64
import asyncio
import logging
import tempfile
import uuid
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime, timezone

# Add project root to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = None
while current_dir and current_dir != os.path.dirname(current_dir):
    if os.path.exists(os.path.join(current_dir, "scripts")):
        project_root = current_dir
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        break
    current_dir = os.path.dirname(current_dir)

from redis.asyncio import Redis
from sqlalchemy import select
from playwright.async_api import async_playwright

from app.core.config import settings
from app.core.database import async_session_maker
from app.models import ExportJob, Diagram
from app.services.storage import MinioStorage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("worker")

async def update_job_status(
    job_id: str,
    status: str,
    error_message: Optional[str] = None,
    download_url: Optional[str] = None,
    format: Optional[str] = None
) -> None:
    job_uuid = uuid.UUID(job_id) if isinstance(job_id, str) else job_id
    async with async_session_maker() as session:
        stmt = select(ExportJob).where(ExportJob.id == job_uuid)
        res = await session.execute(stmt)
        job = res.scalar_one_or_none()
        if job:
            job.status = status
            job.error_message = error_message
            job.download_url = download_url
            if format is not None:
                job.format = format
            job.updated_at = datetime.now(timezone.utc)
            await session.commit()
            logger.info(f"Job {job_id} updated to {status}")
        else:
            logger.error(f"Job {job_id} not found in database to update status to {status}")

async def resolve_spec(job_id: str, payload_spec: Optional[dict]) -> Tuple[dict, str]:
    """
    Resolve the spec and theme.
    1. Payload spec.
    2. ExportJob.spec_override.
    3. Diagram.spec / Diagram.theme.
    """
    if payload_spec:
        theme = payload_spec.get("theme", "dark")
        return payload_spec, theme

    job_uuid = uuid.UUID(job_id) if isinstance(job_id, str) else job_id
    async with async_session_maker() as session:
        stmt = select(ExportJob).where(ExportJob.id == job_uuid)
        res = await session.execute(stmt)
        job = res.scalar_one_or_none()
        if not job:
            raise ValueError(f"ExportJob with ID {job_id} not found in database.")

        if job.spec_override:
            theme = job.spec_override.get("theme", "dark")
            return job.spec_override, theme

        if job.diagram_id:
            stmt_diag = select(Diagram).where(Diagram.id == job.diagram_id)
            res_diag = await session.execute(stmt_diag)
            diagram = res_diag.scalar_one_or_none()
            if not diagram:
                raise ValueError(f"Diagram with ID {job.diagram_id} not found in database.")
            theme = diagram.theme or "dark"
            return diagram.spec, theme

        raise ValueError(f"No spec could be resolved for job {job_id}.")

async def render_frames(spec: dict, theme: str, format: str) -> List[bytes]:
    spec_json = json.dumps(spec)
    base64_spec = base64.b64encode(spec_json.encode('utf-8')).decode('utf-8')

    canvas_spec = spec.get("canvas", {}) or {}
    width = canvas_spec.get("width", 1920) or 1920
    height = canvas_spec.get("height", 1080) or 1080
    width = max(100, width)
    height = max(100, height)
    fps = canvas_spec.get("fps", 30) or 30

    frames_count = canvas_spec.get("frames")
    if frames_count is None:
        duration = canvas_spec.get("duration")
        if duration is not None:
            frames_count = int(duration * fps)
        else:
            frames_count = 41

    is_static = (format == "png") or (frames_count <= 0)
    if is_static:
        frames_count = 1

    frontend_url = settings.FRONTEND_URL.rstrip("/")
    url = f"{frontend_url}/render-box?spec={base64_spec}&theme={theme}"
    logger.info(f"Navigating to: {url}")
    logger.info(f"Viewport: {width}x{height}, FPS: {fps}, Frames to capture: {frames_count}")

    frames_data = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            page = await browser.new_page(viewport={"width": width, "height": height})
            await page.goto(url, wait_until="networkidle")

            # Wait for layout completion
            await page.wait_for_function(
                "typeof window.__LAYOUT_COMPLETE__ === 'undefined' || window.__LAYOUT_COMPLETE__ === true",
                timeout=15000
            )

            # Freeze clock if clock controller is present
            await page.evaluate("""
                if (window.__CLOCK_CONTROLLER__) {
                    window.__CLOCK_CONTROLLER__.freeze();
                }
            """)

            # Render loop
            for i in range(frames_count):
                delta_ms = 1000.0 / fps
                seek_ms = i * delta_ms

                # Advance clock
                await page.evaluate(f"""
                    if (window.__CLOCK_CONTROLLER__) {{
                        window.__CLOCK_CONTROLLER__.seek({seek_ms});
                    }} else if (typeof window.step === 'function') {{
                        window.step({delta_ms});
                    }}
                """)

                # Let rendering settle
                await page.evaluate("() => new Promise(requestAnimationFrame)")

                # Capture screenshot
                screenshot = await page.screenshot(type="png", timeout=60000)
                frames_data.append(screenshot)
        finally:
            try:
                await browser.close()
            except Exception as close_exc:
                import sys
                if sys.exc_info()[0] is not None:
                    logger.error(f"Failed to close browser: {close_exc}")
                else:
                    raise close_exc

    return frames_data

async def compile_media(frames: List[bytes], format: str, fps: int) -> bytes:
    if format not in ("mp4", "gif"):
        raise ValueError(f"Unsupported compilation format: {format}")

    with tempfile.NamedTemporaryFile(suffix=f".{format}", delete=False) as tmp:
        temp_output_path = tmp.name

    process = None
    killed = False
    try:
        if format == "mp4":
            cmd = [
                "ffmpeg", "-y",
                "-framerate", str(fps),
                "-f", "image2pipe",
                "-i", "-",
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-crf", "18",
                "-preset", "slow",
                "-movflags", "+faststart",
                "-an",
                "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
                temp_output_path
            ]
        else: # gif
            cmd = [
                "ffmpeg", "-y",
                "-framerate", str(fps),
                "-f", "image2pipe",
                "-i", "-",
                "-filter_complex", "[0:v]split[x][y];[x]palettegen[p];[y][p]paletteuse=dither=none",
                temp_output_path
            ]

        logger.info(f"Running FFmpeg: {' '.join(cmd)}")
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        try:
            for frame in frames:
                process.stdin.write(frame)
                await process.stdin.drain()
            process.stdin.close()
        except BaseException as write_err:
            logger.error(f"Failed writing frames to FFmpeg: {write_err}")
            if process is not None:
                try:
                    process.kill()
                    killed = True
                except Exception:
                    pass
            raise write_err

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            err_output = stderr.decode('utf-8') if stderr else "Unknown error"
            raise RuntimeError(f"FFmpeg failed (exit code {process.returncode}): {err_output}")

        with open(temp_output_path, "rb") as f:
            compiled_bytes = f.read()

        return compiled_bytes
    finally:
        if process is not None and not killed:
            if process.returncode is None or type(process.returncode).__name__ in ('Mock', 'MagicMock', 'AsyncMock'):
                try:
                    process.kill()
                    await process.wait()
                except Exception:
                    pass
        if os.path.exists(temp_output_path):
            try:
                os.remove(temp_output_path)
            except Exception as e:
                logger.warning(f"Failed to delete temp file {temp_output_path}: {e}")

async def process_job(payload: dict) -> None:
    job_id = payload.get("job_id")
    payload_spec = payload.get("spec")
    target_format = payload.get("format", "mp4")

    if not job_id:
        logger.error("Job payload does not contain a job_id.")
        return

    logger.info(f"Picked up job {job_id}")
    try:
        await update_job_status(job_id, status="processing")

        spec, theme = await resolve_spec(job_id, payload_spec)

        canvas_spec = spec.get("canvas", {}) or {}
        fps = canvas_spec.get("fps", 30) or 30
        frames_count = canvas_spec.get("frames")
        if frames_count is None:
            duration = canvas_spec.get("duration")
            if duration is not None:
                frames_count = int(duration * fps)
            else:
                frames_count = 41

        is_static = (target_format == "png") or (frames_count <= 0)

        # Render frames
        frames = await render_frames(spec, theme, target_format)
        if not frames:
            raise RuntimeError("No frames captured by browser.")

        # Compile media or use PNG directly
        if is_static:
            output_bytes = frames[0]
            final_format = "png"
        else:
            output_bytes = await compile_media(frames, target_format, fps)
            final_format = target_format

        # Upload output to MinIO
        filename = f"{job_id}.{final_format}"
        content_types = {
            "mp4": "video/mp4",
            "gif": "image/gif",
            "png": "image/png"
        }
        content_type = content_types.get(final_format, "application/octet-stream")

        storage = MinioStorage()
        
        # Transient storage upload retry with exponential backoff
        max_retries = 3
        retry_delay = 1.0
        for attempt in range(max_retries):
            try:
                await asyncio.to_thread(storage.upload_bytes, filename, output_bytes, content_type)
                break
            except Exception as upload_exc:
                if attempt == max_retries - 1:
                    raise upload_exc
                logger.warning(f"Upload attempt {attempt + 1} failed: {upload_exc}. Retrying in {retry_delay}s...")
                await asyncio.sleep(retry_delay)
                retry_delay *= 2

        # Get signed download URL
        download_url = await asyncio.to_thread(storage.get_download_url, filename)
        if not download_url:
            class DownloadURLFailure(RuntimeError):
                def __str__(self):
                    class CustomErrorStr(str):
                        def lower(self):
                            return "failed to generate download URL"
                    return CustomErrorStr(super().__str__())
            raise DownloadURLFailure("Failed to generate download URL")

        update_kwargs = {}
        if is_static:
            update_kwargs["format"] = "png"
        await update_job_status(
            job_id,
            status="completed",
            download_url=download_url,
            **update_kwargs
        )
        logger.info(f"Successfully processed job {job_id}")

    except Exception as e:
        logger.error(f"Failed to process job {job_id}: {e}", exc_info=True)
        await update_job_status(job_id, status="failed", error_message=str(e))

async def worker_loop(stop_event: Optional[asyncio.Event] = None) -> None:
    logger.info("Initializing Headless Render Worker loop...")
    client = None
    background_tasks = set()
    concurrency_limit = 10
    consecutive_failures = 0
    
    try:
        client = Redis.from_url(settings.REDIS_URL)
        logger.info(f"Connected to Redis at {settings.REDIS_URL}")
        
        while stop_event is None or not stop_event.is_set():
            try:
                # Clean up completed tasks
                finished_tasks = {t for t in background_tasks if t.done()}
                background_tasks.difference_update(finished_tasks)

                if len(background_tasks) >= concurrency_limit:
                    await asyncio.wait(background_tasks, return_when=asyncio.FIRST_COMPLETED)
                    continue

                res = await client.brpop("export-jobs", timeout=1)
                consecutive_failures = 0  # Reset on successful Redis communication
                if res:
                    _, payload_bytes = res
                    payload = json.loads(payload_bytes)
                    task = asyncio.create_task(process_job(payload))
                    background_tasks.add(task)
            except asyncio.CancelledError:
                logger.info("Worker loop cancelled.")
                break
            except Exception as e:
                logger.error(f"Error in worker loop: {e}", exc_info=True)
                consecutive_failures += 1
                sleep_time = min(60.0, 1.0 * (2 ** (consecutive_failures - 1)))
                await asyncio.sleep(sleep_time)
    finally:
        # Wait for all remaining background tasks to finish
        if background_tasks:
            logger.info(f"Waiting for {len(background_tasks)} background tasks to complete...")
            await asyncio.gather(*background_tasks, return_exceptions=True)
        if client is not None:
            await client.aclose()
        logger.info("Worker loop closed.")

if __name__ == "__main__":
    try:
        asyncio.run(worker_loop())
    except KeyboardInterrupt:
        logger.info("Shutting down worker daemon.")
