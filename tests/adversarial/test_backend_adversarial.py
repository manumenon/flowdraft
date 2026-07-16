import unittest
import uuid
import json
import jwt
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import DataError

from app.main import app
from app.api.deps import get_db
from app.models import User, Diagram, ExportJob

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

        # Simulate Postgres UUID type validation failure in queries
        # if diagram_id is a non-UUID string.
        # e.g., select(Diagram).where(Diagram.id == diagram_id)
        if model == Diagram:
            for k, v in params.items():
                if "id" in k and "user_id" not in k:
                    # check if the value is a valid UUID or uuid.UUID
                    if v is not None and not isinstance(v, uuid.UUID):
                        try:
                            uuid.UUID(str(v))
                        except ValueError:
                            raise DataError("select ...", {}, Exception("invalid input syntax for type uuid"))

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


class TestBackendAdversarial(unittest.TestCase):
    def setUp(self):
        self.mock_db = MockAsyncSession()
        app.dependency_overrides[get_db] = lambda: self.mock_db
        self.client = TestClient(app, raise_server_exceptions=False)

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_deactivated_user_auth_bypass(self):
        """
        Adversarial Test 1: Verify that deactivated users (is_active=False)
        are blocked from accessing authenticated routes.
        """
        # Create a deactivated user in mock DB
        deactivated_user = User(
            id=uuid.uuid4(),
            email="deactivated@example.com",
            hashed_password="mock-hashed-password",
            is_active=False
        )
        self.mock_db.users_list.append(deactivated_user)

        # Generate a valid token
        from app.core.security import create_access_token
        token = create_access_token(data={"sub": deactivated_user.email, "user_id": str(deactivated_user.id)})
        headers = {"Authorization": f"Bearer {token}"}

        response = self.client.get("/api/v1/diagrams/", headers=headers)
        # We assert that the request is rejected with 401 Unauthorized or 403 Forbidden
        self.assertIn(response.status_code, [401, 403], 
            msg="Deactivated user was allowed to access protected endpoints (auth bypass)!")

    def test_default_user_check_unauthenticated_request(self):
        """
        Adversarial Test 2: Verify that unauthenticated requests do not execute
        unnecessary database queries (like checking/creating the default user)
        before validating the credentials/token.
        """
        spy_execute = MagicMock(side_effect=self.mock_db.execute)
        self.mock_db.execute = spy_execute

        # Send request without token
        response = self.client.get("/api/v1/diagrams/")
        
        # Verify it is rejected
        self.assertEqual(response.status_code, 401)
        
        # Verify that no DB queries were executed for default user
        # In a hardened API gateway, early rejection should happen before any DB queries.
        spy_execute.assert_not_called()

    def test_default_jwt_secret_rejected(self):
        """
        Adversarial Test 3: Verify that the API gateway rejects tokens signed
        with the default/weak JWT secret to prevent token forgery.
        """
        # Create a user in mock DB
        user = User(
            id=uuid.uuid4(),
            email="admin@example.com",
            hashed_password="mock-hashed-password",
            is_active=True
        )
        self.mock_db.users_list.append(user)

        # Generate token using the default JWT secret
        token = jwt.encode(
            {"sub": user.email, "user_id": str(user.id)},
            "super-secret-key-change-in-prod-must-be-at-least-32-bytes",
            algorithm="HS256"
        )
        headers = {"Authorization": f"Bearer {token}"}

        # Request protected resource
        response = self.client.get("/api/v1/diagrams/", headers=headers)
        
        # Assert that the API gateway rejects the token signed with the default key
        self.assertEqual(response.status_code, 401, 
            msg="API Gateway accepted a JWT token signed with the default/weak secret key!")

    def test_export_malformed_diagram_id_handling(self):
        """
        Adversarial Test 4: Verify that passing a malformed non-UUID diagram_id
        to the export endpoint is handled cleanly with 400/422, rather than
        causing a database exception and returning a 500 error.
        """
        # Pre-seed a user so we can authenticate
        user = User(
            id=uuid.uuid4(),
            email="exporter@example.com",
            hashed_password="mock-hashed-password",
            is_active=True
        )
        self.mock_db.users_list.append(user)

        # Generate a valid token
        from app.core.security import create_access_token
        token = create_access_token(data={"sub": user.email, "user_id": str(user.id)})
        headers = {"Authorization": f"Bearer {token}"}

        # Send request with malformed diagram_id (not a valid UUID string)
        malformed_payload = {
            "diagram_id": "malformed-non-uuid-string-'; DROP TABLE diagrams;--",
            "format": "mp4"
        }
        
        response = self.client.post("/api/v1/export/", json=malformed_payload, headers=headers)
        
        # We assert that the response is 400 Bad Request or 422 Unprocessable Entity
        self.assertIn(response.status_code, [400, 422],
            msg=f"API returned {response.status_code} instead of 400/422 for malformed diagram_id.")

    @patch("app.services.redis_broker.RedisBroker.ping")
    def test_health_check_database_offline(self, mock_redis_ping):
        """
        Adversarial Test 5: Verify that the health check endpoint returns an unhealthy
        status (500) if the database is offline/unreachable, rather than solely
        checking Redis.
        """
        mock_redis_ping.return_value = True

        # Sabotage the database session dependency to raise an exception
        async def mock_get_db_offline():
            raise Exception("Database connection refused")
            yield  # To make it a generator
            
        app.dependency_overrides[get_db] = mock_get_db_offline
        
        try:
            response = self.client.get("/health")
            # If the database is offline, health check must return 500 Internal Server Error
            self.assertEqual(response.status_code, 500, 
                msg="Health check returned 200 OK even though the database is offline!")
            res_json = response.json()
            self.assertEqual(res_json["status"], "unhealthy")
            self.assertIn("database", res_json)
        finally:
            # Restore dependency overrides
            app.dependency_overrides[get_db] = lambda: self.mock_db
