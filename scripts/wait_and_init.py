import asyncio
import socket
import time
import sys
import os
from urllib.parse import urlparse

# Configure Python path compatibility dynamically to resolve imports
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = None
while current_dir and current_dir != os.path.dirname(current_dir):
    if os.path.exists(os.path.join(current_dir, "scripts")):
        project_root = current_dir
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        break
    current_dir = os.path.dirname(current_dir)

from app.core.config import settings
from app.core.database import engine, Base
from app.models import User, Diagram, ExportJob
from app.services.storage import MinioStorage

def wait_for_port(url_str: str, service_name: str, timeout: int = 60):
    """Wait until a service port is open."""
    if "://" in url_str:
        parsed = urlparse(url_str)
        host = parsed.hostname
        port = parsed.port
        if not port:
            if parsed.scheme == "postgresql":
                port = 5432
            elif parsed.scheme == "redis":
                port = 6379
    else:
        parts = url_str.split(":")
        host = parts[0]
        port = int(parts[1]) if len(parts) > 1 else 9000

    print(f"Waiting for {service_name} at {host}:{port}...", flush=True)
    start_time = time.time()
    while True:
        try:
            with socket.create_connection((host, port), timeout=2):
                print(f"{service_name} is ready.", flush=True)
                return True
        except (socket.timeout, ConnectionRefusedError, OSError):
            if time.time() - start_time > timeout:
                print(f"Timeout waiting for {service_name} at {host}:{port}", flush=True)
                return False
            time.sleep(2)

async def init_db():
    print("Running DB migrations/schema creation...", flush=True)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("DB schema created successfully.", flush=True)
    except Exception as e:
        print(f"Failed to create DB schema: {e}", flush=True)
        raise e

def init_minio():
    print("Verifying MinIO exports bucket...", flush=True)
    try:
        storage = MinioStorage()
        if storage.client and storage.client.bucket_exists("exports"):
            print("MinIO 'exports' bucket is ready.", flush=True)
        else:
            print("MinIO exports bucket could not be verified.", flush=True)
    except Exception as e:
        print(f"Failed to initialize MinIO: {e}", flush=True)
        raise e

async def main():
    print("Starting services initialization...", flush=True)
    db_ok = wait_for_port(settings.DATABASE_URL, "PostgreSQL")
    minio_ok = wait_for_port(settings.MINIO_ENDPOINT, "MinIO")
    
    if db_ok:
        await init_db()
    else:
        print("Skipping DB init due to connection failure.", flush=True)
        sys.exit(1)
        
    if minio_ok:
        init_minio()
    else:
        print("Skipping MinIO init due to connection failure.", flush=True)
        sys.exit(1)
    
    print("Initialization completed successfully.", flush=True)

if __name__ == "__main__":
    asyncio.run(main())
