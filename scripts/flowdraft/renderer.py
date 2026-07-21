"""
flowdraft.renderer
------------------
Generic IR renderer — walks the compiled node tree and draws each element
based on its ``type``.  **Zero** ``if node["id"] == "specific_name"`` checks.

Architecture
~~~~~~~~~~~~
The **compiler** is the single source of truth for element sizes and
``layout_offsets``.  This renderer only *reads* from ``layout_offsets`` —
it never computes its own text positions.  Every draw call uses the offset
dicts produced by ``compiler.measure_element()``.

Drawing primitives are imported from the ``flowdraft`` package:
* ``drawing.draw_rect``  / ``draw_ellipse`` / ``draw_diamond`` / ``draw_line``
* ``drawing.icon``       (full icon sprite library)
* ``text.draw_text``     (auto-shrink text rendering)
* ``excal.Excal``        (Excalidraw JSON builder)

All coordinates are **logical pixels** — the drawing functions handle
scaling to physical (hi-DPI) pixels internally.
"""

from __future__ import annotations

import math
from typing import Any, Optional

from PIL import ImageDraw

from .constants import THEME
from .drawing import (
    draw_rect,
    draw_ellipse,
    draw_diamond,
    draw_line,
    icon as draw_icon,
)
from .text import draw_text
from .excal import Excal


# ═══════════════════════════════════════════════════════════════════════════
# Port coordinate helpers
# ═══════════════════════════════════════════════════════════════════════════

_RECT_PORTS: dict[str, Any] = {
    "top":          lambda x, y, w, h: (x + w / 2, y),
    "bottom":       lambda x, y, w, h: (x + w / 2, y + h),
    "left":         lambda x, y, w, h: (x, y + h / 2),
    "right":        lambda x, y, w, h: (x + w, y + h / 2),
    "top-left":     lambda x, y, w, h: (x, y),
    "top-right":    lambda x, y, w, h: (x + w, y),
    "bottom-left":  lambda x, y, w, h: (x, y + h),
    "bottom-right": lambda x, y, w, h: (x + w, y + h),
    "center":       lambda x, y, w, h: (x + w / 2, y + h / 2),
}


def get_port_coords(node: dict, port_name: str) -> tuple[float, float]:
    x: float = node["x"]
    y: float = node["y"]
    w: float = node["width"]
    h: float = node["height"]

    port_fn = _RECT_PORTS.get(port_name)
    if port_fn is not None:
        return port_fn(x, y, w, h)

    return (x + w / 2, y + h / 2)


# ═══════════════════════════════════════════════════════════════════════════
# Style reading helpers
# ═══════════════════════════════════════════════════════════════════════════

def _get_style(node: dict) -> dict:
    return node.get("_resolved_style") or node.get("style") or {}


def _stroke_color(node: dict, default: str | None = None) -> str:
    style = _get_style(node)
    return (
        style.get("strokeColor")
        or node.get("color")
        or default
        or THEME["core_stroke"]
    )


def _fill_color(node: dict, default: str | None = None) -> str | None:
    style = _get_style(node)
    return style.get("fillColor") or default


def _stroke_width(node: dict, default: float = 2) -> float:
    style = _get_style(node)
    return style.get("strokeWidth") or default


def _corner_radius(node: dict, default: float = 12) -> float:
    style = _get_style(node)
    return style.get("cornerRadius") or default


def _stroke_style(node: dict, default: str = "solid") -> str:
    style = _get_style(node)
    return style.get("strokeStyle") or default


def _hand_font(node: dict) -> bool:
    style = _get_style(node)
    val = style.get("hand")
    return val if val is not None else True


def _bold_font(node: dict) -> bool:
    style = _get_style(node)
    val = style.get("bold")
    return val if val is not None else True


# ═══════════════════════════════════════════════════════════════════════════
# Icon drawing
# ═══════════════════════════════════════════════════════════════════════════

