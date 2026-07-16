import asyncio
import json
import unittest
import uuid
from unittest.mock import patch, MagicMock, AsyncMock
import httpx
from fastapi.testclient import TestClient

from app.main import app
from app.api.deps import get_db
from app.models import User, Diagram, ExportJob
from app.services.redis_broker import RedisBroker
from app.services.storage import MinioStorage

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


class ConcurrentMockAsyncSession:
    # Class-level variables to share mock database rows across different session instances
    users_list = []
    diagrams_list = []
    export_jobs_list = []

    @classmethod
    def clear_db(cls):
        cls.users_list.clear()
        cls.diagrams_list.clear()
        cls.export_jobs_list.clear()

    def __init__(self):
        self.added = []
        self.deleted = []

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


class TestChallengerResilience(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        ConcurrentMockAsyncSession.clear_db()
        app.dependency_overrides.clear()
        
        # Pre-seed user for auth
        from app.core.security import hash_password
        self.test_user = User(
            id=uuid.uuid4(),
            email="challenger@example.com",
            hashed_password=hash_password("password123"),
            is_active=True
        )
        
        # Use a temporary session instance to seed the mock database
        seed_session = ConcurrentMockAsyncSession()
        seed_session.add(self.test_user)
        
        self.test_diagram = Diagram(
            id=uuid.uuid4(),
            title="Challenger Diagram",
            spec={"elements": [{"id": "n1", "type": "card"}]},
            user_id=self.test_user.id
        )
        seed_session.add(self.test_diagram)

        # Login once to get credentials using standard TestClient with temporary dependency override
        app.dependency_overrides[get_db] = lambda: ConcurrentMockAsyncSession()
        client = TestClient(app)
        response = client.post(
            "/api/v1/auth/token",
            data={"username": "challenger@example.com", "password": "password123"}
        )
        app.dependency_overrides.clear()
        
        self.token = response.json()["access_token"]
        self.auth_headers = {"Authorization": f"Bearer {self.token}"}

    def tearDown(self):
        app.dependency_overrides.clear()

    async def test_get_db_yields_unique_sessions_concurrently(self):
        """Verify that the real get_db yields separate session instances concurrently."""
        from app.core.database import get_db
        sessions = []
        
        async def fetch_session():
            async for session in get_db():
                sessions.append(session)
                
        # Invoke get_db 3 times concurrently
        await asyncio.gather(fetch_session(), fetch_session(), fetch_session())
        
        self.assertEqual(len(sessions), 3)
        self.assertEqual(len(set(sessions)), 3)

    async def test_concurrent_diagram_creations_do_not_share_sessions(self):
        """Simulate concurrent requests creating diagrams and verify distinct database session instances."""
        session_instances = []

        async def get_concurrent_db():
            sess = ConcurrentMockAsyncSession()
            session_instances.append(sess)
            yield sess

        app.dependency_overrides[get_db] = get_concurrent_db

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
            tasks = []
            for i in range(10):
                payload = {
                    "title": f"Diagram {i}",
                    "spec": {"elements": [{"id": f"n{i}", "type": "card"}]}
                }
                tasks.append(ac.post("/api/v1/diagrams", json=payload, headers=self.auth_headers))
            
            responses = await asyncio.gather(*tasks)

        # Verify all diagram creation requests returned 201 Created
        for res in responses:
            self.assertEqual(res.status_code, 201)

        # Verify 10 separate session objects were instantiated and yielded
        self.assertEqual(len(session_instances), 10)
        self.assertEqual(len(set(session_instances)), 10)

    @patch("app.api.v1.exports.RedisBroker")
    async def test_concurrent_exports_do_not_share_sessions(self, mock_broker_class):
        """Simulate concurrent requests submitting exports and verify distinct database session instances."""
        mock_broker = MagicMock()
        mock_broker.enqueue_export_job = AsyncMock()
        mock_broker_class.return_value = mock_broker

        session_instances = []

        async def get_concurrent_db():
            sess = ConcurrentMockAsyncSession()
            session_instances.append(sess)
            yield sess

        app.dependency_overrides[get_db] = get_concurrent_db

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
            tasks = []
            for i in range(10):
                payload = {
                    "diagram_id": str(self.test_diagram.id),
                    "format": "mp4"
                }
                tasks.append(ac.post("/api/v1/export", json=payload, headers=self.auth_headers))
            
            responses = await asyncio.gather(*tasks)

        # Verify all export submission requests returned 200 OK
        for res in responses:
            self.assertEqual(res.status_code, 200)

        # Verify 10 separate session objects were instantiated and yielded
        self.assertEqual(len(session_instances), 10)
        self.assertEqual(len(set(session_instances)), 10)

    @patch("app.api.v1.exports.RedisBroker")
    def test_redis_failure_during_export_returns_500_and_updates_db(self, mock_broker_class):
        """Verify that when Redis is down, POST /export returns 500 cleanly and updates DB status to failed."""
        mock_broker = MagicMock()
        mock_broker.enqueue_export_job = AsyncMock(side_effect=Exception("Redis connection refused"))
        mock_broker_class.return_value = mock_broker

        session = ConcurrentMockAsyncSession()
        app.dependency_overrides[get_db] = lambda: session

        client = TestClient(app)
        payload = {
            "diagram_id": str(self.test_diagram.id),
            "format": "mp4"
        }
        
        response = client.post("/api/v1/export/", json=payload, headers=self.auth_headers)
        
        # Verify 500 error returned
        self.assertEqual(response.status_code, 500)
        self.assertIn("Failed to submit export job", response.json()["detail"])
        
        # Verify the job status is set to failed and error message populated in database
        self.assertEqual(len(session.export_jobs_list), 1)
        job = session.export_jobs_list[0]
        self.assertEqual(job.status, "failed")
        self.assertIn("Redis connection refused", job.error_message)

    @patch("app.services.storage.Minio")
    def test_minio_init_failure_during_status_returns_200_with_empty_url(self, mock_minio_class):
        """Verify that when MinIO is down during initialization, GET /export/{id} returns 200 and empty download_url."""
        # Force MinIO client initialization to fail
        mock_minio_class.side_effect = Exception("Minio connection timeout")
        
        session = ConcurrentMockAsyncSession()
        job = ExportJob(
            id=uuid.uuid4(),
            diagram_id=self.test_diagram.id,
            format="mp4",
            status="completed",
            user_id=self.test_user.id
        )
        session.add(job)
        app.dependency_overrides[get_db] = lambda: session
        
        client = TestClient(app)
        response = client.get(f"/api/v1/export/{job.id}", headers=self.auth_headers)
        
        # Verify response is 200 and has empty download url
        self.assertEqual(response.status_code, 200)
        res_json = response.json()
        self.assertEqual(res_json["status"], "completed")
        self.assertEqual(res_json["download_url"], "")

    @patch("app.services.storage.Minio")
    def test_minio_presigned_url_failure_returns_200_with_empty_url(self, mock_minio_class):
        """Verify that when MinIO presigned URL generation throws an exception, GET /export/{id} degrades gracefully."""
        mock_client = MagicMock()
        mock_minio_class.return_value = mock_client
        mock_client.bucket_exists.return_value = True
        # Force presigned_get_object to raise exception
        mock_client.presigned_get_object.side_effect = Exception("S3 bucket not accessible")
        
        session = ConcurrentMockAsyncSession()
        job = ExportJob(
            id=uuid.uuid4(),
            diagram_id=self.test_diagram.id,
            format="mp4",
            status="completed",
            user_id=self.test_user.id
        )
        session.add(job)
        app.dependency_overrides[get_db] = lambda: session
        
        client = TestClient(app)
        response = client.get(f"/api/v1/export/{job.id}", headers=self.auth_headers)
        
        # Verify response is 200 and has empty download url
        self.assertEqual(response.status_code, 200)
        res_json = response.json()
        self.assertEqual(res_json["status"], "completed")
        self.assertEqual(res_json["download_url"], "")
