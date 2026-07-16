import unittest
import asyncio
import socket
import threading
import uuid
import json
import base64
from unittest.mock import patch, MagicMock, AsyncMock

from app.worker import render_frames, compile_media, process_job, resolve_spec
from app.core.config import settings
from app.models import ExportJob, Diagram
from tests.e2e.mock_services import ThreadingHTTPServer, MockFrontendHandler, MockMinIOHandler

def find_free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    s.close()
    return port

class TestChallengerWorkerStress(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.port = find_free_port()
        cls.server = ThreadingHTTPServer(('127.0.0.1', cls.port), MockFrontendHandler)
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()
        # Override frontend URL to point to our local mock frontend
        cls.original_frontend_url = settings.FRONTEND_URL
        settings.FRONTEND_URL = f"http://127.0.0.1:{cls.port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        settings.FRONTEND_URL = cls.original_frontend_url

    async def test_zero_duration_mp4(self):
        """Verify worker handles a zero-duration export spec (frames=0) for mp4."""
        spec = {
            "canvas": {
                "width": 800,
                "height": 600,
                "fps": 30,
                "frames": 0
            },
            "elements": [{"id": "node_1", "type": "card"}]
        }
        # In this case, render_frames should set frames_count=1 and capture exactly 1 frame.
        frames = await render_frames(spec, "dark", "mp4")
        self.assertEqual(len(frames), 1)
        self.assertTrue(isinstance(frames[0], bytes))

    async def test_zero_duration_gif(self):
        """Verify worker handles a zero-duration export spec (duration=0) for gif."""
        spec = {
            "canvas": {
                "width": 800,
                "height": 600,
                "fps": 30,
                "duration": 0
            },
            "elements": [{"id": "node_1", "type": "card"}]
        }
        frames = await render_frames(spec, "dark", "gif")
        self.assertEqual(len(frames), 1)

    async def test_format_png(self):
        """Verify worker handles format='png'."""
        spec = {
            "canvas": {
                "width": 800,
                "height": 600,
                "fps": 30,
                "frames": 10
            },
            "elements": [{"id": "node_1", "type": "card"}]
        }
        frames = await render_frames(spec, "dark", "png")
        self.assertEqual(len(frames), 1)

    async def test_viewport_resizing_custom_resolutions(self):
        """Verify that the worker can resize viewports to small, large, and high-density bounds."""
        resolutions = [
            (100, 100),    # Extremely small resolution
            (3840, 2160),  # 4K resolution
            (1210, 1138)   # Non-standard custom resolution
        ]
        
        for w, h in resolutions:
            spec = {
                "canvas": {
                    "width": w,
                    "height": h,
                    "fps": 30,
                    "frames": 1
                },
                "elements": [{"id": "node_1", "type": "card"}]
            }
            frames = await render_frames(spec, "dark", "png")
            self.assertEqual(len(frames), 1)

    async def test_high_density_diagram_payload(self):
        """Stress test the worker with a very high density spec (e.g. 200 nodes)."""
        nodes = [{"id": f"node_{i}", "type": "card"} for i in range(200)]
        spec = {
            "canvas": {
                "width": 1920,
                "height": 1080,
                "fps": 30,
                "frames": 2
            },
            "elements": nodes
        }
        frames = await render_frames(spec, "dark", "mp4")
        self.assertEqual(len(frames), 2)

    async def test_missing_fields_and_null_values(self):
        """Verify resilience when elements have missing fields or null values in spec."""
        # Missing canvas spec
        spec_no_canvas = {
            "elements": [{"id": "node_1", "type": "card"}]
        }
        frames = await render_frames(spec_no_canvas, "dark", "mp4")
        # Fallback frames_count should be 41
        self.assertEqual(len(frames), 41)

        # Null values in width and height
        spec_null_canvas = {
            "canvas": {
                "width": None,
                "height": None,
                "fps": None,
                "frames": None,
                "duration": None
            },
            "elements": [{"id": "node_1", "type": "card"}]
        }
        frames = await render_frames(spec_null_canvas, "dark", "mp4")
        self.assertEqual(len(frames), 41)

        # Invalid spec elements format (handled gracefully or fails at resolver/runner)
        spec_invalid = {
            "canvas": {"width": 800, "height": 600, "frames": 1},
            "elements": None
        }
        # In this case, render_frames resolves spec.get("canvas") but doesn't validate diagram.
        # It should still capture a frame.
        frames = await render_frames(spec_invalid, "dark", "mp4")
        self.assertEqual(len(frames), 1)
