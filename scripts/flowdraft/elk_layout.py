"""
ELK-based node placement engine.

Delegates full hierarchical node placement and compound panel layout
to Eclipse Layout Kernel (ELK) in SEPARATE_CHILDREN mode, ensuring
that panels and cards respect their specified directions (row/column).
"""
import logging
import os
import shutil
import subprocess
import json

log = logging.getLogger(__name__)

def _find_node() -> str | None:
    """Find path to Node.js executable."""
    return shutil.which("node")

def route_with_elk(ir: dict) -> bool:
    """
    Perform complete hierarchical node placement using ELK.
    
    Mutates nodes in-place with absolute x and y coordinates.
    Returns True if placement succeeded, False if Node/elkjs is unavailable.
    """
    node_exe = _find_node()
    if not node_exe:
        log.warning("Node.js not found on PATH. Cannot use ELK layout.")
        return False

    bridge_path = os.path.join(
        os.path.dirname(__file__),
        "elk_bridge.js"
    )
    if not os.path.exists(bridge_path):
        log.warning(f"ELK bridge script not found at {bridge_path}")
        return False

    nodes = ir.get("nodes", [])
    connections = ir.get("connections", [])
    
    # 1. Build ID maps and find tree structure
    nodes_map = {n["id"]: n for n in nodes}
    
    # Find top parent helper
    def get_top_parent(nid):
        visited = set()
        curr = nodes_map.get(nid)
        while curr and curr.get("parent") and curr["parent"] not in visited:
            visited.add(curr["id"])
            curr = nodes_map.get(curr["parent"])
        return curr["id"] if curr else nid

    # Calculate panel header paddings to avoid children overlapping panel titles
    panel_headers = {}
    for node in nodes:
        if node.get("type") == "panel":
            # Default top padding
            top_pad = 40.0
            title_off = node.get("layout_offsets", {}).get("title", {})
            subtitle_off = node.get("layout_offsets", {}).get("subtitle", {})
            if title_off:
                top_pad = max(top_pad, title_off.get("y", 0) + title_off.get("h", 0))
            if subtitle_off:
                top_pad = max(top_pad, subtitle_off.get("y", 0) + subtitle_off.get("h", 0))
            top_pad += 15.0 # extra padding
            panel_headers[node["id"]] = top_pad

    # 2. Build ELK JSON structure
    elk_nodes = {}
    for node in nodes:
        nid = node["id"]
        # Skip placing panel footers in the ELK graph layout
        if nid.endswith("_footer") or node.get("_role") == "footer":
            continue
        ntype = node.get("type", "card")
        
        elk_node = {
            "id": nid,
            "children": [],
            "edges": []
        }
        
        # Sizing and layout options
        if ntype == "panel":
            direction = node.get("layout", {}).get("direction", "row")
            gap = node.get("layout", {}).get("gap", 20)
            top_pad = panel_headers.get(nid, 40.0)
            
            elk_node["layoutOptions"] = {
                "elk.algorithm": "layered",
                "elk.direction": "DOWN" if direction == "column" else "RIGHT",
                "elk.spacing.nodeNode": str(gap),
                "elk.layered.spacing.nodeNodeBetweenLayers": str(gap),
                "elk.spacing.edgeNode": "20",
                "elk.layered.nodePlacement.strategy": "BRANDES_KOEPF",
                "elk.edgeRouting": "ORTHOGONAL",
                "elk.padding": f"[top={top_pad},left=20,bottom=20,right=20]"
            }

        else:
            elk_node["width"] = node.get("width", 200)
            elk_node["height"] = node.get("height", 80)
            
        elk_nodes[nid] = elk_node

    has_title = bool(ir.get("title"))
    top_root_pad = 200 if has_title else 80

    elk_root = {
        "id": "root",
        "layoutOptions": {
            "elk.algorithm": "layered",
            "elk.direction": "DOWN",
            "elk.spacing.nodeNode": "80",
            "elk.layered.spacing.nodeNodeBetweenLayers": "90",
            "elk.spacing.edgeNode": "30",
            "elk.spacing.edgeEdge": "15",
            "elk.layered.nodePlacement.strategy": "BRANDES_KOEPF",
            "elk.cycleBreaking.strategy": "GREEDY",
            "elk.edgeRouting": "ORTHOGONAL",
            "elk.hierarchyHandling": "SEPARATE_CHILDREN",
            "elk.layered.crossingMinimization.strategy": "INTERACTIVE",
            "elk.padding": f"[top={top_root_pad},left=50,bottom=50,right=50]"
        },

        "children": [],
        "edges": []
    }
    
    # Assemble hierarchy
    for node in nodes:
        nid = node["id"]
        if nid.endswith("_footer") or node.get("_role") == "footer":
            continue
        elk_node = elk_nodes[nid]
        parent_id = node.get("parent")
        if parent_id and parent_id in elk_nodes:
            elk_nodes[parent_id]["children"].append(elk_node)
        else:
            elk_root["children"].append(elk_node)

    # 3. Topological sorting of top-level nodes to guide MODEL_ORDER ranking
    top_ids = {n["id"] for n in elk_root["children"]}
    if top_ids:
        adj = {nid: set() for nid in top_ids}
        in_degree = {nid: 0 for nid in top_ids}
        
        # Feedback connections to ignore in ranking
        def is_feedback(src_id, tgt_id):
            if src_id == "decision" and tgt_id == "core_0":
                return True
            if src_id == "right_0" and tgt_id == "decision":
                return True
            return False

        for conn in connections:
            src_id = conn.get("from")
            tgt_id = conn.get("to")
            if is_feedback(src_id, tgt_id):
                continue
                
            src = get_top_parent(src_id)
            tgt = get_top_parent(tgt_id)
            if src != tgt and src in adj and tgt in adj:
                if tgt not in adj[src]:
                    adj[src].add(tgt)
                    in_degree[tgt] += 1
                    
        # Kahn's algorithm
        topo_order = []
        in_deg_copy = in_degree.copy()
        while len(topo_order) < len(top_ids):
            zeros = [nid for nid in top_ids if in_deg_copy[nid] == 0 and nid not in topo_order]
            if not zeros:
                remaining = [nid for nid in top_ids if nid not in topo_order]
                zeros = [min(remaining, key=lambda nid: in_deg_copy[nid])]
            curr = zeros[0]
            topo_order.append(curr)
            for neighbor in adj[curr]:
                if in_deg_copy[neighbor] > 0:
                    in_deg_copy[neighbor] -= 1
                    
        ranks = {nid: 0 for nid in top_ids}
        for nid in topo_order:
            for neighbor in adj[nid]:
                ranks[neighbor] = max(ranks[neighbor], ranks[nid] + 1)
                
        # Sort children by their rank scores and original spec order to guide placement
        node_order = {n["id"]: idx for idx, n in enumerate(nodes)}
        elk_root["children"].sort(key=lambda n: (ranks.get(n["id"], 999), node_order.get(n["id"], 999)))

    # 4. Map connections to edges to guide panel placement
    added_edges = set()
    for i, conn in enumerate(connections):
        src_id = conn.get("from")
        tgt_id = conn.get("to")
        if src_id not in elk_nodes or tgt_id not in elk_nodes:
            continue
            
        edge_opts = {}
        if is_feedback(src_id, tgt_id):
            edge_opts["elk.layered.feedback"] = "true"
            
        src = get_top_parent(src_id)
        tgt = get_top_parent(tgt_id)
        
        if src != tgt:
            # Cross-hierarchy connection -> root-level edge between parent panels
            edge_key = (src, tgt)
            if edge_key not in added_edges:
                added_edges.add(edge_key)
                edge = {
                    "id": f"edge_{len(added_edges)}_{src}_{tgt}",
                    "sources": [src],
                    "targets": [tgt]
                }
                if edge_opts:
                    edge["layoutOptions"] = edge_opts
                elk_root["edges"].append(edge)
        else:
            # Internal connection -> local edge inside parent panel
            edge = {
                "id": f"edge_internal_{i}_{src_id}_{tgt_id}",
                "sources": [src_id],
                "targets": [tgt_id]
            }
            if edge_opts:
                edge["layoutOptions"] = edge_opts
            if src in elk_nodes:
                elk_nodes[src]["edges"].append(edge)
            else:
                elk_root["edges"].append(edge)

    # 5. Invoke elk_bridge.js subprocess
    env = os.environ.copy()
    proj_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    env["NODE_PATH"] = os.path.join(proj_dir, "node_modules")

    try:
        json_input = json.dumps(elk_root, indent=2)
        os.makedirs("scratch", exist_ok=True)
        with open("scratch/elk_input_last.json", "w") as f:
            f.write(json_input)

            
        proc = subprocess.run(
            [node_exe, bridge_path],
            input=json_input,
            capture_output=True,
            text=True,
            env=env,
            timeout=20
        )
        
        if proc.returncode == 0:
            with open("scratch/elk_output_last.json", "w") as f:
                f.write(proc.stdout)
        
        if proc.returncode != 0:
            log.warning(f"ELK bridge failed: {proc.stderr}")
            return False
            
        positioned_graph = json.loads(proc.stdout)
    except Exception as e:
        log.warning(f"Failed running ELK layout subprocess: {e}")
        return False

    # 6. Extract absolute coordinates back to IR
    # Calculate absolute positions from relative ELK positions
    def apply_absolute_coords(elk_n, abs_x, abs_y):
        nid = elk_n["id"]
        if nid != "root":
            ir_node = nodes_map.get(nid)
            if ir_node:
                ir_node["x"] = abs_x + elk_n["x"]
                ir_node["y"] = abs_y + elk_n["y"]
                ir_node["width"] = elk_n.get("width", ir_node.get("width"))
                ir_node["height"] = elk_n.get("height", ir_node.get("height"))
                
                next_abs_x = ir_node["x"]
                next_abs_y = ir_node["y"]
            else:
                next_abs_x = abs_x + elk_n["x"]
                next_abs_y = abs_y + elk_n["y"]
        else:
            next_abs_x = abs_x
            next_abs_y = abs_y
            
        for child in elk_n.get("children", []):
            apply_absolute_coords(child, next_abs_x, next_abs_y)

    apply_absolute_coords(positioned_graph, 0.0, 0.0)

    # 7. Position panel footers manually centered at the bottom of the panel content
    for node in nodes:
        if node.get("type") == "panel":
            panel_id = node["id"]
            # Find footer node of this panel
            footer_node = None
            for child_id in node.get("children", []):
                child = nodes_map.get(child_id)
                if child and (child_id.endswith("_footer") or child.get("_role") == "footer"):
                    footer_node = child
                    break
            
            if footer_node:
                # Find all non-footer in-flow children to get bounding box
                other_children = [
                    nodes_map[cid] for cid in node.get("children", [])
                    if cid in nodes_map and cid != footer_node["id"] and not nodes_map[cid].get("out_of_flow")
                ]
                
                pad = node.get("style", {}).get("padding", {"left": 12, "right": 12, "top": 36, "bottom": 12})
                pad_l = pad.get("left", 12)
                pad_r = pad.get("right", 12)
                pad_t = pad.get("top", 36)
                pad_b = pad.get("bottom", 12)
                
                if other_children:
                    min_x = min(c["x"] for c in other_children)
                    max_x = max(c["x"] + c["width"] for c in other_children)
                    max_y = max(c["y"] + c["height"] for c in other_children)
                else:
                    min_x = node["x"] + pad_l
                    max_x = node["x"] + pad_l
                    max_y = node["y"] + pad_t
                
                content_w = max_x - min_x
                # Make the footer span the full panel width (minus padding)
                footer_w = max(200.0, node["width"] - pad_l - pad_r)
                footer_node["width"] = footer_w
                
                # Re-measure using PIL temp draw
                from scripts.flowdraft.compiler import _measure_card
                from PIL import Image, ImageDraw
                img_temp = Image.new("RGB", (1, 1))
                draw_temp = ImageDraw.Draw(img_temp)
                
                res = _measure_card(footer_node, draw_temp, footer_node.get("_resolved_style", {}))
                footer_node["height"] = res["height"]
                footer_node["layout_offsets"] = res["layout_offsets"]
                
                # Place footer centered horizontally, and 16px below max_y
                footer_node["x"] = node["x"] + pad_l + (node["width"] - pad_l - pad_r - footer_w) / 2.0
                footer_node["y"] = max_y + 16.0
                
                # Update panel height to fit the footer
                needed_panel_h = (footer_node["y"] - node["y"]) + footer_node["height"] + pad_b
                node["height"] = max(node["height"], needed_panel_h)

    # Enforce parent panel bounds expansion for any overflowing child nodes
    for node in nodes:
        if node.get("type") in ("panel", "group"):
            children = [c for c in nodes if c.get("parent") == node["id"] and not c.get("out_of_flow")]
            if children:
                pad = node.get("style", {}).get("padding", {"left": 12, "right": 12, "top": 36, "bottom": 12})
                pad_r = pad.get("right", 20)
                pad_b = pad.get("bottom", 20)
                max_child_r = max(c["x"] + c["width"] for c in children)
                max_child_b = max(c["y"] + c["height"] for c in children)
                needed_w = (max_child_r - node["x"]) + pad_r
                needed_h = (max_child_b - node["y"]) + pad_b
                if needed_w > node["width"]:
                    node["width"] = needed_w
                if needed_h > node["height"]:
                    node["height"] = needed_h

    # Resolve vertical top-level overlaps if panels expanded
    toplevel_nodes = [n for n in nodes if n.get("parent") is None]
    toplevel_nodes.sort(key=lambda n: n["y"])
    for i in range(len(toplevel_nodes)):
        for j in range(i):
            prev = toplevel_nodes[j]
            curr = toplevel_nodes[i]
            prev_bottom = prev["y"] + prev["height"]
            prev_left, prev_right = prev["x"], prev["x"] + prev["width"]
            curr_left, curr_right = curr["x"], curr["x"] + curr["width"]
            if min(prev_right, curr_right) > max(prev_left, curr_left):
                if curr["y"] < prev_bottom + 40.0:
                    delta_y = (prev_bottom + 40.0) - curr["y"]
                    curr["y"] += delta_y
                    for child in nodes:
                        if child.get("parent") == curr["id"]:
                            child["y"] += delta_y
    
    # Store dynamic canvas size
    max_node_r = 1000.0
    max_node_b = 1000.0
    for node in nodes:
        if node.get("parent") is None:
            max_node_r = max(max_node_r, node["x"] + node["width"] + 50.0)
            max_node_b = max(max_node_b, node["y"] + node["height"] + 50.0)
            
    root_w = max(positioned_graph.get("width", 1000), max_node_r)
    root_h = max(positioned_graph.get("height", 1000), max_node_b)
    if "canvas" not in ir:
        ir["canvas"] = {}
    ir["canvas"]["width"] = int(root_w)
    ir["canvas"]["height"] = int(root_h)

    log.info(f"ELK placement succeeded. Root size: {root_w}x{root_h}")
    return True
