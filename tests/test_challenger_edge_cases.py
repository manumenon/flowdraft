import unittest
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
import jwt

from app.main import app
from app.api.deps import get_db
from app.models import User, Diagram, ExportJob
from app.schemas import UserRegister, DiagramCreate, ExportJobCreate
from app.core.config import settings
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
            # Extract email or username
            email_val = None
            for k, v in params.items():
                if "email" in k or "username" in k:
                    email_val = v
                    break
            if email_val is None:
                for k, v in params.items():
                    if isinstance(v, str):
                        email_val = v
                        break
            if email_val is not None:
                matches = [u for u in self.users_list if u.email == email_val]
                return MockResult(matches)
            return MockResult([])

        elif model == Diagram:
            user_id_val = None
            for k, v in params.items():
                if "user_id" in k:
                    user_id_val = v
                    break
            
            diagram_id_val = None
            for k, v in params.items():
                if "id" in k and "user_id" not in k:
                    diagram_id_val = v
                    break

            if diagram_id_val is not None:
                matches = [d for d in self.diagrams_list if str(d.id) == str(diagram_id_val)]
                return MockResult(matches)
            
            if user_id_val is not None:
                matches = [d for d in self.diagrams_list if str(d.user_id) == str(user_id_val)]
                return MockResult(matches)

            return MockResult(self.diagrams_list)

        elif model == ExportJob:
            job_id_val = None
            for k, v in params.items():
                if "id" in k:
                    job_id_val = v
                    break
            if job_id_val is not None:
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


