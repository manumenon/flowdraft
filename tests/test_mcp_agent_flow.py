import sys
import os
import uuid
import unittest
import json
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

# Ensure backend directory is in sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings
from app.models import User, Diagram, ExportJob
from app.api.v1.mcp import (
    compile_diagram,
    validate_diagram_spec,
    list_templates,
    get_template,
    save_diagram,
    trigger_export,
    get_export_status,
)

class MockResult:
    def __init__(self, data):
        self._data = data

    def scalars(self):
        return self

    def all(self):
        return self._data

    def first(self):
        return self._data[0] if self._data else None

    def scalar_one_or_none(self):
        return self._data[0] if self._data else None

    def scalar(self):
        return self._data[0] if self._data else None


class MockAsyncSession:
    def __init__(self):
        self.added = []
        self.deleted = []
        self.users_list = []
        self.diagrams_list = []
        self.export_jobs_list = []

    def add(self, obj):
        if not hasattr(obj, "id") or getattr(obj, "id") is None:
            obj.id = uuid.uuid4()
        if isinstance(obj, User):
            self.users_list.append(obj)
        elif isinstance(obj, Diagram):
            self.diagrams_list.append(obj)
        elif isinstance(obj, ExportJob):
            self.export_jobs_list.append(obj)
        self.added.append(obj)

    async def delete(self, obj):
        self.deleted.append(obj)
        if isinstance(obj, Diagram) and obj in self.diagrams_list:
            self.diagrams_list.remove(obj)
        elif isinstance(obj, ExportJob) and obj in self.export_jobs_list:
            self.export_jobs_list.remove(obj)

    async def commit(self):
        pass

    async def refresh(self, obj):
        pass

    async def execute(self, stmt):
        model = stmt.column_descriptions[0]["type"]
        compiled = stmt.compile()
        params = compiled.params

        if model == User:
            email_val = None
            for k, v in params.items():
                if isinstance(v, str) and "@" in v:
                    email_val = v
                    break
            if email_val:
                matches = [u for u in self.users_list if u.email == email_val]
                return MockResult(matches)
            return MockResult(self.users_list)

        elif model == Diagram:
            diagram_id_val = None
            for k, v in params.items():
                if "id" in k and "user_id" not in k:
                    diagram_id_val = v
                    break
            if diagram_id_val:
                matches = [d for d in self.diagrams_list if str(d.id) == str(diagram_id_val)]
                return MockResult(matches)
            return MockResult(self.diagrams_list)

        elif model == ExportJob:
            job_id_val = None
            for k, v in params.items():
                if "id" in k:
                    job_id_val = v
                    break
            if job_id_val:
                matches = [j for j in self.export_jobs_list if str(j.id) == str(job_id_val)]
                return MockResult(matches)
            return MockResult(self.export_jobs_list)

        return MockResult([])

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


