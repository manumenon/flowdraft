"""
flowdraft.drawing
-----------------
Primitive drawing functions that write to both the PIL raster canvas and the
Excalidraw JSON model simultaneously.

Each function accepts an ``Excal`` instance (*ex*) and a PIL ``ImageDraw``
(*draw*).  Coordinates are given in logical pixels and scaled internally
unless ``scaled=True`` is passed (meaning the caller already did the scaling).
"""

from PIL import ImageDraw

from .constants import THEME, SCALE_X, SCALE_Y
from .color import hex_rgba, c, scaled_box, adjust_color
from .fonts import has_cjk, load_font
from .geometry import path_len, point_at_distance, arrow_head


# ---------------------------------------------------------------------------
# Rectangles, ellipses, lines, diamonds
# ---------------------------------------------------------------------------
def draw_rect(
    ex,
    draw: ImageDraw.ImageDraw,
    x: float, y: float, w: float, h: float,
    stroke: str,
    fill: str = None,
    width: float = 2,
    radius: float = 10,
    style: str = "solid",
    scaled: bool = False,
    opacity: float = None,
) -> None:
    """Draw a rounded rectangle on the PIL canvas and add it to the Excal model.

    Args:
        ex:      Excal JSON builder.
        draw:    PIL ImageDraw.
        x, y:   Top-left corner (logical px, or physical if *scaled*).
        w, h:   Dimensions (logical px, or physical if *scaled*).
        stroke:  Stroke colour hex string.
        fill:    Fill colour hex string (None = no fill).
        width:   Border width.
        radius:  Corner radius.
        style:   "solid" | "dashed" | "dotted".
        scaled:  Coordinates are already scaled to physical pixels.
        opacity: 0-1 transparency.
    """
    from .constants import SCALE_X, SCALE_Y
    if not scaled:
        x = x * SCALE_X
        y = y * SCALE_Y
        w = w * SCALE_X
        h = h * SCALE_Y
        width = width * min(SCALE_X, SCALE_Y)
        radius = radius * min(SCALE_X, SCALE_Y)
    stroke = adjust_color(stroke)
    fill = adjust_color(fill)
    ex.rect(x, y, w, h, stroke, fill or "transparent", width, style, radius=radius, opacity=opacity)
    alpha = int(opacity * 255) if opacity is not None else 255
    draw.rounded_rectangle(
        scaled_box(x, y, w, h),
        radius=c(radius),
        outline=hex_rgba(stroke, alpha),
        fill=hex_rgba(fill, alpha) if fill else None,
        width=max(1, c(width)),
    )


def draw_ellipse(
    ex,
    draw: ImageDraw.ImageDraw,
    x: float, y: float, w: float, h: float,
    stroke: str,
    fill: str = None,
    width: float = 2,
    scaled: bool = False,
    opacity: float = None,
) -> None:
    """Draw an ellipse on the PIL canvas and add it to the Excal model."""
    from .constants import SCALE_X, SCALE_Y
    if not scaled:
        x = x * SCALE_X
        y = y * SCALE_Y
        w = w * SCALE_X
        h = h * SCALE_Y
        width = width * min(SCALE_X, SCALE_Y)
    stroke = adjust_color(stroke)
    fill = adjust_color(fill)
    ex.ellipse(x, y, w, h, stroke, fill or "transparent", width, opacity=opacity)
    alpha = int(opacity * 255) if opacity is not None else 255
    draw.ellipse(
        scaled_box(x, y, w, h),
        outline=hex_rgba(stroke, alpha),
        fill=hex_rgba(fill, alpha) if fill else None,
        width=max(1, c(width)),
    )


