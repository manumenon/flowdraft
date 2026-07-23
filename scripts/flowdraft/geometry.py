"""
flowdraft.geometry
------------------
Path-length calculation, point interpolation, and arrowhead drawing.
"""

import math
from PIL import ImageDraw

from .color import hex_rgba, c
from .constants import THEME


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------
def path_len(points: list) -> float:
    """Return the total Euclidean length of a polyline.

    Args:
        points: List of ``(x, y)`` tuples.

    Returns:
        Total path length in the same units as *points*.
    """
    return sum(math.dist(a, b) for a, b in zip(points, points[1:]))


def point_at_distance(points: list, distance: float) -> tuple:
    """Return the point on a polyline at the given cumulative *distance*.

    If *distance* exceeds the total path length, the last point is returned.

    Args:
        points:   List of ``(x, y)`` tuples.
        distance: Distance along the path from the first point.

    Returns:
        An ``(x, y)`` tuple.
    """
    if not points:
        return (0, 0)
    left = distance
    for a, b in zip(points, points[1:]):
        seg = math.dist(a, b)
        if seg == 0:
            continue
        if left <= seg:
            t = left / seg
            return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
        left -= seg
    return points[-1]


def point_at_fraction(points: list, t: float) -> tuple:
    """Return the point on a polyline at fractional position *t* ∈ [0, 1).

    The fraction wraps modulo 1 so values outside [0, 1) are handled correctly
    for looping animations.
    """
    total = path_len(points)
    if t < 0.0:
        frac = max(0.0, t)
    else:
        frac = t % 1.0
    return point_at_distance(points, frac * total)


# ---------------------------------------------------------------------------
# Arrowhead
# ---------------------------------------------------------------------------
def arrow_head(
    draw: ImageDraw.ImageDraw,
    a: tuple,
    b: tuple,
    stroke: str,
    width: float = 2,
    opacity: float = None,
) -> None:
    """Draw a solid filled triangle arrowhead pointing from *a* toward *b*.

    The arrowhead is 1.5× larger than a typical open arrowhead and has a thin
    background-coloured outline for contrast.

    Args:
        draw:    PIL ImageDraw object.
        a:       Penultimate point (defines arrow direction).
        b:       Tip point of the arrow.
        stroke:  Hex fill colour for the arrowhead.
        width:   Line width (used to scale the arrowhead length).
        opacity: Optional 0-1 float for transparency.
    """
    from . import constants as _c
    SCALE_X = _c.SCALE_X
    SCALE_Y = _c.SCALE_Y

    angle = math.atan2(b[1] - a[1], b[0] - a[0])
    length = 20 * min(SCALE_X, SCALE_Y) + width  # 1.5× vs original 14 px
    spread = 0.48  # tighter spread for a sharper head

    p1 = (
        b[0] - length * math.cos(angle - spread),
        b[1] - length * math.sin(angle - spread),
    )
    p2 = (
        b[0] - length * math.cos(angle + spread),
        b[1] - length * math.sin(angle + spread),
    )
    alpha = int(opacity * 255) if opacity is not None else 255

    # Solid filled triangle
    draw.polygon(
        [(c(p1[0]), c(p1[1])), (c(b[0]), c(b[1])), (c(p2[0]), c(p2[1]))],
        fill=hex_rgba(stroke, alpha),
    )
    # Thin outline in background colour for contrast
    draw.polygon(
        [(c(p1[0]), c(p1[1])), (c(b[0]), c(b[1])), (c(p2[0]), c(p2[1]))],
        outline=hex_rgba(THEME["bg"], min(alpha, 80)),
    )


