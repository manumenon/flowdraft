import asyncio
original_sleep = asyncio.sleep
import json
import os
import unittest
import uuid
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
from app.services.storage import MinioStorage

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

class TestWorkerAdversarial(unittest.IsolatedAsyncioTestCase):

    # ==========================================================================
    # 1. MinIO Upload / Presigned URL Generation Gaps
    # ==========================================================================

    @patch("app.worker.async_session_maker")
    @patch("app.worker.render_frames")
    @patch("app.worker.MinioStorage")
    async def test_minio_download_url_failure_sets_failed(
        self, mock_minio_storage_cls, mock_render_frames, mock_session_maker
    ):
        """Verify that when MinIO presigned URL generation fails (returns empty string),
        the job fails instead of silently marking it as completed with an empty URL."""
        job_id = uuid.uuid4()
        mock_job = ExportJob(id=job_id, status="queued", format="png")
        
        mock_session = AsyncMock()
        mock_session_maker.return_value.__aenter__.return_value = mock_session
        mock_session.execute.return_value = MockResult(mock_job)
        
        # Mock storage to return empty string for download URL (indicating failure)
        mock_storage = MagicMock()
        mock_storage.upload_bytes.return_value = "filename"
        mock_storage.get_download_url.return_value = ""
        mock_minio_storage_cls.return_value = mock_storage
        
        mock_render_frames.return_value = [b"frame_bytes"]
        
        payload = {"job_id": str(job_id), "format": "png", "spec": {"canvas": {"frames": 1}}}
        
        await process_job(payload)
        
        # Because the code is not hardened, it will mark it as completed.
        # We assert it should be failed, which makes the test FAIL against unhardened code.
        self.assertEqual(mock_job.status, "failed")
        self.assertIn("download URL", mock_job.error_message.lower())

    @patch("app.worker.async_session_maker")
    @patch("app.worker.render_frames")
    @patch("app.worker.MinioStorage")
    async def test_minio_upload_transient_failure_retry(
        self, mock_minio_storage_cls, mock_render_frames, mock_session_maker
    ):
        """Verify that a transient MinIO upload failure is retried and does not immediately fail the job."""
        job_id = uuid.uuid4()
        mock_job = ExportJob(id=job_id, status="queued", format="png")
        
        mock_session = AsyncMock()
        mock_session_maker.return_value.__aenter__.return_value = mock_session
        mock_session.execute.return_value = MockResult(mock_job)
        
        # Mock upload_bytes to raise ConnectionError on first call, succeed on second call
        mock_storage = MagicMock()
        mock_storage.upload_bytes.side_effect = [
            ConnectionError("MinIO connection timed out"),
            "filename"
        ]
        mock_storage.get_download_url.return_value = "http://download"
        mock_minio_storage_cls.return_value = mock_storage
        
        mock_render_frames.return_value = [b"frame_bytes"]
        
        payload = {"job_id": str(job_id), "format": "png", "spec": {"canvas": {"frames": 1}}}
        
        await process_job(payload)
        
        # Since unhardened code does not retry, it will fail on the first attempt and mark status as 'failed'.
        # We assert it should be 'completed' (because it should retry and succeed).
        # This makes the test FAIL against unhardened code.
        self.assertEqual(mock_job.status, "completed")

    # ==========================================================================
    # 2. Playwright Browser Crashes / Exception Masking
    # ==========================================================================

    @patch("app.worker.async_playwright")
    async def test_playwright_browser_crash_exception_masking(self, mock_async_playwright):
        """Verify that when the page/browser crashes, the close() call does not mask the original exception."""
        mock_playwright = AsyncMock()
        mock_browser = AsyncMock()
        mock_page = AsyncMock()
        
        mock_async_playwright.return_value = AsyncContextManagerMock(mock_playwright)
        mock_playwright.chromium.launch.return_value = mock_browser
        mock_browser.new_page.return_value = mock_page
        
        # Mock screenshot to raise a target crashed exception
        mock_page.screenshot.side_effect = Exception("Target crashed: Page crashed")
        # Mock close to raise a connection closed exception (because browser has crashed)
        mock_browser.close.side_effect = Exception("Failed to close browser: connection closed")
        
        spec = {"canvas": {"width": 800, "height": 600, "fps": 10, "frames": 3}}
        
        # We expect the root cause (Page crashed) to be raised
        try:
            await render_frames(spec, "dark", "mp4")
            self.fail("render_frames did not raise any exception")
        except Exception as e:
            # We assert that the exception message is the page crash message, not the close message.
            # Because the code is unhardened, the finally block will execute browser.close(),
            # raising "Failed to close browser: connection closed" and masking "Target crashed: Page crashed".
            # Thus, the test will fail!
            self.assertIn("Target crashed", str(e))

    # ==========================================================================
    # 3. Worker-Redis Connection Drops / Exponential Backoff
    # ==========================================================================

    @patch("app.worker.Redis.from_url")
    @patch("app.worker.asyncio.sleep")
    async def test_worker_redis_connection_loss_backoff(self, mock_sleep, mock_redis_from_url):
        """Verify that the worker loop implements exponential backoff on Redis connection failures
        to avoid log spam and connection flooding."""
        mock_redis = AsyncMock()
        mock_redis_from_url.return_value = mock_redis
        
        # Raise ConnectionError on brpop repeatedly
        mock_redis.brpop.side_effect = [
            ConnectionError("Redis connection lost"),
            ConnectionError("Redis connection lost"),
            ConnectionError("Redis connection lost"),
            # Stop the loop after 3 iterations by raising CancelledError
            asyncio.CancelledError()
        ]
        
        # Capture the sleep values
        sleep_durations = []
        async def mock_sleep_fn(delay):
            sleep_durations.append(delay)
            # Yield control so loop can continue
            await original_sleep(0.001)
        mock_sleep.side_effect = mock_sleep_fn
        
        stop_event = asyncio.Event()
        try:
            await worker_loop(stop_event)
        except asyncio.CancelledError:
            pass
            
        # We expect the backoff to increase (e.g. at least second sleep > first sleep)
        # Since unhardened code always sleeps for 1.0 seconds, sleep_durations will be [1.0, 1.0, 1.0]
        self.assertGreater(len(sleep_durations), 1)
        self.assertGreater(sleep_durations[1], sleep_durations[0], 
                           f"Expected backoff sleep times to increase, got {sleep_durations}")

    # ==========================================================================
    # 4. Parallel Job Starvation / Sequential Blocking
    # ==========================================================================

    @patch("app.worker.Redis.from_url")
    @patch("app.worker.process_job")
    async def test_parallel_job_starvation(self, mock_process_job, mock_redis_from_url):
        """Verify that the worker can process multiple jobs concurrently or at least does not starve
        subsequent jobs when one job is slow/blocked."""
        mock_redis = AsyncMock()
        mock_redis_from_url.return_value = mock_redis
        
        job_a_payload = {"job_id": "job_a", "format": "mp4"}
        job_b_payload = {"job_id": "job_b", "format": "mp4"}
        
        # Return job A, then job B, then block
        mock_redis.brpop.side_effect = [
            ("export-jobs", json.dumps(job_a_payload).encode("utf-8")),
            ("export-jobs", json.dumps(job_b_payload).encode("utf-8")),
            asyncio.CancelledError()
        ]
        
        completion_order = []
        
        # Mock process_job to simulate slow job A and fast job B
        async def mock_process_job_fn(payload):
            job_id = payload["job_id"]
            if job_id == "job_a":
                # Slow job A yields control and sleeps
                await asyncio.sleep(0.5)
            else:
                # Fast job B
                await asyncio.sleep(0.01)
            completion_order.append(job_id)
            
        mock_process_job.side_effect = mock_process_job_fn
        
        stop_event = asyncio.Event()
        try:
            await worker_loop(stop_event)
        except asyncio.CancelledError:
            pass
            
        # If the worker is concurrent/hardened, job B should finish before job A (since A takes 0.5s and B takes 0.01s).
        # Since the unhardened worker is strictly sequential, A will start and block the loop, finishing first,
        # then B will start and finish second.
        # We assert that job B should complete first, which will fail for the unhardened sequential worker.
        self.assertEqual(completion_order, ["job_b", "job_a"])

    # ==========================================================================
    # 5. FFmpeg Subprocess Process Leak on Cancellation
    # ==========================================================================

    @patch("app.worker.asyncio.create_subprocess_exec")
    @patch("os.path.exists", return_value=True)
    @patch("os.remove")
    async def test_ffmpeg_process_leak_on_cancellation(self, mock_remove, mock_exists, mock_subprocess):
        """Verify that if the compile_media task is cancelled mid-execution,
        the running FFmpeg subprocess is killed cleanly rather than leaked."""
        mock_process = AsyncMock()
        mock_process.kill = MagicMock()
        mock_process.stdin = MagicMock()
        
        # Make stdin.drain block/sleep so we can cancel during it
        async def mock_drain():
            await asyncio.sleep(10)
        mock_process.stdin.drain.side_effect = mock_drain
        mock_subprocess.return_value = mock_process
        
        frames = [b"frame1", b"frame2"]
        
        # Start compile_media in a task
        task = asyncio.create_task(compile_media(frames, "mp4", 30))
        
        # Let it run until it blocks in stdin.drain
        await asyncio.sleep(0.05)
        
        # Cancel the task
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
            
        # Assert that process.kill was called.
        # Because the unhardened code does not handle CancelledError or kill the process in finally,
        # process.kill will NOT be called, and this assert will fail!
        mock_process.kill.assert_called_once()


if __name__ == "__main__":
    unittest.main()