def draw_line(
    ex,
    draw: ImageDraw.ImageDraw,
    points: list,
    stroke: str,
    width: float = 2,
    style: str = "solid",
    arrow: bool = False,
    scaled: bool = False,
    opacity: float = None,
    fill: str = None,
) -> None:
    """Draw a polyline (or dashed/dotted line) on PIL and in the Excal model.

    Supports solid, dashed, and dotted styles.  If *arrow* is True, an
    arrowhead is drawn at the last point.  Closed polygons (when *fill* is
    provided) are filled.

    Args:
        ex:      Excal JSON builder.
        draw:    PIL ImageDraw.
        points:  List of ``(x, y)`` tuples.
        stroke:  Stroke colour.
        width:   Line width.
        style:   "solid" | "dashed" | "dotted".
        arrow:   Draw arrowhead at the final point.
        scaled:  Coordinates already in physical pixels.
        opacity: 0-1 transparency.
        fill:    Fill colour for closed paths.
    """
    from .constants import SCALE_X, SCALE_Y
    if not scaled:
        points = [(px * SCALE_X, py * SCALE_Y) for px, py in points]
        width = width * min(SCALE_X, SCALE_Y)
    stroke = adjust_color(stroke)
    fill = adjust_color(fill)
    ex.line(points, stroke, width, style, arrow, fill=fill, opacity=opacity)

    # Shorten the last segment of the line for PIL drawing to prevent the line cap from poking through the arrowhead tip
    line_points = list(points)
    if arrow and len(points) >= 2:
        import math
        a, b = points[-2], points[-1]
        dx, dy = b[0] - a[0], b[1] - a[1]
        dist = math.hypot(dx, dy)
        if dist > 0:
            shorten_len = 10 * min(SCALE_X, SCALE_Y)
            if dist > shorten_len:
                line_points[-1] = (b[0] - (dx / dist) * shorten_len, b[1] - (dy / dist) * shorten_len)

    scaled_pts = [(c(px), c(py)) for px, py in line_points]
    alpha = int(opacity * 255) if opacity is not None else 255

    if fill:
        draw.polygon(scaled_pts, fill=hex_rgba(fill, alpha))

    if style == "solid":
        draw.line(scaled_pts, fill=hex_rgba(stroke, alpha), width=max(1, c(width)), joint="curve")
    else:
        total = path_len(line_points)
        dist = 0.0
        dash = 8 * min(SCALE_X, SCALE_Y) if style == "dashed" else 2 * min(SCALE_X, SCALE_Y)
        gap  = 8 * min(SCALE_X, SCALE_Y) if style == "dashed" else 7 * min(SCALE_X, SCALE_Y)
        while dist < total:
            start = point_at_distance(line_points, dist)
            end   = point_at_distance(line_points, min(total, dist + dash))
            draw.line(
                [(c(start[0]), c(start[1])), (c(end[0]), c(end[1]))],
                fill=hex_rgba(stroke, alpha),
                width=max(1, c(width)),
            )
            dist += dash + gap

    if arrow and len(points) >= 2:
        arrow_head(draw, points[-2], points[-1], stroke, width, opacity=opacity)


def draw_diamond(
    ex,
    draw: ImageDraw.ImageDraw,
    x: float, y: float, w: float, h: float,
    stroke: str,
    fill: str = None,
    width: float = 2,
    scaled: bool = False,
    opacity: float = None,
) -> None:
    """Draw a diamond (rotated square) on PIL and in the Excal model."""
    from .constants import SCALE_X, SCALE_Y
    if not scaled:
        x = x * SCALE_X
        y = y * SCALE_Y
        w = w * SCALE_X
        h = h * SCALE_Y
        width = width * min(SCALE_X, SCALE_Y)
    stroke = adjust_color(stroke)
    fill = adjust_color(fill)
    ex.diamond(x, y, w, h, stroke, fill or "transparent", width, opacity=opacity)
    pts = [(x + w / 2, y), (x + w, y + h / 2), (x + w / 2, y + h), (x, y + h / 2)]
    scaled_pts = [(c(px), c(py)) for px, py in pts]
    alpha = int(opacity * 255) if opacity is not None else 255
    draw.polygon(scaled_pts, outline=hex_rgba(stroke, alpha), fill=hex_rgba(fill, alpha) if fill else None)
    draw.line(scaled_pts + [scaled_pts[0]], fill=hex_rgba(stroke, alpha), width=max(1, c(width)))


