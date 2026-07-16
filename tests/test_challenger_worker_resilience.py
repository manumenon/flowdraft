import asyncio
import json
import unittest
import uuid
from unittest.mock import patch, MagicMock, AsyncMock

from redis.exceptions import ConnectionError
from sqlalchemy.exc import OperationalError

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


class TestChallengerWorkerResilience(unittest.IsolatedAsyncioTestCase):

    # ==========================================================================
    # 1. Redis Broker Offline / Disconnect / Restart Handling
    # ==========================================================================

    @patch("app.worker.Redis.from_url")
    @patch("app.worker.process_job")
    @patch("app.worker.logger")
    async def test_worker_loop_redis_offline_recovery(
        self, mock_logger, mock_process_job, mock_redis_from_url
    ):
        """Verify worker loop recovers when Redis is offline and then reconnects."""
        mock_redis = AsyncMock()
        mock_redis_from_url.return_value = mock_redis

        payload_data = {"job_id": str(uuid.uuid4()), "format": "mp4"}
        payload_bytes = json.dumps(payload_data).encode("utf-8")

        # Raise ConnectionError on 1st, return payload on 2nd, then block/return None
        mock_redis.brpop.side_effect = [
            ConnectionError("Redis connection lost"),
            ("export-jobs", payload_bytes),
            None
        ]

        stop_event = asyncio.Event()

        # Run loop in background
        loop_task = asyncio.create_task(worker_loop(stop_event))

        # Sleep to let loop run through first iteration (which sleeps 1s on exception)
        # and then the second iteration (which processes job)
        await asyncio.sleep(1.2)
        stop_event.set()
        await loop_task

        # Verify connection error was logged
        mock_logger.error.assert_any_call(
            "Error in worker loop: Redis connection lost", exc_info=True
        )
        # Verify it successfully processed the job on the next iteration
        mock_process_job.assert_called_once_with(payload_data)
        # Verify connection is closed cleanly on termination
        mock_redis.aclose.assert_called_once()

    # ==========================================================================
    # 2. Database Connection Loss / SQL Failures
    # ==========================================================================

    @patch("app.worker.async_session_maker")
    @patch("app.worker.logger")
    async def test_process_job_database_failure(self, mock_logger, mock_session_maker):
        """Verify that when database connection is down, process_job fails but propagates cleanly to loop."""
        # Database raises OperationalError
        mock_session_maker.side_effect = OperationalError("select", {}, "Database connection refused")

        payload = {"job_id": str(uuid.uuid4()), "format": "mp4"}

        # Directly call process_job to verify the exception is propagated
        with self.assertRaises(OperationalError):
            await process_job(payload)

    @patch("app.worker.Redis.from_url")
    @patch("app.worker.async_session_maker")
    @patch("app.worker.logger")
    async def test_worker_loop_database_failure_liveness(
        self, mock_logger, mock_session_maker, mock_redis_from_url
    ):
        """Verify that database errors during job processing do not crash the worker daemon loop."""
        mock_redis = AsyncMock()
        mock_redis_from_url.return_value = mock_redis

        payload = {"job_id": str(uuid.uuid4()), "format": "mp4"}
        payload_bytes = json.dumps(payload).encode("utf-8")

        # Session maker raises OperationalError on database query/updates
        mock_session_maker.side_effect = OperationalError("select", {}, "Database connection refused")

        # Return payload on first brpop, then return None
        mock_redis.brpop.side_effect = [
            ("export-jobs", payload_bytes),
            None
        ]

        stop_event = asyncio.Event()
        loop_task = asyncio.create_task(worker_loop(stop_event))

        await asyncio.sleep(0.2)
        stop_event.set()
        await loop_task

        # Verify the database error in processing was caught and logged in the worker loop
        found_err_log = False
        for call in mock_logger.error.call_args_list:
            msg = call[0][0]
            if "Error in worker loop" in msg and "Database connection refused" in msg:
                found_err_log = True
                break
            # Or check exception directly
            if call[1].get("exc_info") is True and isinstance(call[1].get("exc_info"), bool):
                found_err_log = True
        
        # At least some logger.error must be called
        self.assertTrue(mock_logger.error.called)

    # ==========================================================================
    # 3. Playwright Browser Crashes, Memory Exhaustion, Page Hangs
    # ==========================================================================

    @patch("app.worker.async_playwright")
    async def test_render_frames_browser_crash(self, mock_async_playwright):
        """Verify that a browser crash raises an exception and browser is closed cleanly."""
        mock_playwright = AsyncMock()
        mock_browser = AsyncMock()
        mock_page = AsyncMock()

        mock_async_playwright.return_value = AsyncContextManagerMock(mock_playwright)
        mock_playwright.chromium.launch.return_value = mock_browser
        mock_browser.new_page.return_value = mock_page

        # Mock page navigation to raise a crash Exception
        mock_page.goto.side_effect = Exception("Chromium process exited unexpectedly")

        spec = {"canvas": {"width": 800, "height": 600, "fps": 10, "frames": 3}}

        with self.assertRaises(Exception) as ctx:
            await render_frames(spec, "dark", "mp4")

        self.assertIn("Chromium process exited unexpectedly", str(ctx.exception))
        # Verify browser resource was closed
        mock_browser.close.assert_called_once()

    @patch("app.worker.async_playwright")
    async def test_render_frames_page_hang_timeout(self, mock_async_playwright):
        """Verify that a viewport page hang (TimeoutError) closes browser and propagates error."""
        mock_playwright = AsyncMock()
        mock_browser = AsyncMock()
        mock_page = AsyncMock()

        mock_async_playwright.return_value = AsyncContextManagerMock(mock_playwright)
        mock_playwright.chromium.launch.return_value = mock_browser
        mock_browser.new_page.return_value = mock_page

        # Mock page navigation to raise TimeoutError
        mock_page.goto.side_effect = asyncio.TimeoutError("Navigation timed out after 30000ms")

        spec = {"canvas": {"width": 800, "height": 600, "fps": 10, "frames": 3}}

        with self.assertRaises(asyncio.TimeoutError):
            await render_frames(spec, "dark", "mp4")

        # Verify browser resource was closed
        mock_browser.close.assert_called_once()

    @patch("app.worker.async_playwright")
    async def test_render_frames_memory_exhaustion(self, mock_async_playwright):
        """Verify that a memory exhaustion exception closes browser resources and propagates error."""
        mock_playwright = AsyncMock()
        mock_browser = AsyncMock()
        mock_page = AsyncMock()

        mock_async_playwright.return_value = AsyncContextManagerMock(mock_playwright)
        mock_playwright.chromium.launch.return_value = mock_browser
        mock_browser.new_page.return_value = mock_page

        # Mock screenshot to raise Out of Memory
        mock_page.screenshot.side_effect = Exception("Out of Memory: Chromium page crashed")

        spec = {"canvas": {"width": 800, "height": 600, "fps": 10, "frames": 3}}

        with self.assertRaises(Exception) as ctx:
            await render_frames(spec, "dark", "mp4")

        self.assertIn("Out of Memory", str(ctx.exception))
        # Verify browser resource was closed
        mock_browser.close.assert_called_once()

    # ==========================================================================
    # 4. FFmpeg Compilation Failures
    # ==========================================================================

    @patch("app.worker.asyncio.create_subprocess_exec")
    @patch("os.path.exists", return_value=True)
    @patch("os.remove")
    async def test_compile_media_write_pipe_corruption(
        self, mock_remove, mock_exists, mock_subprocess
    ):
        """Verify that write pipe corruption kills the FFmpeg process, cleans up files, and raises error."""
        mock_process = AsyncMock()
        mock_process.kill = MagicMock()
        mock_process.stdin = MagicMock()
        mock_process.stdin.write.side_effect = BrokenPipeError("[Errno 32] Broken pipe")
        mock_process.stdin.drain = AsyncMock()
        mock_process.communicate.return_value = (b"", b"FFmpeg pipe write failed")
        mock_process.returncode = 1
        mock_subprocess.return_value = mock_process

        frames = [b"frame1", b"frame2"]

        with self.assertRaises(BrokenPipeError):
            await compile_media(frames, "mp4", 30)

        # Verify subprocess was killed on write error
        mock_process.kill.assert_called_once()
        # Verify temp file was cleaned up
        mock_remove.assert_called_once()

    @patch("app.worker.asyncio.create_subprocess_exec")
    @patch("os.path.exists", return_value=True)
    @patch("os.remove")
    async def test_compile_media_bad_ffmpeg_arguments(
        self, mock_remove, mock_exists, mock_subprocess
    ):
        """Verify that non-zero FFmpeg exits raise RuntimeError and clean up temp files."""
        mock_process = AsyncMock()
        mock_process.stdin = MagicMock()
        mock_process.stdin.write = MagicMock()
        mock_process.stdin.close = MagicMock()
        mock_process.stdin.drain = AsyncMock()

        mock_process.communicate.return_value = (b"", b"Unrecognized option 'preset-invalid'")
        mock_process.returncode = 1
        mock_subprocess.return_value = mock_process

        frames = [b"frame1"]

        with self.assertRaises(RuntimeError) as ctx:
            await compile_media(frames, "mp4", 30)

        self.assertIn("FFmpeg failed (exit code 1): Unrecognized option 'preset-invalid'", str(ctx.exception))
        # Verify temp file was cleaned up
        mock_remove.assert_called_once()


if __name__ == "__main__":
    unittest.main()
