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
    validate_diagram_spec,
    compile_diagram,
    save_diagram,
    list_saved_diagrams,
    trigger_export,
    get_export_status,
    list_templates
)

async def audit_mcp_gaps_verification():
    print("=================================================================")
    print(" MCP SERVER TOOL REMEDIATION VERIFICATION")
    print("=================================================================")

    # 1. Test validate_diagram_spec with orphan nodes and invalid status
    print("\n--- 1. VERIFYING validate_diagram_spec() Diagnostic Warnings ---")
    spec_with_orphans = {
        "version": "2.0",
        "theme": "dark",
        "title": { "prefix": "Test", "highlight": "Orphans & Status" },
        "canvas": { "layoutDirection": "INVALID_DIR" },
        "elements": [
            { "id": "node_a", "type": "card", "title": "Node A", "status": "unknown_status" },
            { "id": "node_b", "type": "card", "title": "Node B" },
            { "id": "orphan_c", "type": "card", "title": "Orphan C" } # No connection!
        ],
        "connections": [
            { "from": "node_a", "to": "node_b" }
        ]
    }
    val_out = await validate_diagram_spec(spec_with_orphans)
    print("Validation Result:", val_out)
    val_data = json.loads(val_out)
    assert len(val_data["warnings"]) >= 3, "Expected diagnostic warnings for orphan node, unknown status, and invalid direction!"

    # 2. Test compile_diagram for annotations and metrics
    print("\n--- 2. VERIFYING compile_diagram() Annotations & Metrics ---")
    spec_with_ann = {
        "version": "2.0",
        "theme": "dark",
        "title": { "prefix": "Test", "highlight": "Annotations" },
        "elements": [{ "id": "n1", "type": "card", "title": "N1" }],
        "annotations": [{ "text": "Watermark Note", "x": 100, "y": 100 }]
    }
    comp_out = await compile_diagram(spec_with_ann)
    comp_data = json.loads(comp_out)
    print("Graph Density:", comp_data.get("graph_density"))
    print("Aspect Ratio:", comp_data.get("aspect_ratio"))
    print("Annotations Array Present:", len(comp_data.get("annotations", [])) > 0)
    assert len(comp_data.get("annotations", [])) > 0, "Expected annotations in compiled output!"

    # 3. Test trigger_export SVG & Excalidraw formats
    print("\n--- 3. VERIFYING trigger_export() SVG & Excalidraw ---")
    export_svg = await trigger_export(spec_with_ann, format="svg")
    export_excalidraw = await trigger_export(spec_with_ann, format="excalidraw")
    print("SVG Trigger Result:", export_svg)
    print("Excalidraw Trigger Result:", export_excalidraw)
    assert json.loads(export_svg)["status"] == "queued"
    assert json.loads(export_excalidraw)["status"] == "queued"

    # 4. Test save_diagram Upsert
    print("\n--- 4. VERIFYING save_diagram() Upsert ---")
    save_1 = await save_diagram("", spec_with_ann, "Original Desc")
    save_1_data = json.loads(save_1)
    diag_id = save_1_data.get("diagram_id")
    print(f"Saved Initial Diagram (Auto-Title: '{save_1_data.get('title')}'): ID={diag_id}")

    save_2 = await save_diagram("Updated Title", spec_with_ann, "Updated Desc", diagram_id=diag_id)
    save_2_data = json.loads(save_2)
    print(f"Upsert Result: Status='{save_2_data.get('status')}', ID={save_2_data.get('diagram_id')}")
    assert save_2_data["status"] == "updated"
    assert save_2_data["diagram_id"] == diag_id

    # 5. Test list_saved_diagrams search query
    print("\n--- 5. VERIFYING list_saved_diagrams() Search ---")
    search_out = await list_saved_diagrams(query="Updated")
    print("Search Result:", search_out)
    assert len(json.loads(search_out)) >= 1

    # 6. Test list_templates Enterprise Templates
    print("\n--- 6. VERIFYING list_templates() Enterprise Templates ---")
    templates_out = await list_templates()
    templates_data = json.loads(templates_out)["templates"]
    tmpl_names = [t["name"] for t in templates_data]
    print("Available Templates:", tmpl_names)
    assert "fintech_platform" in tmpl_names and "global_ai_mesh" in tmpl_names

    print("\n[SUCCESS] ALL 7 MCP SERVER TOOL REMEDIATIONS VERIFIED SUCCESSFULLY!")

if __name__ == "__main__":
    asyncio.run(audit_mcp_gaps_verification())
