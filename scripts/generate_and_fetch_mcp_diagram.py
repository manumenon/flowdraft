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

from app.api.v1.mcp import trigger_export, get_export_status

async def generate_and_fetch():
    print("=================================================================")
    print(" GENERATING COMPLEX DIAGRAM VIA MCP SERVER & FETCHING MEDIA")
    print("=================================================================")

    artifact_dir = r"C:\Users\Administrator\.gemini\antigravity\brain\1cf9cb3b-5bd2-4c9f-9283-ce35d98320c4"
    os.makedirs(artifact_dir, exist_ok=True)

    complex_spec = {
        "version": "2.0",
        "theme": "dark",
        "title": {
            "prefix": "Enterprise Tier-1",
            "highlight": "FinTech Platform Architecture"
        },
        "signature": "@FlowDraft-MCP",
        "canvas": {
            "width": 1920,
            "height": 1440,
            "fps": 30,
            "duration": 2.0
        },
        "elements": [
            { "id": "cdn_edge", "type": "input", "title": "Cloudflare CDN", "body": "Edge TLS & DDoS protection", "icon": "shield" },
            { "id": "ingress_alb", "type": "input", "title": "AWS ALB", "body": "Ingress HTTP/2 router", "icon": "shield" },
            { "id": "auth_svc", "type": "card", "title": "OAuth2 Auth Svc", "body": "JWT issue & verification", "icon": "shield" },
            { "id": "user_db", "type": "cylinder", "title": "User Profile DB", "body": "Postgres primary cluster", "icon": "db" },
            { "id": "order_svc", "type": "card", "title": "Order Engine", "body": "Checkout state machine", "icon": "scan" },
            { "id": "dec_fraud", "type": "diamond", "title": "Fraud Pass?" },
            { "id": "payment_gw", "type": "card", "title": "Stripe Gateway", "body": "External payment capture", "icon": "shield" },
            { "id": "kafka_bus", "type": "card", "title": "Event Streaming", "body": "Kafka multi-region broker", "icon": "hash" },
            { "id": "stream_proc", "type": "card", "title": "Flink Processor", "body": "Realtime fraud & metrics", "icon": "scan" },
            { "id": "analytics_db", "type": "cylinder", "title": "ClickHouse OLAP", "body": "Columnar analytics DB", "icon": "db" },
            { "id": "notif_svc", "type": "card", "title": "Notify Worker", "body": "APNS/FCM push gateway", "icon": "package" }
        ],
        "connections": [
            { "from": "cdn_edge", "to": "ingress_alb", "label": "Edge Traffic", "style": "solid" },
            { "from": "ingress_alb", "to": "auth_svc", "label": "Validate Auth", "style": "solid" },
            { "from": "auth_svc", "to": "user_db", "label": "User Lookup", "style": "dashed" },
            { "from": "ingress_alb", "to": "order_svc", "label": "POST /checkout", "style": "solid" },
            { "from": "order_svc", "to": "dec_fraud", "label": "Risk Score", "style": "solid" },
            { "from": "dec_fraud", "to": "payment_gw", "label": "Approved", "style": "solid" },
            { "from": "payment_gw", "to": "kafka_bus", "label": "Payment Settled", "style": "solid" },
            { "from": "kafka_bus", "to": "stream_proc", "label": "Stream Ingest", "style": "solid" },
            { "from": "stream_proc", "to": "analytics_db", "label": "Batch Sink", "style": "dashed" },
            { "from": "kafka_bus", "to": "notif_svc", "label": "Dispatch Event", "style": "solid" }
        ]
    }

    # 1. Trigger PNG Export via MCP tool
    print("\n[1] Calling MCP Tool: trigger_export(spec, format='png')...")
    png_res_str = await trigger_export(complex_spec, format="png")
    print("Response:", png_res_str)
    
    png_res = json.loads(png_res_str)
    png_job_id = png_res.get("job_id")

    # 2. Trigger GIF Export via MCP tool
    print("\n[2] Calling MCP Tool: trigger_export(spec, format='gif')...")
    gif_res_str = await trigger_export(complex_spec, format="gif")
    print("Response:", gif_res_str)

    gif_res = json.loads(gif_res_str)
    gif_job_id = gif_res.get("job_id")

    # 3. Poll status until completion
    print("\n[3] Polling MCP Tool: get_export_status()...")
    max_wait = 45
    start_time = time.time()

    png_url = None
    gif_url = None

    while time.time() - start_time < max_wait:
        png_status_str = await get_export_status(png_job_id)
        png_status_data = json.loads(png_status_str)
        status = png_status_data.get("status")
        print(f" Elapsed: {int(time.time() - start_time)}s | PNG Job Status: {status}")

        if status == "completed":
            png_url = png_status_data.get("download_url") or png_status_data.get("presigned_url")
            break
        elif status == "failed":
            print(f" [ERROR] PNG Job Failed: {png_status_data.get('error_message')}")
            break

        await asyncio.sleep(2.5)

    if png_url:
        print(f"\n[4] Download URL acquired: {png_url}")
        # Fetch file from local backend proxy
        full_download_url = f"http://localhost:8000{png_url}" if png_url.startswith("/") else png_url
        dest_png_path = os.path.join(artifact_dir, "fintech_architecture.png")
        
        try:
            req = urllib.request.Request(full_download_url, headers={"X-MCP-API-Key": "default-mcp-key"})
            with urllib.request.urlopen(req) as resp, open(dest_png_path, "wb") as out_file:
                out_file.write(resp.read())
            print(f" [SUCCESS] Rendered PNG downloaded & saved to: {dest_png_path}")
            print(f" File Size: {os.path.getsize(dest_png_path)} bytes")
        except Exception as e:
            print(f" [ERROR] Error downloading PNG: {e}")
    else:
        print(" [WARNING] PNG Job did not complete within timeout limit.")

if __name__ == "__main__":
    asyncio.run(generate_and_fetch())
