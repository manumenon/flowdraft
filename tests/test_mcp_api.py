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
    list_saved_diagrams,
    get_saved_diagram,
    delete_saved_diagram,
    trigger_export,
    get_export_status,
    get_schema_resource,
    get_default_template_resource,
    create_architecture_diagram_prompt,
    STARTER_TEMPLATES
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
        sql_str = str(compiled).lower()

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
            if "user_id" in sql_str:
                user_id_val = None
                for k, v in params.items():
                    if "user_id" in k:
                        user_id_val = v
                        break
                if user_id_val:
                    matches = [d for d in self.diagrams_list if str(d.user_id) == str(user_id_val)]
                    return MockResult(matches)

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


class TestMCPAPI(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        settings.MCP_API_KEYS = "test-key-1,test-key-2"
        self.sample_spec = STARTER_TEMPLATES["dataflow"]
        self.mock_db = MockAsyncSession()

    # ------------------------------------------------------------------
    # Middleware Auth Tests
    # ------------------------------------------------------------------

    def test_mcp_unauthorized_no_key(self):
        response = self.client.get("/api/v1/mcp/sse")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "MCP API Key is missing")

        response = self.client.post("/api/v1/mcp/messages/")
        self.assertEqual(response.status_code, 401)

    def test_mcp_forbidden_invalid_key(self):
        response = self.client.post("/api/v1/mcp/messages/", headers={"X-MCP-API-Key": "wrong-key"})
        self.assertEqual(response.status_code, 403)

        response = self.client.post("/api/v1/mcp/messages/?api_key=wrong-key")
        self.assertEqual(response.status_code, 403)

    def test_mcp_authorized_headers(self):
        response = self.client.post("/api/v1/mcp/messages/", headers={"X-MCP-API-Key": "test-key-1"})
        self.assertIn(response.status_code, [400, 404])

    def test_mcp_api_prefix_handling(self):
        response = self.client.post("/api/mcp/messages/", headers={"X-MCP-API-Key": "test-key-2"})
        self.assertIn(response.status_code, [400, 404])

    # ------------------------------------------------------------------
    # Tool Execution Direct Tests
    # ------------------------------------------------------------------

    def test_compile_diagram_success(self):
        res = asyncio.run(compile_diagram(self.sample_spec))
        self.assertIn("Diagram compiled successfully", res)
        self.assertIn("Realtime Dataflow Engine", res)

    def test_compile_diagram_failure(self):
        invalid_spec = {"version": "2.0"} # missing title/elements
        res = asyncio.run(compile_diagram(invalid_spec))
        self.assertIn("Compilation failed", res)

    def test_validate_diagram_spec_valid(self):
        res_str = asyncio.run(validate_diagram_spec(self.sample_spec))
        data = json.loads(res_str)
        self.assertTrue(data["valid"])
        self.assertEqual(data["element_count"], 4)
        self.assertEqual(data["connection_count"], 3)

    def test_validate_diagram_spec_invalid(self):
        res_str = asyncio.run(validate_diagram_spec({}))
        data = json.loads(res_str)
        self.assertFalse(data["valid"])

    def test_list_templates(self):
        res_str = asyncio.run(list_templates())
        data = json.loads(res_str)
        self.assertIn("templates", data)
        names = [t["name"] for t in data["templates"]]
        self.assertIn("dataflow", names)
        self.assertIn("microservices", names)

    def test_get_template(self):
        res_str = asyncio.run(get_template("dataflow"))
        data = json.loads(res_str)
        self.assertEqual(data["theme"], "dark")

        err = asyncio.run(get_template("non_existent"))
        self.assertIn("Error: Template 'non_existent' not found", err)

    def test_diagram_crud_lifecycle(self):
        with patch("app.api.v1.mcp.async_session_maker", return_value=self.mock_db):
            # 1. Save diagram
            save_res = asyncio.run(save_diagram("Test Spec", self.sample_spec, "MCP test diagram"))
            self.assertIn("Diagram saved successfully", save_res)
            diag_id = save_res.split("diagram_id: ")[1].strip()

            # 2. List saved diagrams
            list_res = asyncio.run(list_saved_diagrams(limit=5))
            list_data = json.loads(list_res)
            ids = [d["id"] for d in list_data]
            self.assertIn(diag_id, ids)

            # 3. Get saved diagram
            get_res = asyncio.run(get_saved_diagram(diag_id))
            get_data = json.loads(get_res)
            self.assertEqual(get_data["title"], "Test Spec")

            # 4. Delete saved diagram
            del_res = asyncio.run(delete_saved_diagram(diag_id))
            self.assertIn("deleted successfully", del_res)

    def test_trigger_and_status_export(self):
        with patch("app.api.v1.mcp.async_session_maker", return_value=self.mock_db):
            with patch("app.api.v1.mcp.RedisBroker") as MockBroker:
                mock_inst = AsyncMock()
                mock_inst.enqueue_export_job.return_value = None
                MockBroker.return_value = mock_inst

                # Trigger export
                trigger_res = asyncio.run(trigger_export(self.sample_spec, "gif"))
                self.assertIn("Export job triggered successfully", trigger_res)
                job_id = trigger_res.split("job_id: ")[1].strip()

                # Query status
                status_res = asyncio.run(get_export_status(job_id))
                self.assertIn(f"Job ID: {job_id}", status_res)
                self.assertIn("Status: queued", status_res)

    # ------------------------------------------------------------------
    # Resources & Prompts Tests
    # ------------------------------------------------------------------

    def test_mcp_resources(self):
        schema_json = get_schema_resource()
        schema_data = json.loads(schema_json)
        self.assertEqual(schema_data["version"], "2.0")
        self.assertIn("card", schema_data["supported_element_types"])

        tmpl_json = get_default_template_resource()
        tmpl_data = json.loads(tmpl_json)
        self.assertEqual(tmpl_data["version"], "2.0")

    def test_mcp_prompt(self):
        prompt_txt = create_architecture_diagram_prompt("Cloud Microservices")
        self.assertIn("Cloud Microservices", prompt_txt)
        self.assertIn("FlowDraft V2 diagram spec", prompt_txt)

if __name__ == "__main__":
    unittest.main()
