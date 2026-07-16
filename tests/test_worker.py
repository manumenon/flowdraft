import unittest
import uuid
import json
import base64
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock

from app.worker import (
    resolve_spec,
    update_job_status,
    process_job,
    worker_loop,
    render_frames,
    compile_media
)
from app.models import ExportJob, Diagram


class MockResult:
    def __init__(self, val):
        self.val = val

    def scalar_one_or_none(self):
        return self.val


class AsyncContextManagerMock:
    def __init__(self, val):
        self.val = val

    async def __aenter__(self):
        return self.val

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


class TestRenderWorker(unittest.IsolatedAsyncioTestCase):

    async def test_resolve_spec_from_payload(self):
        # 1. Spec is provided in the payload
        payload_spec = {"canvas": {"width": 800}, "theme": "light"}
        job_id = str(uuid.uuid4())
        
        spec, theme = await resolve_spec(job_id, payload_spec)
        
        self.assertEqual(spec, payload_spec)
        self.assertEqual(theme, "light")

    @patch("app.worker.async_session_maker")
    async def test_resolve_spec_from_export_job_override(self, mock_session_maker):
        job_id = uuid.uuid4()
        mock_job = ExportJob(
            id=job_id,
            spec_override={"canvas": {"height": 600}, "theme": "dark"},
            format="mp4"
        )
        
        mock_session = AsyncMock()
        mock_session_maker.return_value.__aenter__.return_value = mock_session
        mock_session.execute.return_value = MockResult(mock_job)
        
        spec, theme = await resolve_spec(str(job_id), None)
        
        self.assertEqual(spec, mock_job.spec_override)
        self.assertEqual(theme, "dark")
        mock_session.execute.assert_called_once()

    @patch("app.worker.async_session_maker")
    async def test_resolve_spec_from_diagram(self, mock_session_maker):
        job_id = uuid.uuid4()
        diag_id = uuid.uuid4()
        
        mock_job = ExportJob(
            id=job_id,
            diagram_id=diag_id,
            spec_override=None,
            format="mp4"
        )
        mock_diagram = Diagram(
            id=diag_id,
            spec={"canvas": {"width": 1024}},
            theme="custom-theme"
        )
        
        mock_session = AsyncMock()
        mock_session_maker.return_value.__aenter__.return_value = mock_session
        
        # First query for ExportJob, second for Diagram
        mock_session.execute.side_effect = [
            MockResult(mock_job),
            MockResult(mock_diagram)
        ]
        
        spec, theme = await resolve_spec(str(job_id), None)
        
        self.assertEqual(spec, mock_diagram.spec)
        self.assertEqual(theme, "custom-theme")
        self.assertEqual(mock_session.execute.call_count, 2)

    @patch("app.worker.async_session_maker")
    async def test_resolve_spec_not_found(self, mock_session_maker):
        job_id = uuid.uuid4()
        
        mock_session = AsyncMock()
        mock_session_maker.return_value.__aenter__.return_value = mock_session
        mock_session.execute.return_value = MockResult(None)
        
        with self.assertRaises(ValueError):
            await resolve_spec(str(job_id), None)

    @patch("app.worker.async_session_maker")
    async def test_update_job_status(self, mock_session_maker):
        job_id = uuid.uuid4()
        mock_job = ExportJob(id=job_id, status="queued")
        
        mock_session = AsyncMock()
        mock_session_maker.return_value.__aenter__.return_value = mock_session
        mock_session.execute.return_value = MockResult(mock_job)
        
        await update_job_status(str(job_id), "processing", download_url="http://download")
        
        self.assertEqual(mock_job.status, "processing")
        self.assertEqual(mock_job.download_url, "http://download")
        mock_session.commit.assert_called_once()

    @patch("app.worker.async_playwright")
    async def test_render_frames_standard(self, mock_async_playwright):
        # Set up Playwright mocks
        mock_playwright = AsyncMock()
        mock_browser = AsyncMock()
        mock_page = AsyncMock()
        
        mock_async_playwright.return_value = AsyncContextManagerMock(mock_playwright)
        mock_playwright.chromium.launch.return_value = mock_browser
        mock_browser.new_page.return_value = mock_page
        mock_page.screenshot.return_value = b"frame_bytes"
        
        spec = {"canvas": {"width": 800, "height": 600, "fps": 10, "frames": 3}}
        
        frames = await render_frames(spec, "dark", "mp4")
        
        self.assertEqual(len(frames), 3)
        self.assertEqual(frames[0], b"frame_bytes")
        mock_page.goto.assert_called_once()
        mock_browser.close.assert_called_once()

    @patch("app.worker.asyncio.create_subprocess_exec")
    @patch("builtins.open", new_callable=unittest.mock.mock_open, read_data=b"compiled_video_data")
    @patch("os.path.exists", return_value=True)
    @patch("os.remove")
    async def test_compile_media_mp4(self, mock_remove, mock_exists, mock_open_file, mock_subprocess):
        # Set up subprocess mocks
        mock_process = AsyncMock()
        mock_process.stdin = MagicMock()
        mock_process.stdin.write = MagicMock()
        mock_process.stdin.close = MagicMock()
        mock_process.stdin.drain = AsyncMock()
        mock_process.communicate.return_value = (b"", b"")
        mock_process.returncode = 0
        mock_subprocess.return_value = mock_process
        
        frames = [b"frame1", b"frame2"]
        compiled = await compile_media(frames, "mp4", 30)
        
        self.assertEqual(compiled, b"compiled_video_data")
        mock_subprocess.assert_called_once()
        self.assertIn("libx264", mock_subprocess.call_args[0])
        mock_remove.assert_called_once()

    @patch("app.worker.asyncio.create_subprocess_exec")
    @patch("builtins.open", new_callable=unittest.mock.mock_open, read_data=b"compiled_gif_data")
    @patch("os.path.exists", return_value=True)
    @patch("os.remove")
    async def test_compile_media_gif(self, mock_remove, mock_exists, mock_open_file, mock_subprocess):
        # Set up subprocess mocks
        mock_process = AsyncMock()
        mock_process.stdin = MagicMock()
        mock_process.stdin.write = MagicMock()
        mock_process.stdin.close = MagicMock()
        mock_process.stdin.drain = AsyncMock()
        mock_process.communicate.return_value = (b"", b"")
        mock_process.returncode = 0
        mock_subprocess.return_value = mock_process
        
        frames = [b"frame1", b"frame2"]
        compiled = await compile_media(frames, "gif", 30)
        
        self.assertEqual(compiled, b"compiled_gif_data")
        mock_subprocess.assert_called_once()
        self.assertIn("paletteuse=dither=none", mock_subprocess.call_args[0][9])
        mock_remove.assert_called_once()

    @patch("app.worker.asyncio.create_subprocess_exec")
    @patch("os.path.exists", return_value=True)
    @patch("os.remove")
    async def test_compile_media_ffmpeg_failure(self, mock_remove, mock_exists, mock_subprocess):
        # Set up subprocess mocks with failure exit code
        mock_process = AsyncMock()
        mock_process.stdin = MagicMock()
        mock_process.stdin.write = MagicMock()
        mock_process.stdin.close = MagicMock()
        mock_process.stdin.drain = AsyncMock()
        mock_process.communicate.return_value = (b"", b"FFmpeg configuration error")
        mock_process.returncode = 1
        mock_subprocess.return_value = mock_process
        
        frames = [b"frame1"]
        with self.assertRaises(RuntimeError) as ctx:
            await compile_media(frames, "mp4", 30)
            
        self.assertIn("FFmpeg failed (exit code 1)", str(ctx.exception))
        mock_remove.assert_called_once()

    @patch("app.worker.resolve_spec")
    @patch("app.worker.render_frames")
    @patch("app.worker.compile_media")
    @patch("app.worker.MinioStorage")
    @patch("app.worker.update_job_status")
    async def test_process_job_standard_mp4(
        self, mock_update_status, mock_storage_class, mock_compile, mock_render, mock_resolve
    ):
        job_id = str(uuid.uuid4())
        payload = {"job_id": job_id, "spec": {"canvas": {"fps": 30}}, "format": "mp4"}
        
        mock_resolve.return_value = (payload["spec"], "dark")
        mock_render.return_value = [b"frame1", b"frame2"]
        mock_compile.return_value = b"video_bytes"
        
        mock_storage = MagicMock()
        mock_storage.upload_bytes.return_value = f"{job_id}.mp4"
        mock_storage.get_download_url.return_value = f"http://minio/{job_id}.mp4"
        mock_storage_class.return_value = mock_storage
        
        await process_job(payload)
        
        mock_update_status.assert_any_call(job_id, status="processing")
        mock_resolve.assert_called_once_with(job_id, payload["spec"])
        mock_render.assert_called_once_with(payload["spec"], "dark", "mp4")
        mock_compile.assert_called_once_with([b"frame1", b"frame2"], "mp4", 30)
        mock_storage.upload_bytes.assert_called_once_with(f"{job_id}.mp4", b"video_bytes", "video/mp4")
        mock_update_status.assert_any_call(job_id, status="completed", download_url=f"http://minio/{job_id}.mp4")

    @patch("app.worker.resolve_spec")
    @patch("app.worker.render_frames")
    @patch("app.worker.MinioStorage")
    @patch("app.worker.update_job_status")
    async def test_process_job_png_only(
        self, mock_update_status, mock_storage_class, mock_render, mock_resolve
    ):
        job_id = str(uuid.uuid4())
        payload = {"job_id": job_id, "spec": {"canvas": {"fps": 30}}, "format": "png"}
        
        mock_resolve.return_value = (payload["spec"], "dark")
        mock_render.return_value = [b"png_frame_bytes"]
        
        mock_storage = MagicMock()
        mock_storage.upload_bytes.return_value = f"{job_id}.png"
        mock_storage.get_download_url.return_value = f"http://minio/{job_id}.png"
        mock_storage_class.return_value = mock_storage
        
        await process_job(payload)
        
        mock_update_status.assert_any_call(job_id, status="processing")
        mock_render.assert_called_once_with(payload["spec"], "dark", "png")
        mock_storage.upload_bytes.assert_called_once_with(f"{job_id}.png", b"png_frame_bytes", "image/png")
        mock_update_status.assert_any_call(job_id, status="completed", download_url=f"http://minio/{job_id}.png", format="png")

    @patch("app.worker.resolve_spec")
    @patch("app.worker.render_frames")
    @patch("app.worker.MinioStorage")
    @patch("app.worker.update_job_status")
    async def test_process_job_zero_duration(
        self, mock_update_status, mock_storage_class, mock_render, mock_resolve
    ):
        job_id = str(uuid.uuid4())
        # Spec with frames=0 represents zero-duration export
        payload = {"job_id": job_id, "spec": {"canvas": {"frames": 0, "fps": 30}}, "format": "mp4"}
        
        mock_resolve.return_value = (payload["spec"], "dark")
        mock_render.return_value = [b"single_frame_bytes"]
        
        mock_storage = MagicMock()
        mock_storage.upload_bytes.return_value = f"{job_id}.png"
        mock_storage.get_download_url.return_value = f"http://minio/{job_id}.png"
        mock_storage_class.return_value = mock_storage
        
        await process_job(payload)
        
        mock_update_status.assert_any_call(job_id, status="processing")
        mock_render.assert_called_once_with(payload["spec"], "dark", "mp4")
        mock_storage.upload_bytes.assert_called_once_with(f"{job_id}.png", b"single_frame_bytes", "image/png")
        mock_update_status.assert_any_call(job_id, status="completed", download_url=f"http://minio/{job_id}.png", format="png")

    @patch("app.worker.resolve_spec")
    @patch("app.worker.render_frames")
    @patch("app.worker.update_job_status")
    async def test_process_job_browser_crash(
        self, mock_update_status, mock_render, mock_resolve
    ):
        job_id = str(uuid.uuid4())
        payload = {"job_id": job_id, "spec": {}, "format": "mp4"}
        
        mock_resolve.return_value = (payload["spec"], "dark")
        # Simulate Playwright browser crash Exception
        mock_render.side_effect = Exception("Chromium process exited unexpectedly")
        
        await process_job(payload)
        
        mock_update_status.assert_any_call(job_id, status="processing")
        mock_update_status.assert_any_call(
            job_id, status="failed", error_message="Chromium process exited unexpectedly"
        )

    @patch("app.worker.Redis.from_url")
    @patch("app.worker.process_job")
    async def test_worker_loop_execution(self, mock_process_job, mock_redis_from_url):
        mock_redis = AsyncMock()
        mock_redis_from_url.return_value = mock_redis
        
        payload_data = {"job_id": "test-job-id", "format": "mp4"}
        payload_bytes = json.dumps(payload_data).encode("utf-8")
        
        # First iteration returns the job, second returns None
        mock_redis.brpop.side_effect = [
            ("export-jobs", payload_bytes),
            None
        ]
        
        # Stop event to terminate the loop
        stop_event = asyncio.Event()
        
        # We run the loop in a background task so we can trigger the stop event
        loop_task = asyncio.create_task(worker_loop(stop_event))
        
        # Allow loop to execute
        await asyncio.sleep(0.1)
        stop_event.set()
        
        # Wait for task completion
        await loop_task
        
        mock_redis_from_url.assert_called_once()
        mock_redis.brpop.assert_called()
        mock_process_job.assert_called_once_with(payload_data)
        mock_redis.aclose.assert_called_once()


if __name__ == "__main__":
    unittest.main()