def _draw_icon(
    ex: Excal,
    draw: ImageDraw.ImageDraw,
    icon_name: str,
    x: float,
    y: float,
    color: str,
    scale: float = 0.8,
) -> None:
    draw_icon(ex, draw, icon_name, x, y, color, scale, scaled=False)


# ═══════════════════════════════════════════════════════════════════════════
# Decoupled Shape & Content Renderers (Z-Index Layering)
# ═══════════════════════════════════════════════════════════════════════════

# --- CARD ---
def render_card_shape(ex: Excal, draw: ImageDraw.ImageDraw, node: dict) -> None:
    nx, ny = node["x"], node["y"]
    nw, nh = node["width"], node["height"]
    style = _get_style(node)
    borderless = style.get("borderless", False)
    transparent = style.get("transparent", False)

    stroke = None if borderless else _stroke_color(node)
    fill = None if transparent else _fill_color(node, default=THEME["blue_fill"])
    sw = _stroke_width(node, default=2)
    cr = _corner_radius(node, default=12)
    ss = _stroke_style(node)

    if stroke or fill:
        draw_rect(ex, draw, nx, ny, nw, nh, stroke, fill, sw, cr, style=ss, scaled=False)

def render_card_content(ex: Excal, draw: ImageDraw.ImageDraw, node: dict) -> None:
    nx, ny = node["x"], node["y"]
    offsets = node.get("layout_offsets", {})
    style = _get_style(node)
    borderless = style.get("borderless", False)
    stroke = None if borderless else _stroke_color(node)

    # 1. Icon
    icon_opt = offsets.get("icon")
    icon_name = node.get("icon")
    if icon_opt and icon_opt.get("draw") and icon_name:
        icon_scale = icon_opt.get("scale", 0.8)
        _draw_icon(ex, draw, icon_name, nx + icon_opt["x"], ny + icon_opt["y"], stroke, icon_scale)

    # 2. Title
    title_opt = offsets.get("title")
    title_text = node.get("title", "")
    if title_opt and title_text:
        draw_text(
            ex, draw, title_text,
            nx + title_opt["x"], ny + title_opt["y"],
            title_opt["w"], title_opt["h"],
            title_opt.get("size", 18),
            THEME["white"],
            title_opt.get("align", "center"),
            hand=title_opt.get("hand", _hand_font(node)),
            bold=title_opt.get("bold", _bold_font(node)),
            fit=True,
            min_size=title_opt.get("min_size", 12),
            scaled=False,
        )

    # 3. Body
    body_opt = offsets.get("body")
    body_text = node.get("body", "")
    if body_opt and body_text:
        draw_text(
            ex, draw, body_text,
            nx + body_opt["x"], ny + body_opt["y"],
            body_opt["w"], body_opt["h"],
            body_opt.get("size", 14),
            THEME["white"],
            body_opt.get("align", "center"),
            hand=body_opt.get("hand", _hand_font(node)),
            bold=body_opt.get("bold", False),
            spacing=3,
            fit=True,
            min_size=body_opt.get("min_size", 11),
            scaled=False,
        )

def render_card(ex: Excal, draw: ImageDraw.ImageDraw, node: dict) -> None:
    render_card_shape(ex, draw, node)
    render_card_content(ex, draw, node)


# --- DIAMOND ---
def render_diamond_shape(ex: Excal, draw: ImageDraw.ImageDraw, node: dict) -> None:
    nx, ny = node["x"], node["y"]
    nw, nh = node["width"], node["height"]
    stroke = _stroke_color(node, default=THEME["green"])
    fill = _fill_color(node, default="#052515")
    sw = _stroke_width(node, default=2)
    draw_diamond(ex, draw, nx, ny, nw, nh, stroke, fill, sw, scaled=False)

