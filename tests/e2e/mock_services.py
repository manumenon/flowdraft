import http.server
import socketserver
import threading
import json
import uuid
import urllib.request
import time
import os
from urllib.parse import urlparse, parse_qs

class ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True

class MockFrontendHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass # Suppress log output to keep console clean
    
    def do_GET(self):
        parsed_url = urlparse(self.path)
        params = parse_qs(parsed_url.query)
        
        if parsed_url.path.startswith("/render-box"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            
            # Extract test parameters
            fail_worker = params.get("fail_worker", ["false"])[0] == "true"
            text_length = params.get("text_length", [""])[0]
            spec_param = params.get("spec", [""])[0]
            
            fallback_html = ""
            if fail_worker:
                fallback_html = '<div id="fallback-grid">Fallback Grid Layout Active</div>'
            
            cjk_html = ""
            if spec_param == "cjk_long" or "데이터" in spec_param or "성능" in spec_param or "cjk" in spec_param:
                cjk_html = '<div id="cjk-overflow-marker" class="cjk-wrap">CJK Wrapping Active</div>'
                
            text_length_html = ""
            if text_length:
                text_length_html = f'<div id="text-length-offset" data-offset="120" data-length="{text_length}"></div>'
                
            html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Mock Render Box</title>
                <style>
                    .cjk-wrap {{ word-break: break-all; }}
                </style>
            </head>
            <body>
              <div id="canvas" style="width: 100%; height: 100%;">
                <svg id="elk-layout" width="1000" height="1000">
                  <rect id="mock-node" x="10" y="10" width="100" height="50" fill="cyan"></rect>
                </svg>
                {fallback_html}
                {cjk_html}
                {text_length_html}
              </div>
              <script>
                window.gsap = {{
                  ticker: {{ fps: () => 60 }},
                  globalTimeline: {{
                    progressValue: 0.0,
                    timeValue: 0.0,
                    pausedValue: false,
                    progress: function(val) {{
                      if (val !== undefined) {{ this.progressValue = val; }}
                      return this.progressValue;
                    }},
                    time: function(val) {{
                      if (val !== undefined) {{ this.timeValue = val; }}
                      return this.timeValue;
                    }},
                    pause: function() {{
                      this.pausedValue = true;
                    }}
                  }}
                }};
                window.step = function(ms) {{
                  const duration = 5000.0; // 5 seconds
                  const deltaProgress = ms / duration;
                  const newProgress = Math.min(1.0, window.gsap.globalTimeline.progress() + deltaProgress);
                  window.gsap.globalTimeline.progress(newProgress);
                  window.gsap.globalTimeline.time(window.gsap.globalTimeline.time() + (ms / 1000.0));
                  return newProgress;
                }};
              </script>
            </body>
            </html>
            """
            self.wfile.write(html.encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

class MockGatewayHandler(http.server.BaseHTTPRequestHandler):
    jobs = {} # Shared job database
    queue = [] # Simulates message queue (contains JSON-serialized strings)
    diagrams = {} # Diagram spec database
    redis_offline = False
    rate_limit_enabled = False
    rate_limit_count = {}
    logs = [] # In-memory log aggregator
    
    def log_message(self, format, *args):
        # Accumulate logs to simulate aggregated logs
        MockGatewayHandler.logs.append(format % args)
        
    def _check_auth(self):
        parsed_url = urlparse(self.path)
        params = parse_qs(parsed_url.query)
        if params.get("enforce_auth", ["false"])[0] == "true" or "auth" in self.path or "secure" in self.path:
            auth_hdr = self.headers.get("Authorization")
            if not auth_hdr or not auth_hdr.startswith("Bearer "):
                self.send_response(401)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Unauthorized: Missing or invalid token"}).encode("utf-8"))
                return False
        return True

    def do_POST(self):
        if not self._check_auth():
            return
            
        if self.redis_offline:
            self.send_response(503)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Service Unavailable: Message broker offline"}).encode("utf-8"))
            return
            
        if self.rate_limit_enabled:
            client_ip = self.client_address[0]
            count = MockGatewayHandler.rate_limit_count.get(client_ip, 0) + 1
            MockGatewayHandler.rate_limit_count[client_ip] = count
            if count > 5:
                self.send_response(429)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Too Many Requests"}).encode("utf-8"))
                return

        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length).decode('utf-8')
        
        if self.path.startswith("/api/export"):
            try:
                spec = json.loads(post_data)
                # Schema validation check (simulate R2 contract)
                if "elements" not in spec:
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": "Invalid spec: elements field is required"}).encode("utf-8"))
                    return
                
                # Check for empty elements
                if not spec["elements"]:
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": "Invalid spec: elements cannot be empty"}).encode("utf-8"))
                    return
                
                # Check for element id presence
                for el in spec.get("elements", []):
                    if "id" not in el:
                        self.send_response(400)
                        self.send_header("Content-Type", "application/json")
                        self.end_headers()
                        self.wfile.write(json.dumps({"error": "Invalid spec: element missing id"}).encode("utf-8"))
                        return
                
                job_id = str(uuid.uuid4())
                job = {
                    "job_id": job_id,
                    "status": "queued",
                    "spec": spec,
                    "format": spec.get("canvas", {}).get("format", "mp4")
                }
                MockGatewayHandler.jobs[job_id] = job
                
                # Put JSON string on the queue representing BullMQ Redis contract
                queue_payload = {
                    "job_id": job_id,
                    "spec": spec,
                    "format": job["format"]
                }
                MockGatewayHandler.queue.append(json.dumps(queue_payload))
                
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"job_id": job_id, "status": "queued"}).encode("utf-8"))
            except Exception as e:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
                
        elif self.path.startswith("/api/diagrams"):
            try:
                spec = json.loads(post_data)
                diagram_id = str(uuid.uuid4())
                MockGatewayHandler.diagrams[diagram_id] = spec
                
                # Persist to simulate database volume persistence
                try:
                    with open("mock_db_diagrams.json", "w") as f:
                        json.dump(MockGatewayHandler.diagrams, f)
                except Exception:
                    pass
                
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"diagram_id": diagram_id, "spec": spec}).encode("utf-8"))
            except Exception as e:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_GET(self):
        if not self._check_auth():
            return
            
        if self.path == "/health":
            if self.redis_offline:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "unhealthy", "redis": "offline"}).encode("utf-8"))
            else:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "healthy"}).encode("utf-8"))
            return

        if self.path.startswith("/api/export/"):
            job_id = self.path.split("/")[-1]
            job = MockGatewayHandler.jobs.get(job_id)
            if job:
                response = {
                    "job_id": job_id,
                    "status": job["status"]
                }
                if job["status"] == "completed":
                    response["download_url"] = f"http://127.0.0.1:9000/exports/{job_id}.{job['format']}"
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(response).encode("utf-8"))
            else:
                self.send_response(404)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Job not found"}).encode("utf-8"))
                
        elif self.path.startswith("/api/diagrams/"):
            diagram_id = self.path.split("/")[-1]
            # Try reloading from file to simulate database volume persistence
            if os.path.exists("mock_db_diagrams.json"):
                try:
                    with open("mock_db_diagrams.json", "r") as f:
                        MockGatewayHandler.diagrams = json.load(f)
                except Exception:
                    pass
            spec = MockGatewayHandler.diagrams.get(diagram_id)
            if spec:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"diagram_id": diagram_id, "spec": spec}).encode("utf-8"))
            else:
                self.send_response(404)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Diagram not found"}).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()
            
    def do_DELETE(self):
        if not self._check_auth():
            return
            
        if self.path.startswith("/api/diagrams/"):
            diagram_id = self.path.split("/")[-1]
            if diagram_id in MockGatewayHandler.diagrams:
                active_jobs = [j for j in MockGatewayHandler.jobs.values() if j["status"] in ("queued", "processing")]
                if active_jobs:
                    self.send_response(409)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": "Conflict: Cannot delete diagram with active export jobs"}).encode("utf-8"))
                    return
                    
                del MockGatewayHandler.diagrams[diagram_id]
                try:
                    with open("mock_db_diagrams.json", "w") as f:
                        json.dump(MockGatewayHandler.diagrams, f)
                except Exception:
                    pass
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "deleted"}).encode("utf-8"))
            else:
                self.send_response(404)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Diagram not found"}).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

class MockMinIOHandler(http.server.BaseHTTPRequestHandler):
    storage = {} # Key-value store for file uploads
    disk_full = False
    
    def log_message(self, format, *args):
        pass
        
    def do_PUT(self):
        if self.disk_full:
            self.send_response(507)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Insufficient Storage: Disk full"}).encode("utf-8"))
            return
            
        if self.path.startswith("/exports/"):
            content_length = int(self.headers.get('Content-Length', 0))
            file_data = self.rfile.read(content_length)
            MockMinIOHandler.storage[self.path] = file_data
            self.send_response(200)
            self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()
            
    def do_GET(self):
        if self.path.startswith("/exports/"):
            file_data = MockMinIOHandler.storage.get(self.path)
            if file_data:
                self.send_response(200)
                if self.path.endswith(".mp4"):
                    self.send_header("Content-Type", "video/mp4")
                elif self.path.endswith(".gif"):
                    self.send_header("Content-Type", "image/gif")
                else:
                    self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Length", str(len(file_data)))
                self.end_headers()
                self.wfile.write(file_data)
            else:
                self.send_response(404)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

class MockWorkerThread(threading.Thread):
    browser_crash = False
    minio_offline = False
    asset_timeout = False
    
    def __init__(self, frontend_url="http://127.0.0.1:3000", minio_url="http://127.0.0.1:9000"):
        super().__init__()
        self.frontend_url = frontend_url
        self.minio_url = minio_url
        self.daemon = True
        self.running = True
        
    def run(self):
        while self.running:
            if MockGatewayHandler.queue:
                payload_str = MockGatewayHandler.queue.pop(0)
                try:
                    payload = json.loads(payload_str)
                    job_id = payload["job_id"]
                except Exception:
                    job_id = payload_str
                
                job = MockGatewayHandler.jobs.get(job_id)
                if job:
                    job["status"] = "processing"
                    
                    if self.browser_crash:
                        job["status"] = "failed"
                        job["error"] = "Browser process crashed unexpectedly"
                        continue
                        
                    if self.asset_timeout:
                        time.sleep(0.01)
                        job["status"] = "failed"
                        job["error"] = "Timeout loading page assets"
                        continue
                        
                    try:
                        req_url = f"{self.frontend_url}/render-box?job_id={job_id}"
                        with urllib.request.urlopen(req_url) as response:
                            response.read() # Consume mock HTML
                    except Exception as e:
                        job["status"] = "failed"
                        job["error"] = f"Failed to load frontend: {e}"
                        continue
                    
                    time.sleep(0.01)
                    
                    ext = job["format"]
                    if ext == "gif":
                        media_bytes = b"GIF89a" + b"\x00" * 94
                    else:
                        media_bytes = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 84
                    
                    if self.minio_offline:
                        job["status"] = "failed"
                        job["error"] = "Storage service offline"
                        continue
                        
                    try:
                        upload_url = f"{self.minio_url}/exports/{job_id}.{ext}"
                        req = urllib.request.Request(upload_url, data=media_bytes, method="PUT")
                        with urllib.request.urlopen(req) as response:
                            response.read()
                        
                        job["status"] = "completed"
                    except Exception as e:
                        job["status"] = "failed"
                        job["error"] = f"Failed to upload media: {e}"
            else:
                time.sleep(0.01)

class MockEnvironment:
    def __init__(self):
        self.frontend_server = None
        self.gateway_server = None
        self.minio_server = None
        self.worker_thread = None
        
    def start(self):
        # Clear database states
        MockGatewayHandler.jobs.clear()
        MockGatewayHandler.queue.clear()
        MockGatewayHandler.diagrams.clear()
        MockMinIOHandler.storage.clear()
        MockGatewayHandler.logs.clear()
        
        # Cleanup mock DB file if exists
        if os.path.exists("mock_db_diagrams.json"):
            try:
                os.remove("mock_db_diagrams.json")
            except Exception:
                pass
        
        # Start Mock Frontend
        self.frontend_server = ThreadingHTTPServer(("127.0.0.1", 3000), MockFrontendHandler)
        self.frontend_thread = threading.Thread(target=self.frontend_server.serve_forever, daemon=True)
        self.frontend_thread.start()
        
        # Start Mock MinIO
        self.minio_server = ThreadingHTTPServer(("127.0.0.1", 9000), MockMinIOHandler)
        self.minio_thread = threading.Thread(target=self.minio_server.serve_forever, daemon=True)
        self.minio_thread.start()
        
        # Start Mock Gateway
        self.gateway_server = ThreadingHTTPServer(("127.0.0.1", 8000), MockGatewayHandler)
        self.gateway_thread = threading.Thread(target=self.gateway_server.serve_forever, daemon=True)
        self.gateway_thread.start()
        
        # Start Worker
        self.worker_thread = MockWorkerThread()
        self.worker_thread.start()
        
    def stop(self):
        if self.worker_thread:
            self.worker_thread.running = False
            self.worker_thread.join(timeout=2.0)
            
        if self.frontend_server:
            self.frontend_server.shutdown()
            self.frontend_server.server_close()
            
        if self.gateway_server:
            self.gateway_server.shutdown()
            self.gateway_server.server_close()
            
        if self.minio_server:
            self.minio_server.shutdown()
            self.minio_server.server_close()
            
        if os.path.exists("mock_db_diagrams.json"):
            try:
                os.remove("mock_db_diagrams.json")
            except Exception:
                pass