# ---------------------------------------------------------------------------
# Obstacle-aware A* Orthogonal Polyline Routing
# ---------------------------------------------------------------------------
def route_around_obstacles(
    start: tuple[float, float],
    end: tuple[float, float],
    obstacles: list[dict],
    margin: float = 12.0,
) -> list[tuple[float, float]]:
    """Route an orthogonal polyline between start and end avoiding obstacle bounding boxes.

    Args:
        start:     (x, y) start point.
        end:       (x, y) end point.
        obstacles: List of dicts with keys "x", "y", "width", "height".
        margin:    Clearance margin in px.

    Returns:
        List of (x, y) tuple bend points.
    """
    if not obstacles:
        return [start, end]

    expanded = [
        {
            "minX": obs["x"] - margin,
            "maxX": obs["x"] + obs["width"] + margin,
            "minY": obs["y"] - margin,
            "maxY": obs["y"] + obs["height"] + margin,
        }
        for obs in obstacles
    ]

    def is_segment_colliding(p1, p2):
        seg_min_x, seg_max_x = min(p1[0], p2[0]), max(p1[0], p2[0])
        seg_min_y, seg_max_y = min(p1[1], p2[1]), max(p1[1], p2[1])
        for b in expanded:
            if seg_max_x > b["minX"] and seg_min_x < b["maxX"] and seg_max_y > b["minY"] and seg_min_y < b["maxY"]:
                return True
        return False

    if not is_segment_colliding(start, end):
        return [start, end]

    x_coords = {start[0], end[0]}
    y_coords = {start[1], end[1]}
    for b in expanded:
        x_coords.add(b["minX"])
        x_coords.add(b["maxX"])
        y_coords.add(b["minY"])
        y_coords.add(b["maxY"])

    sorted_x = sorted(x_coords)
    sorted_y = sorted(y_coords)

    def heuristic(p):
        return abs(p[0] - end[0]) + abs(p[1] - end[1])

    import heapq
    open_heap = []
    start_h = heuristic(start)
    heapq.heappush(open_heap, (start_h, 0, start, [start]))
    closed_set = set()

    while open_heap:
        f, g, current, path = heapq.heappop(open_heap)

        if abs(current[0] - end[0]) < 2.0 and abs(current[1] - end[1]) < 2.0:
            final_path = path + [end]
            res = [final_path[0]]
            for i in range(1, len(final_path) - 1):
                prev_p = res[-1]
                curr_p = final_path[i]
                next_p = final_path[i + 1]
                collinear_x = abs(prev_p[0] - curr_p[0]) < 0.1 and abs(curr_p[0] - next_p[0]) < 0.1
                collinear_y = abs(prev_p[1] - curr_p[1]) < 0.1 and abs(curr_p[1] - next_p[1]) < 0.1
                if not collinear_x and not collinear_y:
                    res.append(curr_p)
            res.append(end)
            return res

        curr_key = (round(current[0], 1), round(current[1], 1))
        if curr_key in closed_set:
            continue
        closed_set.add(curr_key)

        neighbors = []
        for x in sorted_x:
            if abs(x - current[0]) > 0.1:
                neighbors.append((x, current[1]))
        for y in sorted_y:
            if abs(y - current[1]) > 0.1:
                neighbors.append((current[0], y))

        for np in neighbors:
            np_key = (round(np[0], 1), round(np[1], 1))
            if np_key in closed_set:
                continue
            if is_segment_colliding(current, np):
                continue

            dist = abs(np[0] - current[0]) + abs(np[1] - current[1])
            new_g = g + dist
            new_f = new_g + heuristic(np)
            heapq.heappush(open_heap, (new_f, new_g, np, path + [np]))

    mid_x = (start[0] + end[0]) / 2.0
    return [start, (mid_x, start[1]), (mid_x, end[1]), end]


# ---------------------------------------------------------------------------
# Smart Perpendicular Connection Label Positioning
# ---------------------------------------------------------------------------
def compute_connection_label_pos(
    points: list[tuple[float, float]],
    ports: list[tuple[float, float]] = None,
    clearance_margin: float = 24.0,
    perp_offset: float = 12.0,
) -> dict:
    """Compute connection label midpoint coordinates with perpendicular port clearance.

    Args:
        points:           List of polyline bend points (x, y).
        ports:            List of port coordinates (x, y) to avoid.
        clearance_margin: Min px distance to trigger perpendicular offset.
        perp_offset:       Px offset distance when near a port.

    Returns:
        Dict with "x", "y", "angle", "offset_x", "offset_y", "segment_index".
    """
    if not points or len(points) < 2:
        return {"x": 0.0, "y": 0.0, "angle": 0.0, "offset_x": 0.0, "offset_y": 0.0, "segment_index": 0}

    ports = ports or []
    longest_idx = 0
    max_len = 0.0

    for i in range(len(points) - 1):
        p1 = points[i]
        p2 = points[i + 1]
        dist = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
        if dist > max_len:
            max_len = dist
            longest_idx = i

    p1 = points[longest_idx]
    p2 = points[longest_idx + 1]
    mid_x = (p1[0] + p2[0]) / 2.0
    mid_y = (p1[1] + p2[1]) / 2.0

    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    is_horizontal = abs(dx) >= abs(dy)

    near_conflict = any(math.hypot(mid_x - port[0], mid_y - port[1]) < clearance_margin for port in ports)

    offset_x = 0.0
    offset_y = 0.0
    if near_conflict:
        if is_horizontal:
            offset_y = -perp_offset
        else:
            offset_x = perp_offset

    angle = 0.0 if is_horizontal else 90.0

    return {
        "x": mid_x + offset_x,
        "y": mid_y + offset_y,
        "angle": angle,
        "offset_x": offset_x,
        "offset_y": offset_y,
        "segment_index": longest_idx,
    }


