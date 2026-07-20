import sys
import os
import time

# Add the project root to sys.path so we can import mock_services
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from tests.e2e.mock_services import ThreadingHTTPServer, MockGatewayHandler, MockMinIOHandler, MockWorkerThread

def start_mock_backend():
    print("Starting mock storage (MinIO) on 127.0.0.1:9000...")
    minio_server = ThreadingHTTPServer(("127.0.0.1", 9000), MockMinIOHandler)
    minio_thread = import_threading().Thread(target=minio_server.serve_forever, daemon=True)
    minio_thread.start()

    print("Starting mock API gateway on 127.0.0.1:8000...")
    # Enable authentications and diagram handling
    gateway_server = ThreadingHTTPServer(("127.0.0.1", 8000), MockGatewayHandler)
    gateway_thread = import_threading().Thread(target=gateway_server.serve_forever, daemon=True)
    gateway_thread.start()

    print("Starting mock render worker daemon...")
    worker = MockWorkerThread()
    worker.start()

    print("\n------------------------------------------------------------")
    print("Mock backend services are running!")
    print("  - API Gateway: http://localhost:8000")
    print("  - MinIO Storage: http://localhost:9000")
    print("Keep this terminal open to interact with the React frontend.")
    print("Press Ctrl+C to terminate.")
    print("------------------------------------------------------------\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping mock backend services...")
        worker.running = False
        worker.join(timeout=1.0)
        gateway_server.shutdown()
        gateway_server.server_close()
        minio_server.shutdown()
        minio_server.server_close()
        print("Mock backend stopped.")

def import_threading():
    import threading
    return threading

if __name__ == "__main__":
    start_mock_backend()