def render_diamond_content(ex: Excal, draw: ImageDraw.ImageDraw, node: dict) -> None:
    nx, ny = node["x"], node["y"]
    offsets = node.get("layout_offsets", {})

    title_opt = offsets.get("title")
    title_text = node.get("title", "")
    if title_opt and title_text:
        draw_text(
            ex, draw, title_text,
            nx + title_opt["x"], ny + title_opt["y"],
            title_opt["w"], title_opt["h"],
            title_opt.get("size", 18),
            THEME["white"],
            title_opt.get("align", "center"),
            hand=title_opt.get("hand", _hand_font(node)),
            bold=title_opt.get("bold", True),
            fit=True,
            min_size=title_opt.get("min_size", 12),
            scaled=False,
        )

    body_opt = offsets.get("body")
    body_text = node.get("body", "")
    if body_opt and body_text:
        draw_text(
            ex, draw, body_text,
            nx + body_opt["x"], ny + body_opt["y"],
            body_opt["w"], body_opt["h"],
            body_opt.get("size", 13),
            THEME["white"],
            body_opt.get("align", "center"),
            hand=body_opt.get("hand", _hand_font(node)),
            bold=body_opt.get("bold", False),
            fit=True,
            min_size=body_opt.get("min_size", 10),
            scaled=False,
        )

def render_diamond(ex: Excal, draw: ImageDraw.ImageDraw, node: dict) -> None:
    render_diamond_shape(ex, draw, node)
    render_diamond_content(ex, draw, node)


# --- PANEL ---
def render_panel_shape(ex: Excal, draw: ImageDraw.ImageDraw, node: dict, nodes_map: dict[str, dict]) -> None:
    nx, ny = node["x"], node["y"]
    nw, nh = node["width"], node["height"]
    style = _get_style(node)
    borderless = style.get("borderless", False)
    transparent = style.get("transparent", False)

    stroke = None if borderless else _stroke_color(node, default=THEME["frame"])
    fill = None if transparent else _fill_color(node, default=None)
    sw = _stroke_width(node, default=2)
    cr = _corner_radius(node, default=20)
    ss = _stroke_style(node)

    if stroke or fill:
        draw_rect(ex, draw, nx, ny, nw, nh, stroke, fill, sw, cr, style=ss, scaled=False)

    for child_id in node.get("children", []):
        child = nodes_map.get(child_id)
        if child is not None:
            render_node_shape(ex, draw, child, nodes_map)

def render_panel_content(ex: Excal, draw: ImageDraw.ImageDraw, node: dict, nodes_map: dict[str, dict]) -> None:
    nx, ny = node["x"], node["y"]
    nw, nh = node["width"], node["height"]
    offsets = node.get("layout_offsets", {})

    title_opt = offsets.get("title")
    title_text = node.get("title", "")
    if title_opt and title_text:
        draw_text(
            ex, draw, title_text,
            nx + title_opt["x"], ny + title_opt["y"],
            title_opt["w"], title_opt["h"],
            title_opt.get("size", 22),
            THEME["white"],
            title_opt.get("align", "left"),
            hand=title_opt.get("hand", _hand_font(node)),
            bold=title_opt.get("bold", True),
            fit=True,
            min_size=title_opt.get("min_size", 12),
            scaled=False,
        )

    sub_opt = offsets.get("subtitle")
    subtitle_text = node.get("subtitle", "")
    if sub_opt and subtitle_text:
        draw_text(
            ex, draw, subtitle_text,
            nx + sub_opt["x"], ny + sub_opt["y"],
            sub_opt["w"], sub_opt["h"],
            sub_opt.get("size", 14),
            THEME["muted"],
            sub_opt.get("align", "left"),
            hand=sub_opt.get("hand", _hand_font(node)),
            bold=sub_opt.get("bold", False),
            fit=True,
            min_size=sub_opt.get("min_size", 10),
            scaled=False,
        )

    badge_opt = offsets.get("badge")
    badge_text = node.get("badge", "")
    if badge_opt and badge_text:
        badge_w = badge_opt["w"]
        badge_h = badge_opt["h"]
        if badge_opt.get("x_anchor") == "right":
            badge_x = nx + nw - badge_w - 15
        else:
            badge_x = nx + badge_opt.get("x", nw - badge_w - 15)
        badge_y = ny + badge_opt["y"]

        draw_rect(
            ex, draw,
            badge_x, badge_y, badge_w, badge_h,
            THEME["green"], "#082b1b",
            1, 6,
            scaled=False,
        )
        draw_text(
            ex, draw, badge_text.upper(),
            badge_x, badge_y + 4,
            badge_w, badge_h - 6,
            badge_opt.get("size", 9),
            THEME["green"],
            "center",
            bold=True,
            scaled=False,
        )

    for child_id in node.get("children", []):
        child = nodes_map.get(child_id)
        if child is not None:
            render_node_content(ex, draw, child, nodes_map)

