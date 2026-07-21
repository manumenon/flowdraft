import sys
import os
import unittest
import uuid
import json
from unittest.mock import patch, MagicMock, AsyncMock

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from fastapi.testclient import TestClient

from app.main import app
from app.api.deps import get_db
from app.models import User, Diagram, ExportJob
from app.schemas import UserRegister, DiagramCreate, ExportJobCreate
from scripts.flowdraft.schema import SpecError

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

    def add(self, obj):
        from app.models import utc_now
        now = utc_now()
        
        self.added.append(obj)
        if not hasattr(obj, "created_at") or obj.created_at is None:
            obj.created_at = now
        if not hasattr(obj, "updated_at") or obj.updated_at is None:
            obj.updated_at = now
            
        if isinstance(obj, User):
            if not obj.id:
                obj.id = uuid.uuid4()
            self.users_list.append(obj)
        elif isinstance(obj, Diagram):
            if not obj.id:
                obj.id = uuid.uuid4()
            self.diagrams_list.append(obj)
        elif isinstance(obj, ExportJob):
            if not obj.id:
                obj.id = uuid.uuid4()
            self.export_jobs_list.append(obj)

    async def commit(self):
        pass

    async def refresh(self, obj):
        pass

    async def delete(self, obj):
        self.deleted.append(obj)
        if isinstance(obj, Diagram) and obj in self.diagrams_list:
            self.diagrams_list.remove(obj)
        elif isinstance(obj, ExportJob) and obj in self.export_jobs_list:
            self.export_jobs_list.remove(obj)

    async def close(self):
        pass


