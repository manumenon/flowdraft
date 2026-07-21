"""
Graphviz-based orthogonal edge router.

Uses Graphviz neato with fixed node positions and splines=ortho
to compute collision-free orthogonal edge paths.  Falls back to
the legacy A* router when Graphviz is not installed.
"""
from __future__ import annotations

import logging
import math
import os
import re
import shutil
import subprocess
import tempfile

log = logging.getLogger(__name__)

# Graphviz uses 72 DPI (1 inch = 72 points).
# neato -n reads pos= values in *points* (not inches).
_DPI = 72.0


def _find_graphviz() -> str | None:
    """Return path to the `neato` binary, or None."""
    common_paths = [
        r"C:\tools\Graphviz\Graphviz-12.2.1-win64\bin",
        r"C:\Program Files\Graphviz\bin",
        r"C:\Program Files (x86)\Graphviz\bin",
        r"C:\tools\Graphviz\bin",
    ]
    for p in common_paths:
        neato = os.path.join(p, "neato.exe")
        if os.path.isfile(neato):
            return neato
    # fallback: check PATH
    found = shutil.which("neato")
    if found:
        return found
    # also try dot
    for p in common_paths:
        dot = os.path.join(p, "dot.exe")
        if os.path.isfile(dot):
            return dot
    return shutil.which("dot")


def _add_obstacle_box(lines: list[str], obs_id: str, x: float, y: float, w: float, h: float, canvas_h: float, buffer: float = 12.0):
    # Expand obstacle by clearance buffer so lines clear rounded corners & card edges
    x_buf = x - buffer / 2.0
    y_buf = y - buffer / 2.0
    w_buf = w + buffer
    h_buf = h + buffer

    # Center position in Graphviz points, Y-flipped
    cx = x_buf + w_buf / 2.0
    cy = canvas_h - (y_buf + h_buf / 2.0)

    w_in = w_buf / _DPI
    h_in = h_buf / _DPI

    lines.append(
        f'  "{obs_id}" ['
        f'pos="{cx:.1f},{cy:.1f}!", '
        f'width={w_in:.4f}, height={h_in:.4f}, '
        f'shape=box'
        f'];'
    )


