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
        data = json.loads(res)
        self.assertEqual(data["status"], "compiled")
        self.assertEqual(data["title"], "Realtime Dataflow Engine")
        self.assertIn("bounding_box", data)
        self.assertGreaterEqual(data["element_count"], 4)
        self.assertEqual(data["connection_count"], 3)

    def test_compile_diagram_failure(self):
        invalid_spec = {"version": "2.0"} # missing title/elements
        res = asyncio.run(compile_diagram(invalid_spec))
        data = json.loads(res)
        self.assertEqual(data["status"], "error")
        self.assertIn("Compilation failed", data["error"])

    def test_compile_diagram_ts_engine_nested_panels_no_overlap(self):
        # Stage 6b regression: compile_diagram is now bridged to the TS
        # layout engine (backend/app/services/ts_layout_bridge.py) instead
        # of the legacy Python compile_spec()+layout() pair. This spec has
        # nested panels (elements inside panels) and a panel footer
        # (`center_panel`'s footer -> `center_footer`), so it exercises the
        # parent-relative -> absolute coordinate accumulation the bridge is
        # responsible for, not just flat/simple specs.
        default_spec_path = os.path.join(project_root, "assets", "default-spec-v2.json")
        with open(default_spec_path, "r", encoding="utf-8") as f:
            spec = json.load(f)

        res = asyncio.run(compile_diagram(spec))
        data = json.loads(res)

        self.assertEqual(data["status"], "compiled", data.get("error"))
        self.assertGreater(data["element_count"], 20)
        self.assertGreater(data["connection_count"], 0)
        self.assertIn("bounding_box", data)

        nodes = data["nodes"]
        self.assertTrue(len(nodes) > 0)

        # Every node must be positively/sanely positioned and sized.
        for n in nodes:
            self.assertIsInstance(n["x"], (int, float))
            self.assertIsInstance(n["y"], (int, float))
            self.assertGreaterEqual(n["width"], 0)
            self.assertGreaterEqual(n["height"], 0)

        # A nested panel's children must actually be positioned (a bridge
        # bug in the parent-relative -> absolute conversion would leave
        # these at (0, 0) or outside their panel's bounds).
        by_id = {n["id"]: n for n in nodes}
        self.assertIn("center_panel", by_id)
        self.assertIn("center_footer", by_id)
        panel = by_id["center_panel"]
        footer = by_id["center_footer"]
        self.assertGreaterEqual(footer["x"], panel["x"] - 2)
        self.assertGreaterEqual(footer["y"], panel["y"] - 2)
        self.assertLessEqual(footer["x"] + footer["width"], panel["x"] + panel["width"] + 2)
        self.assertLessEqual(footer["y"] + footer["height"], panel["y"] + panel["height"] + 2)

        # No two sibling node rects (same parent, including top-level
        # siblings sharing `parent: None`) may overlap.
        siblings_by_parent = {}
        for n in nodes:
            siblings_by_parent.setdefault(n["parent"], []).append(n)

        def rects_overlap(a, b):
            ax1, ay1, ax2, ay2 = a["x"], a["y"], a["x"] + a["width"], a["y"] + a["height"]
            bx1, by1, bx2, by2 = b["x"], b["y"], b["x"] + b["width"], b["y"] + b["height"]
            ix = min(ax2, bx2) - max(ax1, bx1)
            iy = min(ay2, by2) - max(ay1, by1)
            return ix > 1 and iy > 1  # >1px tolerance for touching edges

        overlaps = []
        for sibs in siblings_by_parent.values():
            for i in range(len(sibs)):
                for j in range(i + 1, len(sibs)):
                    if rects_overlap(sibs[i], sibs[j]):
                        overlaps.append((sibs[i]["id"], sibs[j]["id"]))

        self.assertEqual(overlaps, [], f"Found overlapping sibling node rects: {overlaps}")

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
        err_data = json.loads(err)
        self.assertIn("non_existent", err_data["error"])

    def test_diagram_crud_lifecycle(self):
        with patch("app.api.v1.mcp.async_session_maker", return_value=self.mock_db):
            # 1. Save diagram
            save_res = asyncio.run(save_diagram("Test Spec", self.sample_spec, "MCP test diagram"))
            save_data = json.loads(save_res)
            self.assertEqual(save_data["status"], "saved")
            diag_id = save_data["diagram_id"]

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
            del_data = json.loads(del_res)
            self.assertEqual(del_data["status"], "deleted")

    def test_trigger_and_status_export(self):
        with patch("app.api.v1.mcp.async_session_maker", return_value=self.mock_db):
            with patch("app.api.v1.mcp.RedisBroker") as MockBroker:
                mock_inst = AsyncMock()
                mock_inst.enqueue_export_job.return_value = None
                MockBroker.return_value = mock_inst

                # Trigger export
                trigger_res = asyncio.run(trigger_export(self.sample_spec, "gif"))
                trigger_data = json.loads(trigger_res)
                self.assertEqual(trigger_data["status"], "queued")
                job_id = trigger_data["job_id"]

                # Query status
                status_res = asyncio.run(get_export_status(job_id))
                status_data = json.loads(status_res)
                self.assertEqual(status_data["job_id"], job_id)
                self.assertEqual(status_data["status"], "queued")

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