class TestBackendAPI(unittest.TestCase):
    def setUp(self):
        self.mock_db = MockAsyncSession()
        app.dependency_overrides[get_db] = lambda: self.mock_db
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()

    def _get_auth_headers(self, email="user@example.com", password="password123"):
        # Create user in mock DB
        from app.core.security import hash_password
        user = User(
            id=uuid.uuid4(),
            email=email,
            hashed_password=hash_password(password),
            is_active=True
        )
        self.mock_db.add(user)

        # Login to get token
        response = self.client.post(
            "/api/v1/auth/token",
            data={"username": email, "password": password}
        )
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}, user

    def test_signup_success(self):
        response = self.client.post(
            "/api/v1/auth/signup",
            json={"email": "new@example.com", "password": "securepassword"}
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["email"], "new@example.com")
        self.assertIn("id", data)
        self.assertTrue(data["is_active"])

    def test_signup_duplicate_email(self):
        # Pre-register user
        self.mock_db.add(User(
            id=uuid.uuid4(),
            email="dup@example.com",
            hashed_password="somehash",
            is_active=True
        ))
        response = self.client.post(
            "/api/v1/auth/signup",
            json={"email": "dup@example.com", "password": "securepassword"}
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Email already registered")

    def test_token_login_success(self):
        headers, user = self._get_auth_headers("login@example.com", "pass123")
        self.assertIn("Authorization", headers)

    def test_token_login_failure(self):
        # Create user
        from app.core.security import hash_password
        self.mock_db.add(User(
            id=uuid.uuid4(),
            email="fail@example.com",
            hashed_password=hash_password("pass123"),
            is_active=True
        ))
        
        # Wrong password
        response = self.client.post(
            "/api/v1/auth/token",
            data={"username": "fail@example.com", "password": "wrongpassword"}
        )
        self.assertEqual(response.status_code, 401)
        
        # Non-existent user
        response = self.client.post(
            "/api/v1/auth/token",
            data={"username": "noexist@example.com", "password": "pass"}
        )
        self.assertEqual(response.status_code, 401)

    def test_diagram_crud_flow(self):
        headers, user = self._get_auth_headers()
        
        # 1. Create Diagram (POST)
        valid_spec = {
            "elements": [
                {"id": "card_1", "type": "card", "title": "Test Title"}
            ]
        }
        response = self.client.post(
            "/api/v1/diagrams/",
            json={"title": "My Diagram", "spec": valid_spec, "theme": "dark"},
            headers=headers
        )
        self.assertEqual(response.status_code, 201)
        diagram_data = response.json()
        self.assertEqual(diagram_data["title"], "My Diagram")
        self.assertEqual(diagram_data["spec"], valid_spec)
        diagram_id = diagram_data["id"]

        # 2. Get All Diagrams (GET /)
        response = self.client.get("/api/v1/diagrams/", headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        self.assertEqual(response.json()[0]["id"], diagram_id)

        # 3. Get Specific Diagram (GET /{id})
        response = self.client.get(f"/api/v1/diagrams/{diagram_id}", headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["title"], "My Diagram")

        # 4. Update Diagram (PUT /{id})
        updated_spec = {
            "elements": [
                {"id": "card_1", "type": "card", "title": "Updated Title"}
            ]
        }
        response = self.client.put(
            f"/api/v1/diagrams/{diagram_id}",
            json={"title": "Updated Diagram Title", "spec": updated_spec},
            headers=headers
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["title"], "Updated Diagram Title")
        self.assertEqual(response.json()["spec"], updated_spec)

        # 5. Delete Diagram (DELETE /{id})
        response = self.client.delete(f"/api/v1/diagrams/{diagram_id}", headers=headers)
        self.assertEqual(response.status_code, 204)
        
        # Verify it is deleted
        response = self.client.get(f"/api/v1/diagrams/{diagram_id}", headers=headers)
        self.assertEqual(response.status_code, 404)

    def test_diagram_spec_validation_failure(self):
        headers, user = self._get_auth_headers()
        
        # Missing 'type' field in elements
        invalid_spec = {
            "canvas": {"width": 800},
            "elements": [
                {"id": "node_1"}
            ]
        }
        response = self.client.post(
            "/api/v1/diagrams/",
            json={"title": "Invalid Spec", "spec": invalid_spec},
            headers=headers
        )
        self.assertEqual(response.status_code, 400)
        # Custom SpecError handler format checks
        res_json = response.json()
        self.assertIn("detail", res_json)
        self.assertIn("path", res_json)
        self.assertEqual(res_json["path"], "elements[0]")

    def test_diagram_authorization(self):
        # Access diagrams without token
        response = self.client.get("/api/v1/diagrams/")
        self.assertEqual(response.status_code, 401)

        # Access diagrams owned by another user
        headers_1, user_1 = self._get_auth_headers("user1@example.com")
        headers_2, user_2 = self._get_auth_headers("user2@example.com")

        # Create diagram as user_1
        diag = Diagram(
            id=uuid.uuid4(),
            title="User 1 Diagram",
            spec={"elements": [{"id": "n1", "type": "card"}]},
            user_id=user_1.id
        )
        self.mock_db.add(diag)

        # Get as user_2
        response = self.client.get(f"/api/v1/diagrams/{diag.id}", headers=headers_2)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"], "Not authorized to access this diagram")

    @patch("app.api.v1.exports.RedisBroker")
    def test_submit_export_job_diagram_id(self, mock_broker_class):
        # Mock broker instance
        mock_broker = MagicMock()
        mock_broker.enqueue_export_job = AsyncMock()
        mock_broker_class.return_value = mock_broker

        headers, user = self._get_auth_headers()

        # Create a diagram in db
        diag = Diagram(
            id=uuid.uuid4(),
            title="Export Spec",
            spec={"elements": [{"id": "n1", "type": "card"}]},
            user_id=user.id
        )
        self.mock_db.add(diag)

        response = self.client.post(
            "/api/v1/export/",
            json={"diagram_id": str(diag.id), "format": "mp4"},
            headers=headers
        )
        self.assertEqual(response.status_code, 200)
        res_json = response.json()
        self.assertIn("job_id", res_json)
        self.assertEqual(res_json["status"], "queued")

        # Verify job is created in db
        self.assertEqual(len(self.mock_db.export_jobs_list), 1)
        job = self.mock_db.export_jobs_list[0]
        self.assertEqual(job.diagram_id, diag.id)
        self.assertEqual(job.format, "mp4")
        self.assertEqual(job.status, "queued")

        # Verify enqueued called
        mock_broker.enqueue_export_job.assert_called_once_with(str(job.id), diag.spec, "mp4")

    @patch("app.api.v1.exports.RedisBroker")
    def test_submit_export_job_spec_override(self, mock_broker_class):
        mock_broker = MagicMock()
        mock_broker.enqueue_export_job = AsyncMock()
        mock_broker_class.return_value = mock_broker

        headers, user = self._get_auth_headers()

        override_spec = {"elements": [{"id": "n2", "type": "card"}]}
        response = self.client.post(
            "/api/v1/export/",
            json={"spec_override": override_spec, "format": "gif"},
            headers=headers
        )
        self.assertEqual(response.status_code, 200)
        res_json = response.json()
        self.assertIn("job_id", res_json)
        self.assertEqual(res_json["status"], "queued")

        # Verify job has spec_override and enqueued correctly
        job = self.mock_db.export_jobs_list[0]
        self.assertEqual(job.spec_override, override_spec)
        self.assertEqual(job.format, "gif")
        mock_broker.enqueue_export_job.assert_called_once_with(str(job.id), override_spec, "gif")

    @patch("app.api.v1.exports.MinioStorage")
    def test_get_export_job_status(self, mock_minio_class):
        mock_minio = MagicMock()
        mock_minio.get_download_url.return_value = "http://minio/exports/job.gif?token=xyz"
        mock_minio_class.return_value = mock_minio

        headers, user = self._get_auth_headers()

        # 1. Test non-completed job status check
        job = ExportJob(
            id=uuid.uuid4(),
            diagram_id=None,
            spec_override={"elements": [{"id": "n1", "type": "card"}]},
            format="gif",
            status="queued",
            user_id=user.id
        )
        self.mock_db.add(job)

        response = self.client.get(f"/api/v1/export/{job.id}", headers=headers)
        self.assertEqual(response.status_code, 200)
        res_json = response.json()
        self.assertEqual(res_json["status"], "queued")
        self.assertIsNone(res_json["download_url"])
        mock_minio.get_download_url.assert_not_called()

        # 2. Test completed job status check (populates download_url)
        job.status = "completed"
        response = self.client.get(f"/api/v1/export/{job.id}", headers=headers)
        self.assertEqual(response.status_code, 200)
        res_json = response.json()
        self.assertEqual(res_json["status"], "completed")
        self.assertEqual(res_json["download_url"], f"/api/v1/export/{job.id}/download")
