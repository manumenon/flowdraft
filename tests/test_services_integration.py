import json
import unittest
from datetime import timedelta
from unittest.mock import patch, MagicMock, AsyncMock

from app.services.storage import MinioStorage
from app.services.redis_broker import RedisBroker

class TestMinioStorage(unittest.TestCase):
    @patch("app.services.storage.Minio")
    def test_minio_init_bucket_exists(self, mock_minio_class):
        mock_client = MagicMock()
        mock_minio_class.return_value = mock_client
        mock_client.bucket_exists.return_value = True
        
        storage = MinioStorage()
        
        mock_client.bucket_exists.assert_called_once_with("exports")
        mock_client.make_bucket.assert_not_called()
        self.assertEqual(storage.client, mock_client)

    @patch("app.services.storage.Minio")
    def test_minio_init_bucket_not_exists(self, mock_minio_class):
        mock_client = MagicMock()
        mock_minio_class.return_value = mock_client
        mock_client.bucket_exists.return_value = False
        
        storage = MinioStorage()
        
        mock_client.bucket_exists.assert_called_once_with("exports")
        mock_client.make_bucket.assert_called_once_with("exports")

    @patch("app.services.storage.Minio")
    def test_minio_init_exception(self, mock_minio_class):
        mock_minio_class.side_effect = Exception("Connection failed")
        
        storage = MinioStorage()
        self.assertIsNone(storage.client)

    @patch("app.services.storage.Minio")
    def test_upload_bytes_success(self, mock_minio_class):
        mock_client = MagicMock()
        mock_minio_class.return_value = mock_client
        mock_client.bucket_exists.return_value = True
        
        storage = MinioStorage()
        res = storage.upload_bytes("test.png", b"fake_data", "image/png")
        
        self.assertEqual(res, "test.png")
        mock_client.put_object.assert_called_once()
        args, kwargs = mock_client.put_object.call_args
        self.assertEqual(kwargs["bucket_name"], "exports")
        self.assertEqual(kwargs["object_name"], "test.png")
        self.assertEqual(kwargs["content_type"], "image/png")
        self.assertEqual(kwargs["length"], 9)

    @patch("app.services.storage.Minio")
    def test_upload_bytes_client_not_initialized(self, mock_minio_class):
        mock_minio_class.side_effect = Exception("Init error")
        storage = MinioStorage()
        
        with self.assertRaises(RuntimeError):
            storage.upload_bytes("test.png", b"data")

    @patch("app.services.storage.Minio")
    def test_get_download_url_success(self, mock_minio_class):
        mock_client = MagicMock()
        mock_minio_class.return_value = mock_client
        mock_client.bucket_exists.return_value = True
        mock_client.presigned_get_object.return_value = "http://minio/exports/test.png?token=foo"
        
        storage = MinioStorage()
        url = storage.get_download_url("test.png", expires_seconds=1800)
        
        self.assertEqual(url, "http://minio/exports/test.png?token=foo")
        mock_client.presigned_get_object.assert_called_once()
        args, kwargs = mock_client.presigned_get_object.call_args
        self.assertEqual(kwargs["bucket_name"], "exports")
        self.assertEqual(kwargs["object_name"], "test.png")
        self.assertEqual(kwargs["expires"], timedelta(seconds=1800))

    @patch("app.services.storage.Minio")
    def test_get_download_url_exception_handling(self, mock_minio_class):
        mock_client = MagicMock()
        mock_minio_class.return_value = mock_client
        mock_client.bucket_exists.return_value = True
        mock_client.presigned_get_object.side_effect = Exception("Minio error")
        
        storage = MinioStorage()
        url = storage.get_download_url("test.png")
        self.assertEqual(url, "")


class TestRedisBroker(unittest.IsolatedAsyncioTestCase):
    @patch("app.services.redis_broker.Redis.from_url")
    async def test_enqueue_export_job_success(self, mock_from_url):
        mock_client = MagicMock()
        mock_client.lpush = AsyncMock()
        mock_client.aclose = AsyncMock()
        mock_from_url.return_value = mock_client
        
        broker = RedisBroker(redis_url="redis://localhost:9999/0")
        
        job_id = "test-job-id"
        spec = {"elements": []}
        fmt = "mp4"
        
        await broker.enqueue_export_job(job_id, spec, fmt)
        
        mock_from_url.assert_called_once_with("redis://localhost:9999/0")
        mock_client.lpush.assert_called_once()
        
        args, kwargs = mock_client.lpush.call_args
        self.assertEqual(args[0], "export-jobs")
        payload = json.loads(args[1])
        self.assertEqual(payload["job_id"], job_id)
        self.assertEqual(payload["spec"], spec)
        self.assertEqual(payload["format"], fmt)
        
        mock_client.aclose.assert_called_once()

    @patch("app.services.redis_broker.Redis.from_url")
    async def test_enqueue_export_job_exception(self, mock_from_url):
        mock_client = MagicMock()
        mock_client.lpush = AsyncMock(side_effect=Exception("Redis connection error"))
        mock_client.aclose = AsyncMock()
        mock_from_url.return_value = mock_client
        
        broker = RedisBroker()
        
        with self.assertRaises(Exception):
            await broker.enqueue_export_job("job_id", {}, "gif")
            
        mock_client.aclose.assert_called_once()

    @patch("app.services.redis_broker.Redis.from_url")
    async def test_ping_success(self, mock_from_url):
        mock_client = MagicMock()
        mock_client.ping = AsyncMock(return_value=True)
        mock_client.aclose = AsyncMock()
        mock_from_url.return_value = mock_client
        
        broker = RedisBroker()
        res = await broker.ping()
        
        self.assertTrue(res)
        mock_client.ping.assert_called_once()
        mock_client.aclose.assert_called_once()

    @patch("app.services.redis_broker.Redis.from_url")
    async def test_ping_failure(self, mock_from_url):
        mock_client = MagicMock()
        mock_client.ping = AsyncMock(side_effect=Exception("Timeout"))
        mock_client.aclose = AsyncMock()
        mock_from_url.return_value = mock_client
        
        broker = RedisBroker()
        res = await broker.ping()
        
        self.assertFalse(res)
        mock_client.aclose.assert_called_once()