def render_panel(ex: Excal, draw: ImageDraw.ImageDraw, node: dict, nodes_map: dict[str, dict]) -> None:
    render_panel_shape(ex, draw, node, nodes_map)
    render_panel_content(ex, draw, node, nodes_map)


# --- INPUT ---
def render_input_shape(ex: Excal, draw: ImageDraw.ImageDraw, node: dict) -> None:
    nx, ny = node["x"], node["y"]
    nw, nh = node["width"], node["height"]
    stroke = _stroke_color(node, default=THEME["cyan"])
    sw = _stroke_width(node, default=2)
    cr = _corner_radius(node, default=8)
    draw_rect(ex, draw, nx, ny, nw, nh, stroke, "#061826", sw, cr, scaled=False)

def render_input_content(ex: Excal, draw: ImageDraw.ImageDraw, node: dict) -> None:
    nx, ny = node["x"], node["y"]
    nw = node["width"]
    offsets = node.get("layout_offsets", {})
    stroke = _stroke_color(node, default=THEME["cyan"])
    icon_name = node.get("icon") or "file"

    icon_opt = offsets.get("icon")
    if icon_opt and icon_opt.get("draw"):
        icon_scale = icon_opt.get("scale", 0.5)
        _draw_icon(ex, draw, icon_name, nx + icon_opt["x"], ny + icon_opt["y"], stroke, icon_scale)
    else:
        cx = nx + nw / 2
        _draw_icon(ex, draw, icon_name, cx - 16, ny + 1, stroke, 0.65)

    title_opt = offsets.get("title")
    title_text = node.get("label", "") or node.get("title", "")
    if title_opt and title_text:
        draw_text(
            ex, draw, title_text,
            nx + title_opt["x"], ny + title_opt["y"],
            title_opt["w"], title_opt["h"],
            title_opt.get("size", 13),
            THEME["white"],
            title_opt.get("align", "center"),
            hand=title_opt.get("hand", _hand_font(node)),
            bold=title_opt.get("bold", False),
            fit=True,
            min_size=title_opt.get("min_size", 9),
            scaled=False,
        )

def render_input(ex: Excal, draw: ImageDraw.ImageDraw, node: dict) -> None:
    render_input_shape(ex, draw, node)
    render_input_content(ex, draw, node)


# --- LABEL ---
def render_label(ex: Excal, draw: ImageDraw.ImageDraw, node: dict) -> None:
    nx, ny = node["x"], node["y"]
    offsets = node.get("layout_offsets", {})
    color = _stroke_color(node, default=THEME["white"])
    align = node.get("align", "center")

    title_opt = offsets.get("title")
    title_text = node.get("title", "") or node.get("text", "")
    if title_opt and title_text:
        draw_text(
            ex, draw, title_text,
            nx + title_opt["x"], ny + title_opt["y"],
            title_opt["w"], title_opt["h"],
            title_opt.get("size", 14),
            color,
            title_opt.get("align", align),
            hand=title_opt.get("hand", _hand_font(node)),
            bold=title_opt.get("bold", _bold_font(node)),
            fit=True,
            min_size=title_opt.get("min_size", 9),
            scaled=False,
        )

