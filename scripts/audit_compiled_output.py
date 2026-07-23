#!/usr/bin/env python3
import os
import sys
import json
import asyncio

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
backend_dir = os.path.join(project_root, "backend")
if project_root not in sys.path:
    sys.path.insert(0, project_root)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.api.v1.mcp import compile_diagram

async def audit_compiler():
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

    res_str = await compile_diagram(spec)
    res = json.loads(res_str)

    print("=================================================================")
    print(" COMPILER OUTPUT CRITIQUE & GEOMETRY METRICS AUDIT")
    print("=================================================================")
    print(f"Canvas Dimensions: {res.get('canvas_dimensions')}")
    print(f"Total Nodes (elements + decors): {len(res.get('nodes', []))}")
    print(f"Total Connections: {len(res.get('connections', []))}")
    print(f"Bounding Box: {res.get('bounding_box')}")

    nodes = res.get('nodes', [])
    connections = res.get('connections', [])

    print("\n--- NODE POSITION ANALYSIS ---")
    for n in nodes:
        print(f"Node [{n['id']}] ({n['type']}): pos=({n['x']}, {n['y']}), size=({n['width']}x{n['height']})")

    print("\n--- CONNECTION ROUTING ANALYSIS ---")
    for c in connections:
        pts = c.get('points', [])
        print(f"Connection [{c['from']} -> {c['to']}]: {len(pts)} routing waypoints -> {pts}")

if __name__ == "__main__":
    asyncio.run(audit_compiler())