# ---------------------------------------------------------------------------
# Dynamic Diagram Bounding Box Computation
# ---------------------------------------------------------------------------
def compute_diagram_bounds(nodes: list[dict]) -> dict:
    """Compute overall diagram bounding box enclosing all node positions and extents.

    Args:
        nodes: List of node dicts with 'x', 'y', 'width', 'height'.

    Returns:
        Dict with "min_x", "min_y", "max_x", "max_y", "width", "height", "center_x", "center_y".
    """
    if not nodes:
        return {
            "min_x": 0.0,
            "min_y": 0.0,
            "max_x": 1920.0,
            "max_y": 1080.0,
            "width": 1920.0,
            "height": 1080.0,
            "center_x": 960.0,
            "center_y": 540.0,
        }

    min_x = float("inf")
    min_y = float("inf")
    max_x = float("-inf")
    max_y = float("-inf")

    for n in nodes:
        x = float(n.get("x", 0.0) or 0.0)
        y = float(n.get("y", 0.0) or 0.0)
        w = float(n.get("width", 200.0) or 200.0)
        h = float(n.get("height", 80.0) or 80.0)

        min_x = min(min_x, x)
        min_y = min(min_y, y)
        max_x = max(max_x, x + w)
        max_y = max(max_y, y + h)

    if min_x == float("inf"):
        min_x, min_y, max_x, max_y = 0.0, 0.0, 1920.0, 1080.0

    width = max_x - min_x
    height = max_y - min_y
    center_x = (min_x + max_x) / 2.0
    center_y = (min_y + max_y) / 2.0

    return {
        "min_x": min_x,
        "min_y": min_y,
        "max_x": max_x,
        "max_y": max_y,
        "width": width,
        "height": height,
        "center_x": center_x,
        "center_y": center_y,
    }


# ---------------------------------------------------------------------------
# Directional Port Exit Normal Vector Stubs
# ---------------------------------------------------------------------------
def get_port_normal(side: str) -> tuple[float, float]:
    """Get normal vector for a perimeter port side (NORTH/TOP, SOUTH/BOTTOM, EAST/RIGHT, WEST/LEFT)."""
    s = (side or "SOUTH").upper()
    if s in ("NORTH", "TOP"):
        return (0.0, -1.0)
    elif s in ("SOUTH", "BOTTOM"):
        return (0.0, 1.0)
    elif s in ("EAST", "RIGHT"):
        return (1.0, 0.0)
    elif s in ("WEST", "LEFT"):
        return (-1.0, 0.0)
    return (0.0, 1.0)


def add_directional_stubs(
    start: tuple[float, float],
    end: tuple[float, float],
    start_side: str = "SOUTH",
    end_side: str = "NORTH",
    stub_len: float = 16.0,
) -> list[tuple[float, float]]:
    """Extend start and end points along perimeter port normal vectors.

    Args:
        start:      (x, y) start point.
        end:        (x, y) end point.
        start_side: 'NORTH', 'SOUTH', 'EAST', or 'WEST'.
        end_side:   'NORTH', 'SOUTH', 'EAST', or 'WEST'.
        stub_len:   Extension stub length in px.

    Returns:
        List of 4 points: [start, start_stub, end_stub, end].
    """
    sn = get_port_normal(start_side)
    en = get_port_normal(end_side)

    start_stub = (start[0] + sn[0] * stub_len, start[1] + sn[1] * stub_len)
    end_stub = (end[0] + en[0] * stub_len, end[1] + en[1] * stub_len)

    return [start, start_stub, end_stub, end]


# ---------------------------------------------------------------------------
# Connection Arrow Collinear Path Straightening
# ---------------------------------------------------------------------------
def straighten_connection_path(
    points: list[tuple[float, float]],
    snap_threshold: float = 12.0,
) -> list[tuple[float, float]]:
    """Snap near-collinear connection points into straight lines within threshold.

    Args:
        points:         List of polyline points (x, y).
        snap_threshold: Min px delta to snap to collinear axis.

    Returns:
        List of straightened (x, y) polyline points.
    """
    if not points or len(points) < 2:
        return points or []

    straightened = [list(p) for p in points]
    start = straightened[0]
    end = straightened[-1]

    # Snap horizontal axis
    if abs(start[1] - end[1]) < snap_threshold:
        avg_y = (start[1] + end[1]) / 2.0
        for p in straightened:
            p[1] = avg_y

    # Snap vertical axis
    if abs(start[0] - end[0]) < snap_threshold:
        avg_x = (start[0] + end[0]) / 2.0
        for p in straightened:
            p[0] = avg_x

    # Simplify collinear intermediate points
    res = [(straightened[0][0], straightened[0][1])]
    for i in range(1, len(straightened) - 1):
        prev = res[-1]
        curr = (straightened[i][0], straightened[i][1])
        nxt = (straightened[i + 1][0], straightened[i + 1][1])

        collinear_x = abs(prev[0] - curr[0]) < 0.1 and abs(curr[0] - nxt[0]) < 0.1
        collinear_y = abs(prev[1] - curr[1]) < 0.1 and abs(curr[1] - nxt[1]) < 0.1

        if not collinear_x and not collinear_y:
            res.append(curr)

    res.append((straightened[-1][0], straightened[-1][1]))
    return res
