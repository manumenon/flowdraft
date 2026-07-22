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

from app.api.v1.mcp import compile_diagram, validate_diagram_spec, trigger_export

async def inspect_complex_layout():
    print("=================================================================")
    print(" DEEP INSPECTION & ALIGNMENT VALIDATION OF COMPLEX MCP DIAGRAM")
    print("=================================================================")

    # Define a complex 12-element multi-tier distributed system
    spec = {
        "version": "2.0",
        "theme": "dark",
        "title": {
            "prefix": "Enterprise Tier-1",
            "highlight": "FinTech Platform Architecture"
        },
        "signature": "@FlowDraft-LayoutValidator",
        "canvas": {
            "width": 2560,
            "height": 1600,
            "fps": 30,
            "duration": 3.0
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

    # Step 1: Structural Spec Validation
    print("\n[STEP 1] Validating Spec Schema...")
    val_json = await validate_diagram_spec(spec)
    val_data = json.loads(val_json)
    print(f"Validation Status: valid={val_data.get('valid')}, elements={val_data.get('element_count')}, connections={val_data.get('connection_count')}")

    # Step 2: Compile & Inspect Layout Geometry
    print("\n[STEP 2] Compiling Layout Geometry via ELK Engine...")
    comp_json = await compile_diagram(spec)
    comp_data = json.loads(comp_json)
    
    if comp_data.get("status") != "compiled":
        print(f"Compilation Failed: {comp_data}")
        return

    print("\n--- COMPILED LAYOUT METRICS ---")
    print(f"Title: {comp_data.get('title')}")
    print(f"Total Nodes: {comp_data.get('element_count')}")
    print(f"Total Connections: {comp_data.get('connection_count')}")

    bbox = comp_data.get("bounding_box", {})
    print(f"\n--- BOUNDING BOX ---")
    print(f"X: {bbox.get('min_x')} -> {bbox.get('max_x')} (Width: {bbox.get('width')}px)")
    print(f"Y: {bbox.get('min_y')} -> {bbox.get('max_y')} (Height: {bbox.get('height')}px)")

    nodes = comp_data.get("nodes", [])
    print(f"\n--- NODE PLACEMENT & ALIGNMENT ANALYSIS ({len(nodes)} NODES) ---")
    user_nodes = [n for n in nodes if not n["id"].startswith("decor_")]
    decor_nodes = [n for n in nodes if n["id"].startswith("decor_")]

    print("\n[USER CARD NODES]")
    for n in user_nodes:
        right = n['x'] + n['width']
        bottom = n['y'] + n['height']
        print(f" - [{n['id']}] ({n['type']}): pos=({n['x']:.1f}, {n['y']:.1f}) size={n['width']}x{n['height']} bounds=({n['x']:.1f}, {n['y']:.1f}) -> ({right:.1f}, {bottom:.1f})")

    # Step 3: Overlap & Collision Check
    print("\n[STEP 3] Running 2D AABB Collision & Overlap Check...")
    collisions = []
    for i in range(len(user_nodes)):
        for j in range(i + 1, len(user_nodes)):
            n1, n2 = user_nodes[i], user_nodes[j]
            # Check bounding box overlap with padding
            overlap_x = (n1['x'] < n2['x'] + n2['width']) and (n1['x'] + n1['width'] > n2['x'])
            overlap_y = (n1['y'] < n2['y'] + n2['height']) and (n1['y'] + n1['height'] > n2['y'])
            if overlap_x and overlap_y:
                collisions.append((n1['id'], n2['id']))

    if collisions:
        print(f" [FAIL] Found {len(collisions)} overlapping node pairs: {collisions}")
    else:
        print(f" [PASS] ZERO OVERLAPS DETECTED! All {len(user_nodes)} nodes are cleanly separated.")

    # Step 4: Connection Routing Alignment Check
    connections = comp_data.get("connections", [])
    print(f"\n[STEP 4] Connection Path Alignment Check ({len(connections)} CONNECTIONS)...")
    node_map = {n['id']: n for n in user_nodes}

    path_errors = []
    for idx, conn in enumerate(connections):
        src_id = conn.get("from")
        tgt_id = conn.get("to")
        points = conn.get("points", [])
        
        start_pt = points[0] if points else [0, 0]
        end_pt = points[-1] if points else [0, 0]

        print(f" Connection {idx+1}: '{src_id}' -> '{tgt_id}' ({conn.get('style')}) | {len(points)} waypoints | start=({start_pt[0]:.1f}, {start_pt[1]:.1f}) end=({end_pt[0]:.1f}, {end_pt[1]:.1f})")

        # Verify points array is valid
        if len(points) < 2:
            path_errors.append(f"Connection {src_id} -> {tgt_id} has insufficient waypoints.")

    if path_errors:
        print(f" [FAIL] Connection Routing Errors: {path_errors}")
    else:
        print(f" [PASS] ALL {len(connections)} CONNECTIONS HAVE VALID ALIGNED WAYPOINTS!")

    # Step 5: Export Trigger Check
    print("\n[STEP 5] Triggering GIF Export for Complex Architecture...")
    export_res = await trigger_export(spec, format="gif")
    print(f"Export Trigger Response: {export_res}")

    print("\n=================================================================")
    print(" DEEP MCP LAYOUT & ALIGNMENT VERIFICATION COMPLETE!")
    print("=================================================================")

if __name__ == "__main__":
    asyncio.run(inspect_complex_layout())
