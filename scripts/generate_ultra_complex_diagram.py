#!/usr/bin/env python3
import os
import sys
import json
import asyncio
import time
import urllib.request

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
backend_dir = os.path.join(project_root, "backend")
if project_root not in sys.path:
    sys.path.insert(0, project_root)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.api.v1.mcp import (
    validate_diagram_spec,
    compile_diagram,
    save_diagram,
    trigger_export,
    get_export_status,
)

async def generate_ultra_complex():
    print("=================================================================")
    print(" GENERATING WIDESCREEN LANDSCAPE (LR) AI PLATFORM DIAGRAM VIA MCP")
    print("=================================================================")

    artifact_dir = r"C:\Users\Administrator\.gemini\antigravity\brain\1cf9cb3b-5bd2-4c9f-9283-ce35d98320c4"
    os.makedirs(artifact_dir, exist_ok=True)

    spec = {
        "version": "2.0",
        "theme": "dark",
        "title": {
            "prefix": "Global Multi-Region",
            "highlight": "AI Platform & Lakehouse Mesh"
        },
        "signature": "@FlowDraft-Enterprise",
        "canvas": {
            "width": 2560,
            "height": 1440,
            "layoutDirection": "LR",
            "fps": 30,
            "duration": 3.0
        },
        "elements": [
            { "id": "global_dns", "type": "input", "title": "Route53 Anycast", "body": "Global DNS routing & health checks", "icon": "shield", "status": "healthy" },
            { "id": "waf_edge", "type": "input", "title": "Cloudflare WAF", "body": "L7 Firewall & Bot management", "icon": "shield", "status": "healthy" },
            { "id": "region_us_east", "type": "input", "title": "US-East ALB", "body": "Primary ingress controller", "icon": "shield", "status": "active" },
            { "id": "region_eu_west", "type": "input", "title": "EU-West ALB", "body": "Secondary ingress controller", "icon": "shield", "status": "active" },
            { "id": "auth_keycloak", "type": "card", "title": "Keycloak IAM", "body": "OAuth2 / OIDC token issuer", "icon": "shield", "status": "healthy" },
            { "id": "user_vault_db", "type": "cylinder", "title": "Cockroach Vault", "body": "Global distributed SQL cluster", "icon": "db", "status": "syncing" },
            { "id": "ai_gateway", "type": "card", "title": "LLM AI Gateway", "body": "Prompt routing & rate limiting", "icon": "scan", "status": "streaming" },
            { "id": "dec_cache_hit", "type": "diamond", "title": "Vector Cache Hit?" },
            { "id": "redis_vector", "type": "card", "title": "Redis Vector DB", "body": "HNSW embedding cache store", "icon": "package", "status": "healthy" },
            { "id": "inference_cluster", "type": "card", "title": "GPU vLLM Cluster", "body": "Tensor parallel model worker", "icon": "scan", "status": "streaming" },
            { "id": "kafka_event_bus", "type": "card", "title": "Kafka Mesh", "body": "Multi-region event stream bus", "icon": "hash", "status": "streaming" },
            { "id": "flink_stream", "type": "card", "title": "Flink Analytics", "body": "Realtime feature extraction", "icon": "scan", "status": "streaming" },
            { "id": "iceberg_lake", "type": "cylinder", "title": "Iceberg Lakehouse", "body": "ACID parquet data lake", "icon": "db", "status": "syncing" },
            { "id": "clickhouse_olap", "type": "cylinder", "title": "ClickHouse OLAP", "body": "Sub-second metrics & logs", "icon": "db", "status": "healthy" },
            { "id": "grafana_mon", "type": "card", "title": "Grafana Suite", "body": "Observability & tracing", "icon": "package", "status": "healthy" },
            { "id": "audit_archiver", "type": "cylinder", "title": "S3 Cold Vault", "body": "Compliance & legal archive", "icon": "db", "status": "healthy" }
        ],
        "connections": [
            { "from": "global_dns", "to": "waf_edge", "label": "Geo DNS", "style": "solid", "flowing": True, "color": "#10b981" },
            { "from": "waf_edge", "to": "region_us_east", "label": "US Traffic", "style": "solid", "flowing": True, "color": "#3b82f6" },
            { "from": "waf_edge", "to": "region_eu_west", "label": "EU Traffic", "style": "solid", "flowing": True, "color": "#3b82f6" },
            { "from": "region_us_east", "to": "auth_keycloak", "label": "1. Verify JWT", "style": "solid", "flowing": True },
            { "from": "region_eu_west", "to": "auth_keycloak", "label": "1. Verify JWT", "style": "solid", "flowing": True },
            { "from": "auth_keycloak", "to": "user_vault_db", "label": "Sync Identity", "style": "dashed", "color": "#06b6d4" },
            { "from": "region_us_east", "to": "ai_gateway", "label": "2. Prompt Request", "style": "solid", "flowing": True, "color": "#06b6d4" },
            { "from": "region_eu_west", "to": "ai_gateway", "label": "2. Prompt Request", "style": "solid", "flowing": True, "color": "#06b6d4" },
            { "from": "ai_gateway", "to": "dec_cache_hit", "label": "Check Embedding", "style": "solid", "flowing": True },
            { "from": "dec_cache_hit", "to": "redis_vector", "label": "Cache Hit", "style": "dashed", "color": "#10b981" },
            { "from": "dec_cache_hit", "to": "inference_cluster", "label": "Cache Miss -> Infer", "style": "solid", "flowing": True, "color": "#8b5cf6" },
            { "from": "inference_cluster", "to": "kafka_event_bus", "label": "Emit Tokens", "style": "solid", "flowing": True, "color": "#ec4899" },
            { "from": "kafka_event_bus", "to": "flink_stream", "label": "Stream Processing", "style": "solid", "flowing": True, "color": "#ec4899" },
            { "from": "flink_stream", "to": "iceberg_lake", "label": "Persist Raw", "style": "solid", "flowing": True, "color": "#06b6d4" },
            { "from": "flink_stream", "to": "clickhouse_olap", "label": "Index Analytics", "style": "dashed", "color": "#f59e0b" },
            { "from": "clickhouse_olap", "to": "grafana_mon", "label": "Query Dashboard", "style": "solid", "color": "#10b981" },
            { "from": "iceberg_lake", "to": "audit_archiver", "label": "Cold Tier Archive", "style": "dashed", "color": "#64748b" }
        ]
    }


    # 1. Validate spec via MCP tool
    print("\n[1] Validating Spec via MCP validate_diagram_spec()...")
    val_res = await validate_diagram_spec(spec)
    val_data = json.loads(val_res)
    print("Validation Output:", val_data)

    # 2. Compile diagram via MCP tool
    print("\n[2] Compiling Spec via MCP compile_diagram()...")
    comp_res = await compile_diagram(spec)
    comp_data = json.loads(comp_res)
    print(f"Compilation Title: {comp_data.get('title')} | Nodes: {comp_data.get('element_count')} | Connections: {comp_data.get('connection_count')}")

    # 3. Save diagram via MCP tool
    print("\n[3] Saving Diagram via MCP save_diagram()...")
    save_res = await save_diagram("Global Multi-Region AI Platform & Lakehouse Mesh (LR)", spec, "16-element enterprise landscape architecture", "dark")
    print("Save Response:", save_res)

    # 4. Trigger PNG Export
    print("\n[4] Triggering Export via MCP trigger_export(format='png')...")
    export_res_str = await trigger_export(spec, format="png")
    export_res = json.loads(export_res_str)
    job_id = export_res.get("job_id")
    print(f"Export Queued -> Job ID: {job_id}")

    # 5. Poll status until completed
    print("\n[5] Polling Export Status via MCP get_export_status()...")
    start_time = time.time()
    download_url = None

    while time.time() - start_time < 45:
        status_str = await get_export_status(job_id)
        status_data = json.loads(status_str)
        st = status_data.get("status")
        print(f" Elapsed: {int(time.time() - start_time)}s | Status: {st}")

        if st == "completed":
            download_url = status_data.get("download_url") or status_data.get("presigned_url")
            break
        elif st == "failed":
            print(f" [ERROR] Render Failed: {status_data.get('error_message')}")
            break

        await asyncio.sleep(2.5)

    if download_url:
        full_url = f"http://localhost:8000{download_url}" if download_url.startswith("/") else download_url
        dest_png = os.path.join(artifact_dir, "global_ai_platform.png")
        
        req = urllib.request.Request(full_url, headers={"X-MCP-API-Key": "default-mcp-key"})
        with urllib.request.urlopen(req) as resp, open(dest_png, "wb") as f:
            f.write(resp.read())

        print(f"\n[SUCCESS] Rendered Landscape PNG Downloaded to: {dest_png}")
        print(f" File Size: {os.path.getsize(dest_png)} bytes")

if __name__ == "__main__":
    asyncio.run(generate_ultra_complex())
