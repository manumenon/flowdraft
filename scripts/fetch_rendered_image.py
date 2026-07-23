import os
import sys

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
backend_dir = os.path.join(project_root, "backend")
if project_root not in sys.path:
    sys.path.insert(0, project_root)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.services.storage import MinioStorage

def fetch_and_save_image():
    storage = MinioStorage()
    job_id = "4477f24b-d589-4b84-bc64-a6ebbebfbc51"
    object_name = f"{job_id}.png"
    target_path = r"C:\Users\Administrator\.gemini\antigravity\brain\1cf9cb3b-5bd2-4c9f-9283-ce35d98320c4\agentic_rag_perfect_hero_centered.png"
    
    response = storage.client.get_object(storage.bucket_name, object_name)
    with open(target_path, "wb") as f:
        f.write(response.read())
    response.close()
    response.release_conn()
    print(f"Saved artifact image to {target_path}")

if __name__ == "__main__":
    fetch_and_save_image()