# ---------------------------------------------------------------------------
# Icon sprite library
# ---------------------------------------------------------------------------
def icon(ex, draw: ImageDraw.ImageDraw, kind: str, x: float, y: float, color: str = None, scale: float = 1.0, scaled: bool = False) -> None:
    """Draw one of the built-in icon sprites.

    Icons are composed of primitive calls (``draw_line``, ``draw_rect``, etc.)
    so they appear in both the raster output and the Excalidraw JSON.

    Supported kinds: ``folder``, ``file``, ``scan``, ``shield``, ``db``,
    ``hash``, ``package``, and a default dot for unknown kinds.

    Args:
        ex:     Excal JSON builder.
        draw:   PIL ImageDraw.
        kind:   Icon name string.
        x, y:   Top-left anchor in logical (or physical if *scaled*) pixels.
        color:  Primary fill/stroke colour; defaults to ``THEME["cyan"]``.
        scale:  Uniform scale factor applied to all icon coordinates.
        scaled: Coordinates are already in physical pixels.
    """
    from .constants import SCALE_X, SCALE_Y
    if not scaled:
        x = x * SCALE_X
        y = y * SCALE_Y
        scale = scale * min(SCALE_X, SCALE_Y)
    color = adjust_color(color or THEME["cyan"])

    if kind == "folder":
        draw_line(ex, draw, [
            (x, y + 9 * scale), (x, y + 35 * scale),
            (x + 48 * scale, y + 35 * scale), (x + 48 * scale, y + 7 * scale),
            (x + 26 * scale, y + 7 * scale), (x + 21 * scale, y),
            (x + 2 * scale, y), (x + 2 * scale, y + 9 * scale),
        ], THEME["white"], 2, scaled=True)
        draw_rect(ex, draw, x + 5 * scale, y + 15 * scale, 38 * scale, 15 * scale, color, color, 1, 3, scaled=True)

    elif kind == "file":
        draw_rect(ex, draw, x + 7 * scale, y, 33 * scale, 36 * scale, THEME["white"], color, 2, 4, scaled=True)
        draw_line(ex, draw, [(x + 15 * scale, y + 14 * scale), (x + 31 * scale, y + 14 * scale)], THEME["bg"], 2, scaled=True)
        draw_line(ex, draw, [(x + 15 * scale, y + 24 * scale), (x + 31 * scale, y + 24 * scale)], THEME["bg"], 2, scaled=True)

    elif kind == "scan":
        draw_ellipse(ex, draw, x + 14 * scale, y + 11 * scale, 38 * scale, 38 * scale, THEME["white"], None, 4, scaled=True)
        draw_line(ex, draw, [(x + 47 * scale, y + 45 * scale), (x + 64 * scale, y + 62 * scale)], THEME["white"], 5, scaled=True)

    elif kind == "shield":
        pts = [
            (x + 38 * scale, y + 7 * scale),
            (x + 63 * scale, y + 17 * scale),
            (x + 58 * scale, y + 47 * scale),
            (x + 38 * scale, y + 65 * scale),
            (x + 18 * scale, y + 47 * scale),
            (x + 13 * scale, y + 17 * scale),
        ]
        draw_line(ex, draw, pts + [pts[0]], THEME["white"], fill=THEME["green"], width=3, scaled=True, opacity=180 / 255.0)
        draw_line(ex, draw, [
            (x + 27 * scale, y + 37 * scale),
            (x + 36 * scale, y + 48 * scale),
            (x + 51 * scale, y + 27 * scale),
        ], THEME["white"], 4, scaled=True)

    elif kind == "db":
        draw_ellipse(ex, draw, x + 15 * scale, y + 9 * scale,  50 * scale, 17 * scale, THEME["white"], color, 2, scaled=True)
        draw_rect(  ex, draw, x + 15 * scale, y + 17 * scale, 50 * scale, 37 * scale, THEME["white"], color, 2, 0, scaled=True)
        draw_ellipse(ex, draw, x + 15 * scale, y + 45 * scale, 50 * scale, 17 * scale, THEME["white"], color, 2, scaled=True)

    elif kind == "hash":
        draw_line(ex, draw, [(x + 27 * scale, y + 14 * scale), (x + 22 * scale, y + 58 * scale)], THEME["amber"], 4, scaled=True)
        draw_line(ex, draw, [(x + 50 * scale, y + 14 * scale), (x + 45 * scale, y + 58 * scale)], THEME["amber"], 4, scaled=True)
        draw_line(ex, draw, [(x + 15 * scale, y + 29 * scale), (x + 62 * scale, y + 29 * scale)], THEME["white"], 4, scaled=True)
        draw_line(ex, draw, [(x + 13 * scale, y + 45 * scale), (x + 60 * scale, y + 45 * scale)], THEME["white"], 4, scaled=True)

    elif kind == "package":
        draw_line(ex, draw, [
            (x + 38 * scale, y + 8  * scale),
            (x + 66 * scale, y + 23 * scale),
            (x + 66 * scale, y + 52 * scale),
            (x + 38 * scale, y + 68 * scale),
            (x + 10 * scale, y + 52 * scale),
            (x + 10 * scale, y + 23 * scale),
            (x + 38 * scale, y + 8  * scale),
        ], THEME["white"], 3, scaled=True)
        draw_line(ex, draw, [
            (x + 10 * scale, y + 23 * scale),
            (x + 38 * scale, y + 38 * scale),
            (x + 66 * scale, y + 23 * scale),
        ], THEME["amber"], 3, scaled=True)
        draw_line(ex, draw, [(x + 38 * scale, y + 38 * scale), (x + 38 * scale, y + 68 * scale)], THEME["amber"], 3, scaled=True)

    elif kind == "activity":
        # Waveform / heartbeat line
        pts = [
            (x + 4  * scale, y + 36 * scale),
            (x + 18 * scale, y + 36 * scale),
            (x + 26 * scale, y + 14 * scale),
            (x + 35 * scale, y + 57 * scale),
            (x + 43 * scale, y + 22 * scale),
            (x + 51 * scale, y + 36 * scale),
            (x + 68 * scale, y + 36 * scale),
        ]
        draw_line(ex, draw, pts, color, 3, scaled=True)

    elif kind == "lock":
        draw_rect(ex, draw, x + 12 * scale, y + 28 * scale, 44 * scale, 34 * scale,
                  THEME["white"], color, 2, 4, scaled=True)
        draw_line(ex, draw, [
            (x + 18 * scale, y + 28 * scale),
            (x + 18 * scale, y + 13 * scale),
            (x + 50 * scale, y + 13 * scale),
            (x + 50 * scale, y + 28 * scale),
        ], THEME["white"], 3, scaled=True)
        draw_ellipse(ex, draw, x + 29 * scale, y + 37 * scale, 10 * scale, 10 * scale,
                     THEME["bg"], THEME["bg"], 1, scaled=True)

    elif kind == "layers":
        for idx, dy in enumerate([0, 14, 28]):
            margin = idx * 6
            draw_rect(ex, draw,
                      x + (6 + margin) * scale, y + dy * scale,
                      (56 - margin * 2) * scale, 10 * scale,
                      THEME["white"], color, 1.5, 3, scaled=True)

    elif kind == "git-commit":
        draw_line(ex, draw,
                  [(x + 4 * scale, y + 36 * scale), (x + 24 * scale, y + 36 * scale)],
                  THEME["white"], 3, scaled=True)
        draw_ellipse(ex, draw, x + 21 * scale, y + 24 * scale, 26 * scale, 24 * scale,
                     THEME["white"], color, 3, scaled=True)
        draw_line(ex, draw,
                  [(x + 47 * scale, y + 36 * scale), (x + 68 * scale, y + 36 * scale)],
                  THEME["white"], 3, scaled=True)

    elif kind == "database":
        draw_ellipse(ex, draw, x + 15 * scale, y +  9 * scale, 50 * scale, 17 * scale,
                     THEME["white"], color, 2, scaled=True)
        draw_rect(  ex, draw, x + 15 * scale, y + 17 * scale, 50 * scale, 37 * scale,
                     THEME["white"], color, 2, 0, scaled=True)
        draw_ellipse(ex, draw, x + 15 * scale, y + 45 * scale, 50 * scale, 17 * scale,
                     THEME["white"], color, 2, scaled=True)

    elif kind == "cpu":
        draw_rect(ex, draw, x + 17 * scale, y + 17 * scale, 34 * scale, 34 * scale,
                  THEME["white"], color, 2, 3, scaled=True)
        for i in range(3):
            dy = (22 + i * 10) * scale
            draw_line(ex, draw,
                      [(x + 7 * scale, y + dy), (x + 17 * scale, y + dy)],
                      THEME["white"], 2, scaled=True)
            draw_line(ex, draw,
                      [(x + 51 * scale, y + dy), (x + 61 * scale, y + dy)],
                      THEME["white"], 2, scaled=True)

    elif kind == "git-branch":
        draw_ellipse(ex, draw, x + 10 * scale, y +  8 * scale, 14 * scale, 14 * scale,
                     THEME["white"], color, 2, scaled=True)
        draw_ellipse(ex, draw, x + 10 * scale, y + 44 * scale, 14 * scale, 14 * scale,
                     THEME["white"], color, 2, scaled=True)
        draw_ellipse(ex, draw, x + 44 * scale, y +  8 * scale, 14 * scale, 14 * scale,
                     THEME["white"], color, 2, scaled=True)
        draw_line(ex, draw,
                  [(x + 17 * scale, y + 22 * scale), (x + 17 * scale, y + 44 * scale)],
                  THEME["white"], 3, scaled=True)
        draw_line(ex, draw,
                  [(x + 17 * scale, y + 15 * scale), (x + 44 * scale, y + 15 * scale)],
                  THEME["white"], 3, scaled=True)

    elif kind == "users":
        for ox in (0, 22):
            draw_ellipse(ex, draw, x + (8 + ox) * scale, y + 5 * scale,
                         18 * scale, 18 * scale, THEME["white"], color, 2, scaled=True)
            draw_line(ex, draw, [
                (x + (5 + ox) * scale, y + 28 * scale),
                (x + (5 + ox) * scale, y + 50 * scale),
                (x + (27 + ox) * scale, y + 50 * scale),
                (x + (27 + ox) * scale, y + 28 * scale),
            ], THEME["white"], 2, scaled=True)

    elif kind == "share-2":
        for dot_x, dot_y in [(14, 36), (52, 8), (52, 64)]:
            draw_ellipse(ex, draw,
                         x + dot_x * scale - 7 * scale, y + dot_y * scale - 7 * scale,
                         14 * scale, 14 * scale, THEME["white"], color, 2, scaled=True)
        draw_line(ex, draw,
                  [(x + 21 * scale, y + 36 * scale), (x + 45 * scale, y + 15 * scale)],
                  THEME["white"], 2, scaled=True)
        draw_line(ex, draw,
                  [(x + 21 * scale, y + 36 * scale), (x + 45 * scale, y + 57 * scale)],
                  THEME["white"], 2, scaled=True)

    elif kind == "zap":
        # Lightning bolt
        pts = [
            (x + 38 * scale, y + 5 * scale),
            (x + 18 * scale, y + 37 * scale),
            (x + 34 * scale, y + 37 * scale),
            (x + 30 * scale, y + 67 * scale),
            (x + 50 * scale, y + 31 * scale),
            (x + 34 * scale, y + 31 * scale),
        ]
        draw_line(ex, draw, pts + [pts[0]], color, 2, scaled=True, fill=color)

    elif kind == "code":
        # < > brackets
        draw_line(ex, draw, [(x + 22 * scale, y + 18 * scale), (x + 8 * scale, y + 34 * scale), (x + 22 * scale, y + 50 * scale)], THEME["white"], 3, scaled=True)
        draw_line(ex, draw, [(x + 46 * scale, y + 18 * scale), (x + 60 * scale, y + 34 * scale), (x + 46 * scale, y + 50 * scale)], THEME["white"], 3, scaled=True)
        draw_line(ex, draw, [(x + 38 * scale, y + 12 * scale), (x + 30 * scale, y + 56 * scale)], color, 3, scaled=True)

    elif kind == "terminal":
        # >_ console
        draw_rect(ex, draw, x + 8 * scale, y + 8 * scale, 52 * scale, 52 * scale, THEME["white"], color, 2, 4, scaled=True)
        draw_line(ex, draw, [(x + 18 * scale, y + 22 * scale), (x + 28 * scale, y + 30 * scale), (x + 18 * scale, y + 38 * scale)], THEME["white"], 3, scaled=True)
        draw_line(ex, draw, [(x + 34 * scale, y + 38 * scale), (x + 48 * scale, y + 38 * scale)], THEME["white"], 3, scaled=True)

    elif kind == "archive":
        # Box with lid
        draw_rect(ex, draw, x + 10 * scale, y + 24 * scale, 48 * scale, 38 * scale, THEME["white"], color, 2, 2, scaled=True)
        draw_rect(ex, draw, x + 6 * scale, y + 10 * scale, 56 * scale, 14 * scale, THEME["white"], THEME["white"], 2, 1, scaled=True)
        draw_line(ex, draw, [(x + 26 * scale, y + 36 * scale), (x + 42 * scale, y + 36 * scale)], THEME["white"], 3, scaled=True)

    elif kind == "disc":
        # Concentric rings
        draw_ellipse(ex, draw, x + 8 * scale, y + 8 * scale, 52 * scale, 52 * scale, THEME["white"], color, 2, scaled=True)
        draw_ellipse(ex, draw, x + 24 * scale, y + 24 * scale, 20 * scale, 20 * scale, THEME["white"], THEME["white"], 2, scaled=True)

    elif kind == "sliders":
        # Sliders tracks + knobs
        for i in range(3):
            dy = (18 + i * 16) * scale
            draw_line(ex, draw, [(x + 10 * scale, y + dy), (x + 58 * scale, y + dy)], THEME["white"], 2, scaled=True)
            knob_x = (20 + i * 14) * scale
            draw_rect(ex, draw, x + knob_x, y + dy - 6 * scale, 10 * scale, 12 * scale, THEME["white"], color, 1.5, 2, scaled=True)

    elif kind == "box":
        # Box frame
        pts = [
            (x + 34 * scale, y + 8 * scale),
            (x + 60 * scale, y + 22 * scale),
            (x + 60 * scale, y + 50 * scale),
            (x + 34 * scale, y + 64 * scale),
            (x + 8 * scale, y + 50 * scale),
            (x + 8 * scale, y + 22 * scale),
        ]
        draw_line(ex, draw, pts + [pts[0]], THEME["white"], 2, scaled=True)
        draw_line(ex, draw, [(x + 8 * scale, y + 22 * scale), (x + 34 * scale, y + 36 * scale), (x + 60 * scale, y + 22 * scale)], THEME["white"], 2, scaled=True)
        draw_line(ex, draw, [(x + 34 * scale, y + 36 * scale), (x + 34 * scale, y + 64 * scale)], THEME["white"], 2, scaled=True)

    elif kind == "user-check":
        # Person + Checkmark
        draw_ellipse(ex, draw, x + 18 * scale, y + 10 * scale, 24 * scale, 24 * scale, THEME["white"], color, 2, scaled=True)
        draw_line(ex, draw, [
            (x + 8 * scale, y + 54 * scale),
            (x + 8 * scale, y + 44 * scale),
            (x + 18 * scale, y + 38 * scale),
            (x + 42 * scale, y + 38 * scale),
            (x + 52 * scale, y + 44 * scale),
            (x + 52 * scale, y + 54 * scale),
        ], THEME["white"], 2, scaled=True)
        draw_line(ex, draw, [
            (x + 46 * scale, y + 22 * scale),
            (x + 51 * scale, y + 28 * scale),
            (x + 62 * scale, y + 14 * scale),
        ], THEME["green"], 3, scaled=True)

    else:
        # Default: filled circle (unknown icon kind)
        draw_ellipse(ex, draw, x + 18 * scale, y + 18 * scale, 36 * scale, 36 * scale, color, color, 2, scaled=True)


