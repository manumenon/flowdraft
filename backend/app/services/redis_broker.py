import json
import logging
from redis.asyncio import Redis
from app.core.config import settings

logger = logging.getLogger(__name__)

class RedisBroker:
    """
    Async Redis broker using the `redis.asyncio` library.
    Manages enqueueing and checking export jobs.
    """
    def __init__(self, redis_url: str = settings.REDIS_URL) -> None:
        self.redis_url = redis_url

    async def enqueue_export_job(self, job_id: str, spec: dict, format: str) -> None:
        """
        Connects to Redis using `redis_url` and enqueues the job payload
        into a Redis list named 'export-jobs' using LPUSH.
        """
        payload = {
            "job_id": job_id,
            "spec": spec,
            "format": format
        }
        client = None
        try:
            client = Redis.from_url(self.redis_url)
            # LPUSH the JSON-serialized payload to 'export-jobs'
            await client.lpush("export-jobs", json.dumps(payload))
        except Exception as e:
            logger.error(f"Failed to enqueue export job '{job_id}' in Redis: {e}")
            raise e
        finally:
            if client is not None:
                await client.aclose()

    async def ping(self) -> bool:
        """
        Pings Redis to check connectivity.
        Returns True if successful, False otherwise.
        """
        client = None
        try:
            client = Redis.from_url(self.redis_url)
            return await client.ping()
        except Exception as e:
            logger.error(f"Redis ping failed: {e}")
            return False
        finally:
            if client is not None:
                await client.aclose()
