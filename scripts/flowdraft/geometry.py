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

    Args:
        points: List of ``(x, y)`` tuples.
        t:      Fractional position (0 = start, 1 = end, wraps).

    Returns:
        An ``(x, y)`` tuple.
    """
    total = path_len(points)
    return point_at_distance(points, (t % 1.0) * total)


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
    from .constants import SCALE_X, SCALE_Y

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