class TestChallengerEdgeCases(unittest.TestCase):
    def setUp(self):
        self.mock_db = MockAsyncSession()
        app.dependency_overrides[get_db] = lambda: self.mock_db
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()

    def _get_auth_headers(self, email="user@example.com", password="password123", expires_delta=None):
        # Create user in mock DB
        from app.core.security import hash_password, create_access_token
        user = User(
            id=uuid.uuid4(),
            email=email,
            hashed_password=hash_password(password),
            is_active=True
        )
        self.mock_db.add(user)

        # Build token directly to support expiry test
        token_data = {"sub": user.email, "user_id": str(user.id)}
        if expires_delta is not None:
            token = create_access_token(data=token_data, expires_delta=expires_delta)
        else:
            token = create_access_token(data=token_data)
        
        return {"Authorization": f"Bearer {token}"}, user

    # ==========================================================================
    # 1. Invalid Diagram Schemas (Edge Cases & Validation Messages)
    # ==========================================================================

    def test_schema_empty_elements(self):
        """Test diagram creation with empty elements list. Returns 400."""
        headers, user = self._get_auth_headers()
        invalid_spec = {
            "canvas": {"width": 1200, "height": 900},
            "elements": []
        }
        response = self.client.post(
            "/api/v1/diagrams/",
            json={"title": "Empty Elements", "spec": invalid_spec},
            headers=headers
        )
        self.assertEqual(response.status_code, 400)
        res_json = response.json()
        self.assertIn("detail", res_json)
        self.assertEqual(res_json["path"], "elements")
        self.assertIn("at least one element", res_json["detail"])

    def test_schema_missing_elements(self):
        """Test diagram creation with missing elements field. Returns 400."""
        headers, user = self._get_auth_headers()
        invalid_spec = {
            "canvas": {"width": 1200, "height": 900}
        }
        response = self.client.post(
            "/api/v1/diagrams/",
            json={"title": "Missing Elements", "spec": invalid_spec},
            headers=headers
        )
        self.assertEqual(response.status_code, 400)
        res_json = response.json()
        self.assertIn("detail", res_json)
        self.assertEqual(res_json["path"], "<root>")
        self.assertIn("Missing required field 'elements'", res_json["detail"])

    def test_schema_element_missing_required_fields(self):
        """Test diagram element missing 'type' or 'id'. Returns 400."""
        headers, user = self._get_auth_headers()
        # Element missing 'type'
        invalid_spec_1 = {
            "elements": [
                {"id": "node_1"}
            ]
        }
        response = self.client.post(
            "/api/v1/diagrams/",
            json={"title": "Missing Type", "spec": invalid_spec_1},
            headers=headers
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["path"], "elements[0]")
        self.assertIn("Missing required field 'type'", response.json()["detail"])

        # Element missing 'id'
        invalid_spec_2 = {
            "elements": [
                {"type": "card"}
            ]
        }
        response = self.client.post(
            "/api/v1/diagrams/",
            json={"title": "Missing ID", "spec": invalid_spec_2},
            headers=headers
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["path"], "elements[0]")
        self.assertIn("Missing required field 'id'", response.json()["detail"])

    def test_schema_element_empty_id(self):
        """Test diagram element with empty or whitespace-only id. Returns 400."""
        headers, user = self._get_auth_headers()
        invalid_spec = {
            "elements": [
                {"id": "   ", "type": "card"}
            ]
        }
        response = self.client.post(
            "/api/v1/diagrams/",
            json={"title": "Empty ID", "spec": invalid_spec},
            headers=headers
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["path"], "elements[0].id")
        self.assertIn("must not be empty", response.json()["detail"])

    def test_schema_invalid_element_type(self):
        """Test diagram element with unsupported type. Returns 400."""
        headers, user = self._get_auth_headers()
        invalid_spec = {
            "elements": [
                {"id": "node_1", "type": "unsupported_type"}
            ]
        }
        response = self.client.post(
            "/api/v1/diagrams/",
            json={"title": "Bad Type", "spec": invalid_spec},
            headers=headers
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["path"], "elements[0].type")
        self.assertIn("must be one of", response.json()["detail"])

    def test_schema_invalid_elements_type_format(self):
        """Test elements is not a list (e.g. dictionary). Returns 400."""
        headers, user = self._get_auth_headers()
        invalid_spec = {
            "elements": {"id": "node_1", "type": "card"}
        }
        response = self.client.post(
            "/api/v1/diagrams/",
            json={"title": "Elements Dict", "spec": invalid_spec},
            headers=headers
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["path"], "elements")
        self.assertIn("must be list", response.json()["detail"])

    def test_schema_invalid_canvas_dimensions(self):
        """Test canvas width/height is negative or zero. Returns 400."""
        headers, user = self._get_auth_headers()
        invalid_spec = {
            "canvas": {"width": -100, "height": 800},
            "elements": [{"id": "node_1", "type": "card"}]
        }
        response = self.client.post(
            "/api/v1/diagrams/",
            json={"title": "Negative Width", "spec": invalid_spec},
            headers=headers
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["path"], "canvas.width")
        self.assertIn("must be a positive number", response.json()["detail"])

    def test_schema_extremely_long_text_and_emojis(self):
        """Test valid diagram spec containing extremely long title text and emojis/special characters. Returns 201."""
        headers, user = self._get_auth_headers()
        long_title = "A" * 10000 + " 🔥 🚀 🌟 💻 中国 ⚙️"
        valid_spec = {
            "canvas": {"width": 1920, "height": 1080},
            "elements": [
                {
                    "id": "node_1", 
                    "type": "card",
                    "title": long_title,
                    "body": "Special characters and emoji test: 🎉 👻 🚀 🤖"
                }
            ]
        }
        response = self.client.post(
            "/api/v1/diagrams/",
            json={"title": "Emoji Test", "spec": valid_spec},
            headers=headers
        )
        self.assertEqual(response.status_code, 201)
        res_json = response.json()
        self.assertEqual(res_json["spec"]["elements"][0]["title"], long_title)
        self.assertEqual(res_json["spec"]["elements"][0]["body"], "Special characters and emoji test: 🎉 👻 🚀 🤖")

    # ==========================================================================
    # 2. Auth Boundaries (Invalid Tokens, Expired Tokens, SQL Injection Patterns)
    # ==========================================================================

    def test_auth_invalid_token(self):
        """Test API request with an invalid/malformed token. Returns 401."""
        response = self.client.get(
            "/api/v1/diagrams/",
            headers={"Authorization": "Bearer invalid_token_value_here"}
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "Could not validate credentials")

    def test_auth_expired_token(self):
        """Test API request with an expired JWT token. Returns 401."""
        # Generate token with negative expiry
        headers, user = self._get_auth_headers(expires_delta=timedelta(minutes=-5))
        response = self.client.get(
            "/api/v1/diagrams/",
            headers=headers
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "Could not validate credentials")

    def test_auth_sql_injection_signup_and_login(self):
        """Test signup and login resilience against SQL injection patterns. Handles cleanly."""
        sql_payloads = [
            "' OR '1'='1",
            "'; DROP TABLE users; --",
            "admin' --",
            "' UNION SELECT email, hashed_password FROM users --"
        ]

        for payload in sql_payloads:
            # 1. Test signup with injection payload in email.
            # It should succeed (return 201) because SQLAlchemy uses parameterized queries and handles it as a literal string.
            response = self.client.post(
                "/api/v1/auth/signup",
                json={"email": payload, "password": "securepassword123"}
            )
            self.assertEqual(response.status_code, 201)
            self.assertEqual(response.json()["email"], payload)

            # 2. Test login with registered injection email. Should succeed (return 200).
            response_login = self.client.post(
                "/api/v1/auth/token",
                data={"username": payload, "password": "securepassword123"}
            )
            self.assertEqual(response_login.status_code, 200)
            self.assertIn("access_token", response_login.json())

            # 3. Test login with unregistered injection payload. Should fail cleanly (return 401).
            response_fail = self.client.post(
                "/api/v1/auth/token",
                data={"username": payload + "_unregistered", "password": "wrongpassword"}
            )
            self.assertEqual(response_fail.status_code, 401)
            self.assertEqual(response_fail.json()["detail"], "Incorrect email or password")

    def test_auth_missing_token(self):
        """Test request to protected resource without Authorization header. Returns 401."""
        response = self.client.get("/api/v1/diagrams/")
        self.assertEqual(response.status_code, 401)

    def test_auth_wrong_user_forbidden(self):
        """Test accessing another user's diagram. Returns 403."""
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

        # Retrieve as user_2 -> forbidden
        response = self.client.get(f"/api/v1/diagrams/{diag.id}", headers=headers_2)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"], "Not authorized to access this diagram")

    # ==========================================================================
    # 3. Resource ID and Format Boundaries
    # ==========================================================================

    def test_nonexistent_diagram_id(self):
        """Test retrieving, updating, deleting non-existent diagram UUIDs. Returns 404."""
        headers, user = self._get_auth_headers()
        non_existent_uuid = uuid.uuid4()

        # GET non-existent diagram
        response = self.client.get(f"/api/v1/diagrams/{non_existent_uuid}", headers=headers)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Diagram not found")

        # PUT non-existent diagram
        response = self.client.put(
            f"/api/v1/diagrams/{non_existent_uuid}",
            json={"title": "Updated Title"},
            headers=headers
        )
        self.assertEqual(response.status_code, 404)

        # DELETE non-existent diagram
        response = self.client.delete(f"/api/v1/diagrams/{non_existent_uuid}", headers=headers)
        self.assertEqual(response.status_code, 404)

    def test_nonexistent_job_id(self):
        """Test retrieving non-existent export job UUIDs. Returns 404."""
        headers, user = self._get_auth_headers()
        non_existent_uuid = uuid.uuid4()

        response = self.client.get(f"/api/v1/export/{non_existent_uuid}", headers=headers)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Export job not found")

    def test_invalid_uuid_format_path_param(self):
        """Test passing a malformed UUID as a path parameter. Returns 422."""
        headers, user = self._get_auth_headers()
        bad_format_id = "not-a-valid-uuid-12345"

        response = self.client.get(f"/api/v1/diagrams/{bad_format_id}", headers=headers)
        self.assertEqual(response.status_code, 422)
        # Validation details in response
        self.assertIn("detail", response.json())

    def test_invalid_export_format(self):
        """Test submitting an export job with an unsupported format. Returns 400."""
        headers, user = self._get_auth_headers()

        response = self.client.post(
            "/api/v1/export/",
            json={"spec_override": {"elements": [{"id": "n1", "type": "card"}]}, "format": "avi"},
            headers=headers
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Unsupported format", response.json()["detail"])

    def test_export_missing_spec_and_id(self):
        """Test submitting export job with neither diagram_id nor spec_override. Returns 400."""
        headers, user = self._get_auth_headers()

        response = self.client.post(
            "/api/v1/export/",
            json={"format": "mp4"},
            headers=headers
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Must provide either diagram_id or spec_override", response.json()["detail"])