class TestMCPAgentFlow(unittest.TestCase):
    """
    End-to-End automated verification test simulating an external AI Agent workflow connecting
    to the FlowDraft MCP Server over SSE, retrieving templates, building and validating custom specs,
    compiling layout geometry, triggering GIF/PNG exports, and verifying completion status & download URLs.
    """

    def setUp(self):
        self.client = TestClient(app)
        settings.MCP_API_KEYS = "default-mcp-key,test-agent-key"
        self.mock_db = MockAsyncSession()

    def test_mcp_authentication_handshake(self):
        """Step 1: Test authentication handshake over SSE and HTTP endpoints."""
        # 1a. Missing API key -> 401 Unauthorized
        res_401 = self.client.get("/api/v1/mcp/sse")
        self.assertEqual(res_401.status_code, 401)
        self.assertEqual(res_401.json()["detail"], "MCP API Key is missing")

        # 1b. Invalid API key -> 403 Forbidden
        res_403 = self.client.get("/api/v1/mcp/sse?api_key=invalid-key-xyz")
        self.assertEqual(res_403.status_code, 403)
        self.assertEqual(res_403.json()["detail"], "Invalid MCP API Key")

        # 1c. Valid header auth -> 200 Health check & endpoint accessible
        res_health = self.client.get("/api/v1/mcp/health", headers={"X-MCP-API-Key": "default-mcp-key"})
        self.assertEqual(res_health.status_code, 200)
        self.assertEqual(res_health.json()["status"], "healthy")

    def test_full_ai_agent_diagram_creation_and_export_flow(self):
        """Simulates complete 7-step AI agent workflow."""

        # ----------------------------------------------------------------------
        # Step 1: Discover starter templates
        # ----------------------------------------------------------------------
        list_resp = asyncio.run(list_templates())
        list_data = json.loads(list_resp)
        self.assertIn("templates", list_data)
        tmpl_names = [t["name"] for t in list_data["templates"]]
        self.assertIn("dataflow", tmpl_names)
        self.assertIn("microservices", tmpl_names)
        self.assertIn("auth_flow", tmpl_names)

        # ----------------------------------------------------------------------
        # Step 2: Retrieve starter template "dataflow"
        # ----------------------------------------------------------------------
        tmpl_resp = asyncio.run(get_template("dataflow"))
        spec = json.loads(tmpl_resp)
        self.assertEqual(spec["version"], "2.0")
        self.assertEqual(spec["theme"], "dark")
        self.assertEqual(len(spec["elements"]), 4)

        # ----------------------------------------------------------------------
        # Step 3: Customize diagram spec (Add Redis cache cluster & connection)
        # ----------------------------------------------------------------------
        spec["title"]["prefix"] = "Enterprise"
        spec["title"]["highlight"] = "Dataflow Pipeline"
        spec["elements"].append({
            "id": "cache_redis",
            "type": "card",
            "title": "Redis Cache",
            "body": "In-memory cache for fast lookups",
            "icon": "package"
        })
        spec["connections"].append({
            "from": "proc_core",
            "to": "cache_redis",
            "label": "Cache Hit",
            "style": "dashed"
        })

        # ----------------------------------------------------------------------
        # Step 4: Validate customized spec
        # ----------------------------------------------------------------------
        val_resp = asyncio.run(validate_diagram_spec(spec))
        val_data = json.loads(val_resp)
        self.assertTrue(val_data["valid"], f"Spec validation failed: {val_data}")
        self.assertEqual(val_data["element_count"], 5)
        self.assertEqual(val_data["connection_count"], 4)
        self.assertEqual(len(val_data["warnings"]), 0)

        # ----------------------------------------------------------------------
        # Step 5: Compile diagram layout & positioning geometry
        # ----------------------------------------------------------------------
        compile_resp = asyncio.run(compile_diagram(spec))
        compile_data = json.loads(compile_resp)
        self.assertEqual(compile_data["status"], "compiled")
        self.assertEqual(compile_data["title"], "Enterprise Dataflow Pipeline")
        self.assertGreaterEqual(compile_data["element_count"], 5)
        self.assertEqual(compile_data["connection_count"], 4)
        self.assertIn("bounding_box", compile_data)
        bbox = compile_data["bounding_box"]
        self.assertGreater(bbox["width"], 0)
        self.assertGreater(bbox["height"], 0)
        self.assertIn("nodes", compile_data)
        node_ids = [n["id"] for n in compile_data["nodes"]]
        self.assertIn("cache_redis", node_ids)

        # ----------------------------------------------------------------------
        # Step 6: Save diagram and trigger GIF & PNG exports
        # ----------------------------------------------------------------------
        with patch("app.api.v1.mcp.async_session_maker", return_value=self.mock_db):
            with patch("app.api.v1.mcp.RedisBroker") as MockBroker:
                mock_broker = AsyncMock()
                mock_broker.enqueue_export_job.return_value = None
                MockBroker.return_value = mock_broker

                # Save diagram
                save_resp = asyncio.run(save_diagram("Enterprise Dataflow Pipeline", spec, "Customized pipeline"))
                save_data = json.loads(save_resp)
                self.assertEqual(save_data["status"], "saved")
                self.assertIn("diagram_id", save_data)

                # Trigger GIF export
                gif_resp = asyncio.run(trigger_export(spec, format="gif"))
                gif_data = json.loads(gif_resp)
                self.assertEqual(gif_data["status"], "queued")
                self.assertEqual(gif_data["format"], "gif")
                gif_job_id = gif_data["job_id"]
                self.assertTrue(uuid.UUID(gif_job_id))

                # Trigger PNG export
                png_resp = asyncio.run(trigger_export(spec, format="png"))
                png_data = json.loads(png_resp)
                self.assertEqual(png_data["status"], "queued")
                self.assertEqual(png_data["format"], "png")
                png_job_id = png_data["job_id"]
                self.assertTrue(uuid.UUID(png_job_id))

                # ----------------------------------------------------------------------
                # Step 7: Poll export job status & verify completion artifacts
                # ----------------------------------------------------------------------
                # Initial status is queued
                status_initial = asyncio.run(get_export_status(gif_job_id))
                status_init_data = json.loads(status_initial)
                self.assertEqual(status_init_data["status"], "queued")
                self.assertIsNone(status_init_data["download_url"])

                # Simulate render worker marking GIF job completed
                for job in self.mock_db.export_jobs_list:
                    if str(job.id) == gif_job_id:
                        job.status = "completed"
                    elif str(job.id) == png_job_id:
                        job.status = "completed"

                with patch("app.api.v1.mcp.MinioStorage") as MockMinio:
                    mock_storage = MagicMock()
                    mock_storage.get_download_url.return_value = f"http://localhost:9000/exports/{gif_job_id}.gif"
                    mock_stat = MagicMock()
                    mock_stat.size = 1048576  # 1MB
                    mock_storage.client = MagicMock()
                    mock_storage.client.stat_object.return_value = mock_stat
                    MockMinio.return_value = mock_storage

                    # Verify completed GIF status
                    gif_final_resp = asyncio.run(get_export_status(gif_job_id))
                    gif_final_data = json.loads(gif_final_resp)
                    self.assertEqual(gif_final_data["status"], "completed")
                    self.assertEqual(gif_final_data["download_url"], f"/api/v1/export/{gif_job_id}/download")
                    self.assertIn("exports", gif_final_data["presigned_url"])
                    self.assertEqual(gif_final_data["file_size"], 1048576)

                    # Verify completed PNG status
                    png_final_resp = asyncio.run(get_export_status(png_job_id))
                    png_final_data = json.loads(png_final_resp)
                    self.assertEqual(png_final_data["status"], "completed")
                    self.assertEqual(png_final_data["download_url"], f"/api/v1/export/{png_job_id}/download")
                    self.assertEqual(png_final_data["file_size"], 1048576)


if __name__ == "__main__":
    unittest.main()