# --- DECOR BRAND ---
def render_decor_brand_shape(ex: Excal, draw: ImageDraw.ImageDraw, node: dict) -> None:
    bx, by = node["x"], node["y"]
    dots = [
        (0,  0,  THEME["cyan"]),
        (10, 8,  THEME["white"]),
        (0,  16, THEME["purple"]),
        (10, 24, THEME["white"]),
        (20, 0,  THEME["white"]),
        (30, 8,  THEME["pink"]),
        (20, 16, THEME["white"]),
        (30, 24, THEME["green"]),
    ]
    for dx, dy, color in dots:
        draw_ellipse(ex, draw, bx + dx, by + dy, 5, 5, color, color, 1, scaled=False)

def render_decor_brand_content(ex: Excal, draw: ImageDraw.ImageDraw, node: dict) -> None:
    bx, by = node["x"], node["y"]
    signature = node.get("signature", "@FlowDraft")
    from .drawing import draw_signature
    draw_signature(ex, draw, signature, bx + 43, by - 8)

def render_decor_brand(ex: Excal, draw: ImageDraw.ImageDraw, node: dict) -> None:
    render_decor_brand_shape(ex, draw, node)
    render_decor_brand_content(ex, draw, node)


# ═══════════════════════════════════════════════════════════════════════════
# Node Dispatchers (Shape vs Content)
# ═══════════════════════════════════════════════════════════════════════════

_SHAPE_RENDERERS = {
    "card":        render_card_shape,
    "diamond":     render_diamond_shape,
    "input":       render_input_shape,
    "decor_brand": render_decor_brand_shape,
}

_CONTENT_RENDERERS = {
    "card":        render_card_content,
    "diamond":     render_diamond_content,
    "input":       render_input_content,
    "label":       render_label,
    "text":        render_label,
    "decor_brand": render_decor_brand_content,
}

def render_node_shape(ex: Excal, draw: ImageDraw.ImageDraw, node: dict, nodes_map: dict[str, dict]) -> None:
    ntype = node.get("type", "card")
    if ntype == "panel":
        render_panel_shape(ex, draw, node, nodes_map)
        return
    renderer = _SHAPE_RENDERERS.get(ntype)
    if renderer:
        renderer(ex, draw, node)

def render_node_content(ex: Excal, draw: ImageDraw.ImageDraw, node: dict, nodes_map: dict[str, dict]) -> None:
    ntype = node.get("type", "card")
    if ntype == "panel":
        render_panel_content(ex, draw, node, nodes_map)
        return
    renderer = _CONTENT_RENDERERS.get(ntype)
    if renderer:
        renderer(ex, draw, node)

def render_node(ex: Excal, draw: ImageDraw.ImageDraw, node: dict, nodes_map: dict[str, dict]) -> None:
    render_node_shape(ex, draw, node, nodes_map)
    render_node_content(ex, draw, node, nodes_map)


# ═══════════════════════════════════════════════════════════════════════════
# Connection rendering
# ═══════════════════════════════════════════════════════════════════════════

def render_connection(
    ex: Excal,
    draw: ImageDraw.ImageDraw,
    conn: dict,
    nodes_map: dict[str, dict],
) -> None:
    path_points = [tuple(p) for p in conn.get("points", [])]
    if not path_points:
        return

    conn_style = conn.get("style", "solid")
    conn_color = conn.get("color") or THEME["core_stroke"]
    stroke = THEME["muted"] if conn_style == "dashed" else conn_color
    conn_width = conn.get("width", 2)

    draw_line(
        ex, draw, path_points,
        stroke, conn_width, conn_style,
        arrow=True, scaled=False,
    )

    conn_label = conn.get("label")
    if conn_label:
        lbl_opt = conn.get("layout_offsets", {}).get("label")
        if lbl_opt and "x" in lbl_opt and "y" in lbl_opt:
            lbl_x = lbl_opt["x"]
            lbl_y = lbl_opt["y"]
        elif len(path_points) >= 2:
            mid_idx = len(path_points) // 2
            p1 = path_points[mid_idx - 1]
            p2 = path_points[mid_idx]
            lbl_x = (p1[0] + p2[0]) / 2.0
            lbl_y = (p1[1] + p2[1]) / 2.0
        else:
            lbl_x, lbl_y = path_points[0]

        draw_rect(
            ex, draw,
            lbl_x - 40, lbl_y - 12,
            80, 24,
            THEME["bg"], THEME["bg"],
            0, 6,
            scaled=False,
        )
        draw_text(
            ex, draw, conn_label,
            lbl_x - 50, lbl_y - 10,
            100, 20, 12,
            THEME["white"], "center",
            scaled=False,
        )


