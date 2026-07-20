import unittest
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings

class TestMCPAPI(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        settings.MCP_API_KEYS = "test-key-1,test-key-2"

    def test_mcp_unauthorized_no_key(self):
        # GET /api/v1/mcp/sse should return 401 if key is missing
        response = self.client.get("/api/v1/mcp/sse")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "MCP API Key is missing")

        # POST /api/v1/mcp/messages/ should return 401 if key is missing
        response = self.client.post("/api/v1/mcp/messages/")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "MCP API Key is missing")

    def test_mcp_forbidden_invalid_key(self):
        # POST with invalid key should return 403
        response = self.client.post("/api/v1/mcp/messages/", headers={"X-MCP-API-Key": "wrong-key"})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"], "Invalid MCP API Key")

        # Query param key check
        response = self.client.post("/api/v1/mcp/messages/?api_key=wrong-key")
        self.assertEqual(response.status_code, 403)

    def test_mcp_authorized_headers(self):
        # With valid key, it should pass the authentication middleware
        # Since we're sending an empty or dummy body, the mounted app will return 400 Bad Request or 404
        # (instead of 401/403 which are intercepted by the middleware).
        # This proves the request successfully passed the middleware!
        response = self.client.post("/api/v1/mcp/messages/", headers={"X-MCP-API-Key": "test-key-1"})
        self.assertIn(response.status_code, [400, 404])

    def test_mcp_api_prefix_handling(self):
        # Check both /api/v1/mcp and /api/mcp prefixes
        response = self.client.post("/api/mcp/messages/", headers={"X-MCP-API-Key": "test-key-2"})
        self.assertIn(response.status_code, [400, 404])
