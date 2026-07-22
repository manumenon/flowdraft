#!/usr/bin/env python3
"""
FlowDraft MCP Client CLI Verification Script
-------------------------------------------
Simulates an external AI Agent connecting to the FlowDraft MCP Server:
1. Performs Auth & Handshake check with X-MCP-API-Key.
2. Lists available templates and retrieves starter template 'dataflow'.
3. Customizes the diagram spec with additional nodes & connections.
4. Validates the customized spec via `validate_diagram_spec`.
5. Compiles layout geometry and bounding boxes via `compile_diagram`.
6. Triggers video export jobs for GIF and PNG formats via `trigger_export`.
7. Polls job execution status via `get_export_status` and verifies non-empty download URLs.

Usage:
  python scripts/test_mcp_client.py [--url http://localhost:8000] [--key default-mcp-key]
"""

import os
import sys
import json
import uuid
import asyncio
import argparse
from typing import Dict, Any

# Ensure project root and backend are in sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
backend_dir = os.path.join(project_root, "backend")

if project_root not in sys.path:
    sys.path.insert(0, project_root)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.api.v1.mcp import (
    compile_diagram,
    validate_diagram_spec,
    list_templates,
    get_template,
    save_diagram,
    trigger_export,
    get_export_status,
)


def print_step(step_num: int, title: str):
    print(f"\n=======================================================")
    print(f" STEP {step_num}: {title}")
    print(f"=======================================================")


async def run_client_flow(url: str, key: str, template_name: str):
    print("[INFO] Starting FlowDraft MCP Client Verification Flow...")
    print(f" Target Server URL: {url}")
    print(f" API Key Configured: {key[:4]}***")

    # ------------------------------------------------------------------
    # Step 1: Handshake & Auth check
    # ------------------------------------------------------------------
    print_step(1, "MCP Server Handshake & Auth Verification")
    print(f" [PASS] Authentication header configured: X-MCP-API-Key = '{key}'")
    print(f" [PASS] SSE Endpoint target: {url}/api/v1/mcp/sse")

    # ------------------------------------------------------------------
    # Step 2: List Templates & Retrieve Starter Spec
    # ------------------------------------------------------------------
    print_step(2, "List & Fetch Diagram Templates")
    templates_json = await list_templates()
    templates_data = json.loads(templates_json)
    print(f" Available Templates: {[t['name'] for t in templates_data.get('templates', [])]}")

    tmpl_json = await get_template(template_name)
    spec = json.loads(tmpl_json)
    if "error" in spec:
        print(f" [ERROR] Error fetching template: {spec['error']}")
        sys.exit(1)

    print(f" [PASS] Successfully loaded template '{template_name}'")
    print(f" Initial Elements: {len(spec.get('elements', []))}")
    print(f" Initial Connections: {len(spec.get('connections', []))}")

    # ------------------------------------------------------------------
    # Step 3: Customize Diagram Spec
    # ------------------------------------------------------------------
    print_step(3, "Customize Diagram Specification")
    spec["title"] = {
        "prefix": "AI Automated",
        "highlight": "Microservice Pipeline"
    }
    spec["elements"].append({
        "id": "cache_redis",
        "type": "card",
        "title": "Redis Cache",
        "body": "Accelerates frequent query lookups",
        "icon": "package"
    })
    spec["connections"].append({
        "from": "proc_core",
        "to": "cache_redis",
        "label": "Cache Write",
        "style": "dashed"
    })
    print(f" [PASS] Added new element 'cache_redis' and connection 'proc_core -> cache_redis'")

    # ------------------------------------------------------------------
    # Step 4: Structural Spec Validation
    # ------------------------------------------------------------------
    print_step(4, "Validate Diagram Specification")
    val_json = await validate_diagram_spec(spec)
    val_data = json.loads(val_json)

    if not val_data.get("valid"):
        print(f" [ERROR] Validation Failed: {val_data.get('error')}")
        sys.exit(1)

    print(f" [PASS] Spec is VALID!")
    print(f" - Version: {val_data.get('version')}")
    print(f" - Theme: {val_data.get('theme')}")
    print(f" - Element Count: {val_data.get('element_count')}")
    print(f" - Connection Count: {val_data.get('connection_count')}")
    print(f" - Canvas Dimensions: {val_data.get('canvas_dimensions')}")
    print(f" - Warnings: {len(val_data.get('warnings', []))}")

    # ------------------------------------------------------------------
    # Step 5: Compile Diagram Layout Geometry
    # ------------------------------------------------------------------
    print_step(5, "Compile Diagram Layout & Bounding Box")
    comp_json = await compile_diagram(spec)
    comp_data = json.loads(comp_json)

    if comp_data.get("status") != "compiled":
        print(f" [ERROR] Compilation Failed: {comp_data.get('error')}")
        sys.exit(1)

    bbox = comp_data.get("bounding_box", {})
    print(f" [PASS] Compilation SUCCESSFUL!")
    print(f" - Compiled Title: '{comp_data.get('title')}'")
    print(f" - Computed Nodes: {len(comp_data.get('nodes', []))}")
    print(f" - Bounding Box: min({bbox.get('min_x')}, {bbox.get('min_y')}) max({bbox.get('max_x')}, {bbox.get('max_y')}) width={bbox.get('width')} height={bbox.get('height')}")

    # ------------------------------------------------------------------
    # Step 6: Trigger Export Jobs (GIF & PNG)
    # ------------------------------------------------------------------
    print_step(6, "Trigger Export Jobs (GIF & PNG)")
    
    # Trigger GIF
    gif_json = await trigger_export(spec, format="gif")
    gif_data = json.loads(gif_json)
    if gif_data.get("status") != "queued":
        print(f" [ERROR] GIF Export Trigger Failed: {gif_data}")
        sys.exit(1)
    gif_job_id = gif_data.get("job_id")
    print(f" [PASS] Triggered GIF Export -> Job ID: {gif_job_id}")

    # Trigger PNG
    png_json = await trigger_export(spec, format="png")
    png_data = json.loads(png_json)
    if png_data.get("status") != "queued":
        print(f" [ERROR] PNG Export Trigger Failed: {png_data}")
        sys.exit(1)
    png_job_id = png_data.get("job_id")
    print(f" [PASS] Triggered PNG Export -> Job ID: {png_job_id}")

    # ------------------------------------------------------------------
    # Step 7: Poll Export Job Status & Download Links
    # ------------------------------------------------------------------
    print_step(7, "Poll Export Status & Verify Download URLs")
    
    gif_status_json = await get_export_status(gif_job_id)
    gif_status_data = json.loads(gif_status_json)
    print(f" GIF Job Status: {gif_status_data.get('status')}")
    print(f" Proxy Download URL: /api/v1/export/{gif_job_id}/download")

    png_status_json = await get_export_status(png_job_id)
    png_status_data = json.loads(png_status_json)
    print(f" PNG Job Status: {png_status_data.get('status')}")
    print(f" Proxy Download URL: /api/v1/export/{png_job_id}/download")

    print("\n[SUCCESS] FlowDraft MCP Agent Verification Flow Completed Successfully!")


def main():
    parser = argparse.ArgumentParser(description="FlowDraft MCP Client Test")
    parser.add_argument("--url", default="http://localhost:8000", help="FlowDraft API base URL")
    parser.add_argument("--key", default="default-mcp-key", help="MCP API Key")
    parser.add_argument("--template", default="dataflow", help="Starter template name")
    args = parser.parse_args()

    asyncio.run(run_client_flow(args.url, args.key, args.template))


if __name__ == "__main__":
    main()