def _build_dot(
    nodes: list[dict],
    connections: list[dict],
    canvas_w: float,
    canvas_h: float,
) -> str:
    """
    Build a Graphviz DOT string with fixed node positions.

    Our coordinate system: origin top-left, Y increases downward.
    Graphviz coordinate system: origin bottom-left, Y increases upward.
    We convert by flipping Y: gv_y = canvas_h - our_y
    """
    lines = [
        'digraph G {',
        '  graph [splines=ortho, overlap=false];',
        '  node [shape=box, fixedsize=true];',
        '',
    ]

    nodes_map = {n["id"]: n for n in nodes}

    for n in nodes:
        nid = n["id"]
        if nid.startswith("decor_"):
            continue
        x = n.get("x", 0)
        y = n.get("y", 0)
        w = n.get("width", 100)
        h = n.get("height", 50)
        ntype = n.get("type", "card")

        # For panels, add their boundary margins as solid obstacles so edges don't route through them
        if ntype == "panel":
            px = n.get("x", 0)
            py = n.get("y", 0)
            pw = n.get("width", 100)
            ph = n.get("height", 50)
            
            style = n.get("_resolved_style", {})
            padding = style.get("padding", {"left": 20, "right": 20, "top": 40, "bottom": 20})
            pad_l = padding.get("left", 20)
            pad_r = padding.get("right", 20)
            pad_t = padding.get("top", 40)
            pad_b = padding.get("bottom", 20)
            
            direction = n.get("layout", {}).get("direction", "row")
            
            if direction == "column":
                # Add left and right boundary strips
                _add_obstacle_box(lines, f"{nid}_margin_l", px, py, pad_l, ph, canvas_h)
                _add_obstacle_box(lines, f"{nid}_margin_r", px + pw - pad_r, py, pad_r, ph, canvas_h)
            else:
                # Add top and bottom boundary strips
                _add_obstacle_box(lines, f"{nid}_margin_t", px, py, pw, pad_t, canvas_h)
                _add_obstacle_box(lines, f"{nid}_margin_b", px, py + ph - pad_b, pw, pad_b, canvas_h)
            continue

        # Expand obstacle bounds to fill panel margins if nested, to prevent routing through panels
        parent_id = n.get("parent")
        parent_panel = nodes_map.get(parent_id) if parent_id else None
        if parent_panel and parent_panel.get("type") == "panel":
            direction = parent_panel.get("layout", {}).get("direction", "row")
            px = parent_panel.get("x", 0)
            py = parent_panel.get("y", 0)
            pw = parent_panel.get("width", 100)
            ph = parent_panel.get("height", 50)
            
            # Slightly inset to avoid boundary precision issues
            inset = 2.0
            if direction == "column":
                x = px + inset
                w = pw - 2 * inset
            else:
                y = py + inset
                h = ph - 2 * inset

        # Center position in Graphviz points, Y-flipped
        cx = x + w / 2.0
        cy = canvas_h - (y + h / 2.0)

        # Size in inches (Graphviz width/height are in inches)
        w_in = w / _DPI
        h_in = h / _DPI

        shape = "box"
        if ntype == "diamond":
            shape = "diamond"
        elif ntype in ("ellipse", "circle"):
            shape = "ellipse"

        # Use pos="x,y!" to fix position (in points for neato -n)
        lines.append(
            f'  "{nid}" ['
            f'pos="{cx:.1f},{cy:.1f}!", '
            f'width={w_in:.4f}, height={h_in:.4f}, '
            f'shape={shape}'
            f'];'
        )

    lines.append('')

    # Emit edges (skip panel-to-panel connections)
    for conn in connections:
        src = conn.get("from", "")
        tgt = conn.get("to", "")
        if src not in nodes_map or tgt not in nodes_map:
            continue
        if nodes_map[src].get("type") == "panel" or nodes_map[tgt].get("type") == "panel":
            continue
        lines.append(f'  "{src}" -> "{tgt}";')

    lines.append('}')
    return '\n'.join(lines)


def _parse_edge_pos(pos_str: str, canvas_h: float) -> list[tuple[float, float]]:
    """
    Parse a Graphviz edge pos string into a list of (x, y) waypoints.

    Format: "e,ex,ey sx,sy cx1,cy1 cx2,cy2 ex,ey ..." or
            "sx,sy cx1,cy1 ... ex,ey"

    For ortho splines, the control points are axis-aligned segments.
    Graphviz uses cubic B-splines where groups of 4 points define a curve.
    For orthogonal routing, the curves are degenerate (straight lines).
    """
    # Remove endpoint marker
    pos_str = pos_str.strip().strip('"')

    # Extract endpoint hints (e, and s,)
    endpoint = None
    startpoint = None
    parts = pos_str.split()
    cleaned = []
    for part in parts:
        if part.startswith("e,"):
            coords = part[2:].split(",")
            endpoint = (float(coords[0]), canvas_h - float(coords[1]))
        elif part.startswith("s,"):
            coords = part[2:].split(",")
            startpoint = (float(coords[0]), canvas_h - float(coords[1]))
        else:
            cleaned.append(part)

    # Parse the spline control points
    points = []
    for part in cleaned:
        coords = part.split(",")
        if len(coords) == 2:
            x = float(coords[0])
            y = canvas_h - float(coords[1])
            points.append((x, y))

    # For ortho splines, every 4 points is a cubic Bezier segment (3n+1 points total).
    # Extract actual waypoints based on length format and deduplicate near-identical points.
    if len(points) >= 4:
        if (len(points) - 1) % 3 == 0:
            waypoints = [points[0]]
            for i in range(3, len(points), 3):
                waypoints.append(points[i])
        else:
            waypoints = list(points)
        if waypoints[-1] != points[-1]:
            waypoints.append(points[-1])
        points = waypoints

    # Deduplicate consecutive points
    dedup = []
    for pt in points:
        if not dedup or (abs(pt[0] - dedup[-1][0]) > 0.1 or abs(pt[1] - dedup[-1][1]) > 0.1):
            dedup.append(pt)
    points = dedup

    # Use endpoint/startpoint if available
    if startpoint and points:
        points[0] = startpoint
    if endpoint and points:
        points[-1] = endpoint

    return points