# ═══════════════════════════════════════════════════════════════════════════
# Annotation rendering
# ═══════════════════════════════════════════════════════════════════════════

def render_annotation(
    ex: Excal,
    draw: ImageDraw.ImageDraw,
    ann: dict,
    nodes_map: dict[str, dict],
) -> None:
    text = ann.get("text", "")
    if not text:
        return

    ax: float | None = ann.get("x")
    ay: float | None = ann.get("y")

    if ax is None or ay is None:
        return

    aw = ann.get("w", 200)
    ah = ann.get("h", 24)
    a_size = ann.get("size", 14)
    a_color = ann.get("color", THEME["white"])
    a_align = ann.get("align", "center")

    from .fonts import load_font, text_size
    from .compiler import _scratch_draw
    from .constants import SCALE

    font_val = load_font(a_size, hand=False, bold=False)
    draw_scratch = _scratch_draw()
    txt_pw, txt_ph = text_size(draw_scratch, text, font_val)
    txt_w = txt_pw / SCALE
    txt_h = txt_ph / SCALE

    mask_w = min(aw, txt_w + 16.0)
    mask_h = min(ah, txt_h + 8.0)

    draw_rect(
        ex, draw,
        ax - mask_w / 2, ay - mask_h / 2,
        mask_w, mask_h,
        THEME["bg"], THEME["bg"],
        0, 0,
        scaled=False,
    )

    draw_text(
        ex, draw, text,
        ax - aw / 2, ay - ah / 2,
        aw, ah, a_size,
        a_color, a_align,
        fit=True,
        min_size=9,
        scaled=False,
    )


# ═══════════════════════════════════════════════════════════════════════════
# Main entry point — 4-Pass Decoupled Z-Index Rendering Pipeline
# ═══════════════════════════════════════════════════════════════════════════

def render_all(
    ex: Excal,
    draw: ImageDraw.ImageDraw,
    ir: dict,
) -> None:
    """Render the entire compiled IR using a 4-pass decoupled z-index pipeline:

    Pass 1: Top-level panel containers & backgrounds
    Pass 2: Free element node shape backgrounds (Z_bg)
    Pass 3: Connections, arrowheads, and polylines (Z_edges)
    Pass 4: Element node content (icons, titles, body copy) & annotations (Z_labels > Z_edges)
    """
    nodes = ir.get("nodes", [])
    connections = ir.get("connections", [])
    annotations = ir.get("annotations", [])

    nodes_map: dict[str, dict] = {n["id"]: n for n in nodes}

    # Pass 1: Top-level panel container shapes
    for node in nodes:
        if node.get("type") == "panel" and not node.get("parent"):
            render_panel_shape(ex, draw, node, nodes_map)

    # Pass 2: Free element node shape backgrounds
    for node in nodes:
        if not node.get("parent") and node.get("type") not in ("panel",):
            render_node_shape(ex, draw, node, nodes_map)

    # Pass 3: Connections & arrowheads (Z_edges)
    for conn in connections:
        render_connection(ex, draw, conn, nodes_map)

    # Pass 4: Node contents (icons, title text, body text) on top of connections
    for node in nodes:
        if node.get("type") == "panel" and not node.get("parent"):
            render_panel_content(ex, draw, node, nodes_map)

    for node in nodes:
        if not node.get("parent") and node.get("type") not in ("panel",):
            render_node_content(ex, draw, node, nodes_map)

    # Pass 5: Floating annotations
    for ann in annotations:
        render_annotation(ex, draw, ann, nodes_map)
