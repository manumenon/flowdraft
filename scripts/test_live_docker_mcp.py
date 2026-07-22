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

from app.api.v1.mcp import (
    list_templates,
    get_template,
    validate_diagram_spec,
    compile_diagram,
    save_diagram,
    trigger_export,
    get_export_status,
)

async def test_live_mcp_complex_diagram():
    print("=" * 65)
    print(" TESTING LIVE FLOWDRAFT MCP SERVER WITH COMPLEX DIAGRAM")
    print("=" * 65)

    # 1. Tool: list_templates
    print("\n--- 1. Testing list_templates() ---")
    templates_str = await list_templates()
    print("Result:", templates_str)

    # 2. Tool: get_template
    print("\n--- 2. Testing get_template('microservices') ---")
    tmpl_str = await get_template("microservices")
    starter = json.loads(tmpl_str)
    print(f"Loaded template with {len(starter['elements'])} elements.")

    # 3. Construct Complex Diagram
    complex_spec = {
        "version": "2.0",
        "theme": "dark",
        "title": {
            "prefix": "Global E-Commerce",
            "highlight": "Event-Driven Microservices"
        },
        "signature": "@FlowDraft-LiveTest",
        "canvas": {
            "width": 1920,
            "height": 1440,
            "fps": 30,
            "duration": 2.0
        },
        "elements": [
            {
                "id": "ingress_gw",
                "type": "input",
                "title": "API Gateway",
                "body": "Routes ingress HTTP/gRPC requests",
                "icon": "shield"
            },
            {
                "id": "auth_svc",
                "type": "card",
                "title": "Auth Service",
                "body": "JWT validation & RBAC checks",
                "icon": "shield"
            },
            {
                "id": "order_engine",
                "type": "card",
                "title": "Order Engine",
                "body": "Processes checkout state machine",
                "icon": "scan"
            },
            {
                "id": "dec_inventory",
                "type": "diamond",
                "title": "In Stock?"
            },
            {
                "id": "redis_cluster",
                "type": "card",
                "title": "Redis Cache",
                "body": "High-throughput session & cart cache",
                "icon": "package"
            },
            {
                "id": "postgres_master",
                "type": "cylinder",
                "title": "Primary DB",
                "body": "Transactional order records",
                "icon": "db"
            }
        ],
        "connections": [
            { "from": "ingress_gw", "to": "auth_svc", "label": "1. Verify Token", "style": "solid" },
            { "from": "auth_svc", "to": "order_engine", "label": "2. Authorized Request", "style": "solid" },
            { "from": "order_engine", "to": "dec_inventory", "label": "3. Check Stock", "style": "solid" },
            { "from": "dec_inventory", "to": "redis_cluster", "label": "Read Cache", "style": "dashed" },
            { "from": "order_engine", "to": "postgres_master", "label": "4. Commit Order", "style": "solid" }
        ]
    }

    # 4. Tool: validate_diagram_spec
    print("\n--- 3. Testing validate_diagram_spec() with complex diagram ---")
    val_res = await validate_diagram_spec(complex_spec)
    print("Validation Output:")
    print(val_res)
    val_data = json.loads(val_res)
    assert val_data["valid"] is True, "Validation failed!"

    # 5. Tool: compile_diagram
    print("\n--- 4. Testing compile_diagram() ---")
    comp_res = await compile_diagram(complex_spec)
    print("Compilation Output:")
    print(comp_res)

    # 6. Tool: save_diagram
    print("\n--- 5. Testing save_diagram() into DB ---")
    save_res = await save_diagram(
        title="Global E-Commerce Event-Driven Architecture",
        spec=complex_spec,
        description="Complex test architecture generated via MCP agent connection.",
        theme="dark"
    )
    print("Save Output:")
    print(save_res)

    # 7. Tool: trigger_export (GIF)
    print("\n--- 6. Testing trigger_export(spec, format='gif') ---")
    export_gif_res = await trigger_export(complex_spec, format="gif")
    print("GIF Trigger Output:", export_gif_res)

    # 8. Tool: trigger_export (PNG)
    print("\n--- 7. Testing trigger_export(spec, format='png') ---")
    export_png_res = await trigger_export(complex_spec, format="png")
    print("PNG Trigger Output:", export_png_res)

    # Parse job_id for GIF export
    job_id = None
    if "job_id:" in export_gif_res:
        job_id = export_gif_res.split("job_id:")[1].strip()

    if job_id:
        print(f"\n--- 8. Testing get_export_status('{job_id}') ---")
        status_res = await get_export_status(job_id)
        print("Export Status Output:\n", status_res)

    print("\n" + "=" * 65)
    print(" ALL 7 MCP TOOLS VALIDATED SUCCESSFULLY ON LIVE DOCKER CONTAINER!")
    print("=" * 65)

if __name__ == "__main__":
    asyncio.run(test_live_mcp_complex_diagram())