def _parse_dot_output(
    dot_output: str,
    canvas_h: float,
) -> dict[tuple[str, str], list[tuple[float, float]]]:
    """
    Parse Graphviz DOT output and extract edge waypoints from pos attributes.
    """
    edges: dict[tuple[str, str], list[tuple[float, float]]] = {}

    # Join line continuations (backslash followed by newline)
    joined = dot_output.replace('\\\n', '').replace('\\\r\n', '')

    # Match edge definitions with pos attributes
    # Handles both quoted ("src") and unquoted (src) node names
    # and multiline pos values
    edge_pattern = re.compile(
        r'(?:"([^"]+)"|(\w+))\s*->\s*(?:"([^"]+)"|(\w+))\s*\[.*?pos="([^"]+)"',
        re.DOTALL,
    )

    for match in edge_pattern.finditer(joined):
        src = match.group(1) or match.group(2)
        tgt = match.group(3) or match.group(4)
        pos_str = match.group(5)

        points = _parse_edge_pos(pos_str, canvas_h)
        if points and len(points) >= 2:
            edges[(src, tgt)] = points

    return edges


def _simplify_ortho_points(
    points: list[tuple[float, float]],
) -> list[tuple[float, float]]:
    """
    Simplify a polyline by snapping near-axis-aligned segments
    and removing collinear intermediate points.
    """
    if len(points) <= 2:
        return points

    # Snap near-axis-aligned segments (within 3px tolerance)
    snapped = [points[0]]
    for i in range(1, len(points)):
        px, py = points[i]
        prev_x, prev_y = snapped[-1]
        if abs(px - prev_x) < 3.0:
            px = prev_x
        if abs(py - prev_y) < 3.0:
            py = prev_y
        snapped.append((px, py))

    # Remove collinear points
    if len(snapped) <= 2:
        return snapped

    result = [snapped[0]]
    for i in range(1, len(snapped) - 1):
        p_prev = result[-1]
        p_curr = snapped[i]
        p_next = snapped[i + 1]

        same_x = abs(p_prev[0] - p_curr[0]) < 1.0 and abs(p_curr[0] - p_next[0]) < 1.0
        same_y = abs(p_prev[1] - p_curr[1]) < 1.0 and abs(p_curr[1] - p_next[1]) < 1.0
        if not (same_x or same_y):
            result.append(p_curr)
    result.append(snapped[-1])

    return result


def route_edges_graphviz(
    nodes: list[dict],
    connections: list[dict],
    canvas_w: float,
    canvas_h: float,
) -> dict[tuple[str, str], list[tuple[float, float]]] | None:
    """
    Route all edges using Graphviz neato with orthogonal splines.

    Returns a dict mapping (from_id, to_id) -> [(x, y), ...] waypoints,
    or None if Graphviz is not available.
    """
    engine = _find_graphviz()
    if not engine:
        log.warning("Graphviz not found; falling back to A* router")
        return None

    dot_src = _build_dot(nodes, connections, canvas_w, canvas_h)

    try:
        # Run neato -n (preserve positions, only route edges)
        # Output as DOT format so we can parse edge pos= attributes
        result = subprocess.run(
            [engine, '-n', '-Tdot'],
            input=dot_src,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            log.warning("Graphviz failed (rc=%d): %s", result.returncode, result.stderr[:500])
            return None

        if "falling back to straight line" in result.stderr:
            log.info("Graphviz ortho fallback detected, will use hybrid routing")

        edges = _parse_dot_output(result.stdout, canvas_h)

        # Simplify the points
        simplified = {}
        for key, pts in edges.items():
            simplified[key] = _simplify_ortho_points(pts)

        if simplified:
            log.info("Graphviz routed %d edges successfully", len(simplified))
        return simplified

    except FileNotFoundError:
        log.warning("Graphviz binary not found at %s", engine)
        return None
    except subprocess.TimeoutExpired:
        log.warning("Graphviz timed out")
        return None
    except Exception as e:
        log.warning("Graphviz routing failed: %s", e)
        return None
