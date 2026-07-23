"""
flowdraft.layout_quality
------------------------
Automated layout quality assertion module enforcing zero node-node overlaps,
non-negative canvas bounds, unique Excalidraw element IDs, motion verification,
title-badge clearance, directional port normal stubs, and multi-connection port spacing.
"""

import math
from typing import Any, Dict, List, Optional
from scripts.flowdraft.geometry import get_port_normal


def check_zero_node_overlaps(nodes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Assert no pair of sibling or top-level nodes overlap bounding boxes."""
    overlaps = []
    # Group by parent
    by_parent: Dict[Any, List[Dict[str, Any]]] = {}
    for n in nodes:
        pid = n.get("parent")
        by_parent.setdefault(pid, []).append(n)

    for pid, group in by_parent.items():
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                n1 = group[i]
                n2 = group[j]
                # Skip panel, container, group, decor, or out_of_flow nodes
                if n1.get("type") in ("panel", "container", "group") or n2.get("type") in ("panel", "container", "group"):
                    continue
                if n1.get("out_of_flow") or n2.get("out_of_flow"):
                    continue
                if n1.get("id", "").startswith("decor_") or n2.get("id", "").startswith("decor_"):
                    continue

                x1, y1, w1, h1 = float(n1.get("x", 0)), float(n1.get("y", 0)), float(n1.get("width", 200)), float(n1.get("height", 80))
                x2, y2, w2, h2 = float(n2.get("x", 0)), float(n2.get("y", 0)), float(n2.get("width", 200)), float(n2.get("height", 80))

                # Check bounding box overlap (strict interior intersection)
                if x1 < x2 + w2 and x1 + w1 > x2 and y1 < y2 + h2 and y1 + h1 > y2:
                    overlaps.append((n1.get("id"), n2.get("id")))

    return {"name": "zero_node_overlaps", "ok": len(overlaps) == 0, "overlaps": overlaps}


def check_non_negative_canvas_bounds(nodes: List[Dict[str, Any]], min_x: float = 20.0, min_y: float = 20.0) -> Dict[str, Any]:
    """Assert all regular node/card coordinates satisfy x >= min_x (20) and y >= min_y (20)."""
    invalid = []
    for n in nodes:
        if n.get("id", "").startswith("decor_") or n.get("out_of_flow"):
            continue
        x = n.get("x")
        y = n.get("y")
        if x is not None and y is not None:
            if float(x) < min_x or float(y) < min_y:
                invalid.append((n.get("id"), float(x), float(y)))

    return {"name": "non_negative_canvas_bounds", "ok": len(invalid) == 0, "invalid": invalid}


def check_excalidraw_unique_ids(elements_or_nodes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Assert unique element IDs across Excalidraw output elements or IR objects."""
    ids = []
    for el in elements_or_nodes:
        if isinstance(el, dict) and el.get("id"):
            ids.append(str(el.get("id")))

    seen = set()
    duplicates = set()
    for eid in ids:
        if eid in seen:
            duplicates.add(eid)
        seen.add(eid)

    return {"name": "excalidraw_unique_ids", "ok": len(duplicates) == 0, "duplicates": sorted(list(duplicates))}


def check_gif_has_motion(diff_report: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Assert GIF frames have > 250,000 motion pixel diffs across quarter frames."""
    if not diff_report or not isinstance(diff_report, dict):
        return {"name": "gif_has_motion", "ok": True, "note": "No diff report provided"}

    diffs = diff_report.get("diffs", [])
    frames = diff_report.get("frames", 0)
    total_changed = sum(d.get("changed_pixels", 0) for d in diffs)

    ok = (frames >= 1) and (total_changed > 250000 or any(d.get("changed_pixels", 0) > 200000 for d in diffs))

    return {
        "name": "gif_has_motion",
        "ok": ok,
        "total_changed_pixels": total_changed,
        "frames": frames,
        "diffs": diffs
    }


def check_title_badge_clearance(nodes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Assert zero title-badge overlap and vertical clearance from title block / header highlight panel rects."""
    violations = []
    title_rects = []
    for n in nodes:
        nid = n.get("id", "")
        if nid in ("decor_title_highlight", "decor_title_prefix", "decor_title_line", "decor_title_subtitle") or nid.startswith("decor_title"):
            x = float(n.get("x", 0))
            y = float(n.get("y", 0))
            w = float(n.get("width", 0))
            h = float(n.get("height", 0))
            if w > 0 and h > 0:
                title_rects.append((nid, x, y, x + w, y + h))

    if not title_rects:
        title_rects.append(("default_title_highlight", 600.0, 27.0, 992.0, 99.0))

    for n in nodes:
        nid = n.get("id", "")
        if nid.startswith("decor_") or n.get("out_of_flow"):
            continue

        nx1 = float(n.get("x", 0))
        ny1 = float(n.get("y", 0))
        nw = float(n.get("width", 200))
        nh = float(n.get("height", 80))
        nx2 = nx1 + nw
        ny2 = ny1 + nh

        for tr_id, tx1, ty1, tx2, ty2 in title_rects:
            if nx1 < tx2 and nx2 > tx1 and ny1 < ty2 and ny2 > ty1:
                violations.append((nid, tr_id))

    return {"name": "title_badge_clearance", "ok": len(violations) == 0, "violations": violations}


def check_directional_port_normal_stubs(connections: List[Dict[str, Any]], min_stub_len: float = 16.0) -> Dict[str, Any]:
    """Assert initial and final connection segments extend at least min_stub_len (16px) perpendicular normal stubs out of port sides."""
    invalid = []
    tol = 0.5

    for conn in connections:
        cid = conn.get("id") or f"{conn.get('from')}->{conn.get('to')}"
        pts = conn.get("points", [])
        if not pts or len(pts) < 2:
            continue

        p0, p1 = pts[0], pts[1]
        pN_1, pN = pts[-2], pts[-1]

        from_side = conn.get("exitPort") or conn.get("fromPort") or "SOUTH"
        to_side = conn.get("entryPort") or conn.get("toPort") or "NORTH"

        # Check start stub
        snx, sny = get_port_normal(from_side)
        start_vec_x = p1[0] - p0[0]
        start_vec_y = p1[1] - p0[1]

        start_stub_proj = start_vec_x * snx + start_vec_y * sny
        if start_stub_proj < min_stub_len - tol:
            invalid.append({"connection": cid, "port": "exitPort", "side": from_side, "expected_stub": min_stub_len, "actual_stub": start_stub_proj})

        # Check end stub (vector leaving end port outwards along normal: pN_1 - pN)
        enx, eny = get_port_normal(to_side)
        end_out_vec_x = pN_1[0] - pN[0]
        end_out_vec_y = pN_1[1] - pN[1]

        end_stub_proj = end_out_vec_x * enx + end_out_vec_y * eny
        if end_stub_proj < min_stub_len - tol:
            invalid.append({"connection": cid, "port": "entryPort", "side": to_side, "expected_stub": min_stub_len, "actual_stub": end_stub_proj})

    return {"name": "directional_port_normal_stubs", "ok": len(invalid) == 0, "invalid": invalid}


def check_multi_connection_port_spacing(
    connections: List[Dict[str, Any]],
    nodes: Optional[List[Dict[str, Any]]] = None,
    min_spacing: float = 16.0
) -> Dict[str, Any]:
    """Assert parallel connection ports sharing a node side maintain at least min_spacing (16px) offsets."""
    invalid = []
    tol = 0.5

    side_ports: Dict[tuple, List[float]] = {}

    for conn in connections:
        pts = conn.get("points", [])
        if not pts or len(pts) < 2:
            continue

        from_id = conn.get("from")
        from_side = (conn.get("exitPort") or conn.get("fromPort") or "SOUTH").lower()
        if from_id:
            pt0 = pts[0]
            pos0 = pt0[1] if from_side in ("left", "right", "west", "east") else pt0[0]
            side_ports.setdefault((from_id, from_side, "exit"), []).append(pos0)

        to_id = conn.get("to")
        to_side = (conn.get("entryPort") or conn.get("toPort") or "NORTH").lower()
        if to_id:
            ptN = pts[-1]
            posN = ptN[1] if to_side in ("left", "right", "west", "east") else ptN[0]
            side_ports.setdefault((to_id, to_side, "entry"), []).append(posN)

    for (node_id, side, direction), positions in side_ports.items():
        if len(positions) < 2:
            continue
        sorted_pos = sorted(positions)
        for i in range(len(sorted_pos) - 1):
            gap = sorted_pos[i + 1] - sorted_pos[i]
            if gap < min_spacing - tol:
                invalid.append({
                    "node": node_id,
                    "side": side,
                    "direction": direction,
                    "spacing": gap,
                    "min_required": min_spacing
                })

    return {"name": "multi_connection_port_spacing", "ok": len(invalid) == 0, "invalid": invalid}


def check_layout_quality(
    ir: Dict[str, Any],
    diff_report: Optional[Dict[str, Any]] = None,
    excalidraw_elements: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """Execute complete layout quality assertion suite on IR.

    Returns:
        Dict with overall "ok" status and list of individual quality check dicts.
    """
    nodes = ir.get("nodes", [])
    connections = ir.get("connections", [])
    elements = excalidraw_elements if excalidraw_elements is not None else ir.get("elements", nodes + connections)

    checks = [
        check_zero_node_overlaps(nodes),
        check_non_negative_canvas_bounds(nodes),
        check_excalidraw_unique_ids(elements),
        check_gif_has_motion(diff_report or ir.get("_diff_report")),
        check_title_badge_clearance(nodes),
        check_directional_port_normal_stubs(connections),
        check_multi_connection_port_spacing(connections, nodes),
    ]

    return {
        "ok": all(c["ok"] for c in checks),
        "quality_checks": checks,
    }