# ---------------------------------------------------------------------------
# Signature watermark
# ---------------------------------------------------------------------------
def draw_signature(ex, draw: ImageDraw.ImageDraw, text: str, x: float, y: float) -> None:
    """Draw the brand signature with a chromatic-aberration shadow effect.

    Args:
        ex:   Excal JSON builder.
        draw: PIL ImageDraw.
        text: Signature string (e.g. "@FlowDraft").
        x, y: Position in physical pixels.
    """
    from .constants import SCALE_X, SCALE_Y
    from .text import draw_text

    sw = 120 * SCALE_X
    sh = 36 * SCALE_Y
    s_size = 24 * min(SCALE_X, SCALE_Y)

    # Three-pass chromatic aberration: purple shadow, cyan shadow, white text
    for dx, dy, color, alpha in [
        (-1, 1, THEME["purple"], 165),
        (1, -1, THEME["cyan"],   135),
        (0, 0, THEME["white"],   245),
    ]:
        draw_text(
            ex, draw, text,
            x + dx * SCALE_X, y + dy * SCALE_Y,
            sw, sh, s_size, color,
            align="left", bold=True, scaled=True, opacity=alpha / 255.0,
        )

    # Clean underline (replaces the old squiggle)
    draw_line(ex, draw, [
        (x + 4  * SCALE_X, y + 44 * SCALE_Y),
        (x + 90 * SCALE_X, y + 44 * SCALE_Y),
    ], THEME["frame"], width=1, scaled=True, opacity=100 / 255.0)
