import io
import logging
from datetime import timedelta
from minio import Minio
from app.core.config import settings

logger = logging.getLogger(__name__)

class MinioStorage:
    """
    MinioStorage client wrapper using the `minio` library.
    Synchronously interfaces with MinIO to manage file exports.
    """
    def __init__(self) -> None:
        self.bucket_name = "exports"
        try:
            self.client = Minio(
                endpoint=settings.MINIO_ENDPOINT,
                access_key=settings.MINIO_ACCESS_KEY,
                secret_key=settings.MINIO_SECRET_KEY,
                secure=False
            )
            # Check if bucket exports exists, and if not, create it.
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
        except Exception as e:
            logger.error(f"Failed to initialize MinIO client or bucket '{self.bucket_name}': {e}")
            self.client = None

    def upload_bytes(self, file_name: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        """
        Upload bytes directly to the 'exports' bucket.
        Returns the uploaded file_name (object name) on success.
        """
        if self.client is None:
            err_msg = "MinIO client is not initialized"
            logger.error(err_msg)
            raise RuntimeError(err_msg)
        
        try:
            data_stream = io.BytesIO(data)
            self.client.put_object(
                bucket_name=self.bucket_name,
                object_name=file_name,
                data=data_stream,
                length=len(data),
                content_type=content_type
            )
            return file_name
        except Exception as e:
            logger.error(f"Failed to upload bytes for file '{file_name}': {e}")
            raise e

    def get_download_url(self, file_name: str, expires_seconds: int = 3600) -> str:
        """
        Returns a pre-signed GET URL for retrieving the file.
        If MinIO fails or throws an exception, handles it gracefully, logs, and returns an empty string.
        """
        if self.client is None:
            logger.error("MinIO client is not initialized, cannot generate download URL")
            return ""
        
        try:
            url = self.client.presigned_get_object(
                bucket_name=self.bucket_name,
                object_name=file_name,
                expires=timedelta(seconds=expires_seconds)
            )
            return url
        except Exception as e:
            logger.error(f"Failed to get presigned GET URL for file '{file_name}': {e}")
            return ""

    def get_object(self, file_name: str):
        """
        Retrieves the object data stream from the exports bucket.
        """
        if self.client is None:
            raise RuntimeError("MinIO client is not initialized")
        try:
            response = self.client.get_object(
                bucket_name=self.bucket_name,
                object_name=file_name
            )
            return response
        except Exception as e:
            logger.error(f"Failed to get object '{file_name}': {e}")
            raise e
