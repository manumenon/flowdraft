"""
flowdraft.compiler
------------------
Transforms a v2 spec JSON into an Intermediate Representation (IR) — a flat
list of nodes with computed sizes and ``layout_offsets``.

The compiler is the **single source of truth** for element dimensions and
content positioning.  The renderer only reads from ``layout_offsets``; it
never computes its own offsets.

Public API
~~~~~~~~~~
- ``compile_spec(spec)``       — main entry point, returns the full IR dict
- ``measure_element(el, draw)`` — compute size + layout_offsets for one element
- ``resolve_style(el, parent)`` — cascade defaults → theme → parent → element

Design rules
~~~~~~~~~~~~
1. Zero ``if node["id"] == "specific_name"`` checks — only type-based dispatch.
2. Content-driven sizing: all element dimensions derive from text measurement.
3. Every computed position is stored in ``layout_offsets`` so the renderer can
   do a simple read-and-draw without any size arithmetic.
"""

from __future__ import annotations

import copy
from typing import Any, Optional

from PIL import Image, ImageDraw

from .constants import THEME, SCALE
from .fonts import load_font, text_size
from .text import fit_text


# ---------------------------------------------------------------------------
# Default style tables — keyed by element type
# ---------------------------------------------------------------------------

_DEFAULT_PADDING: dict[str, dict[str, float]] = {
    "card":    {"left": 12, "right": 12, "top": 8,   "bottom": 8},
    "diamond": {"left": 0,  "right": 0,  "top": 0,   "bottom": 0},
    "panel":   {"left": 12, "right": 12, "top": 36,  "bottom": 12},
    "input":   {"left": 6,  "right": 6,  "top": 6,  "bottom": 6},
    "label":   {"left": 4,  "right": 4,  "top": 2,  "bottom": 2},
}

_DEFAULT_STYLE: dict[str, dict[str, Any]] = {
    "card": {
        "fillColor": None,
        "strokeColor": None,
        "strokeWidth": 2,
        "strokeStyle": "solid",
        "cornerRadius": 12,
        "bold": True,
        "hand": True,
    },
    "diamond": {
        "fillColor": None,
        "strokeColor": None,
        "strokeWidth": 3,
        "strokeStyle": "solid",
        "cornerRadius": 0,
        "bold": True,
        "hand": True,
    },
    "panel": {
        "fillColor": None,
        "strokeColor": None,
        "strokeWidth": 2,
        "strokeStyle": "solid",
        "cornerRadius": 20,
        "bold": False,
        "hand": True,
    },
    "input": {
        "fillColor": None,
        "strokeColor": None,
        "strokeWidth": 2.5,
        "strokeStyle": "solid",
        "cornerRadius": 8,
        "bold": False,
        "hand": True,
    },
    "label": {
        "fillColor": None,
        "strokeColor": None,
        "strokeWidth": 0,
        "strokeStyle": "solid",
        "cornerRadius": 0,
        "bold": False,
        "hand": True,
    },
}

_MIN_SIZES: dict[str, tuple[float, float]] = {
    "card":    (200, 80),
    "diamond": (140, 140),
    "input":   (110, 50),
    "panel":   (100, 100),   # panels are resized from children later
    "label":   (40,  20),
}

# Icon dimensions in logical pixels (pre-scale)
_ICON_W = 32
_ICON_H = 32
_ICON_SCALE = 0.4          # draw-time icon scale multiplier
_ICON_TITLE_GAP = 8        # horizontal gap between icon and title


# ═══════════════════════════════════════════════════════════════════════════
# Style resolution
# ═══════════════════════════════════════════════════════════════════════════

def resolve_style(
    element: dict,
    parent_style: Optional[dict] = None,
    *,
    theme: Optional[dict] = None,
) -> dict:
    """Cascade style properties: defaults → theme preset → parent → element.

    The cascade order (later wins):
    1. Built-in defaults for the element's ``type``.
    2. ``color_preset`` look-up in the active THEME.
    3. Inherited ``parent_style`` (for children inside panels).
    4. Explicit ``element["style"]`` overrides.

    Args:
        element:      The element dict (must contain at least ``type``).
        parent_style: Resolved style dict of the parent element, if any.
        theme:        Theme dict override; defaults to the global ``THEME``.

    Returns:
        A fully resolved style dict with keys: ``fillColor``, ``strokeColor``,
        ``strokeWidth``, ``strokeStyle``, ``cornerRadius``, ``bold``, ``hand``,
        ``padding``, and ``color_preset``.
    """
    th = theme or THEME
    etype = element.get("type", "card")

    # 1. Start with built-in defaults
    style = copy.deepcopy(_DEFAULT_STYLE.get(etype, _DEFAULT_STYLE["card"]))
    style["padding"] = copy.deepcopy(
        _DEFAULT_PADDING.get(etype, _DEFAULT_PADDING["card"])
    )
    from . import constants as _c
    style["hand"] = getattr(_c, "HAND", True)

    # Track what is explicitly overridden in the element
    elem_style = element.get("style", {})
    elem_padding = elem_style.get("padding") or element.get("padding")
    elem_preset = element.get("color_preset") or elem_style.get("color_preset")
    elem_color = element.get("color")

    # Determine if child specifies any color overrides
    has_elem_color = (
        elem_preset is not None
        or elem_color is not None
        or "fillColor" in elem_style
        or "strokeColor" in elem_style
    )

    # 2. Inherit styles from parent_style if parent_style exists
    if parent_style:
        # Inherit simple properties if not explicitly overridden by child
        for key in ("hand", "bold", "strokeWidth", "strokeStyle", "cornerRadius"):
            if key in parent_style and key not in elem_style:
                style[key] = parent_style[key]

        # Inherit padding from parent if the parent explicitly set it.
        # Do NOT inherit if the parent's padding is just its type default
        # (e.g. panel default top:36 should not leak to child cards).
        if elem_padding is None and "padding" in parent_style:
            parent_padding_was_explicit = parent_style.get("_padding_explicit", False)
            if parent_padding_was_explicit:
                style["padding"] = copy.deepcopy(parent_style["padding"])

        # Inherit color preset if not explicitly overridden by child
        if not has_elem_color and "color_preset" in parent_style:
            style["color_preset"] = parent_style["color_preset"]
            if parent_style["color_preset"]:
                _apply_color_preset(style, parent_style["color_preset"].lower(), th)

        # If parent has resolved colors and we didn't inherit/override them:
        if not has_elem_color and not style.get("color_preset"):
            if "fillColor" in parent_style:
                style["fillColor"] = parent_style["fillColor"]
            if "strokeColor" in parent_style:
                style["strokeColor"] = parent_style["strokeColor"]

    # 3. Apply element's own color_preset
    if elem_preset:
        style["color_preset"] = elem_preset
        _apply_color_preset(style, elem_preset.lower(), th)

    # Fallback: use element-level "color" for strokeColor
    if not style.get("strokeColor") and elem_color:
        style["strokeColor"] = elem_color

    # 4. Apply element-level style overrides
    for key in (
        "fillColor", "strokeColor", "strokeWidth", "strokeStyle",
        "cornerRadius", "bold", "hand", "borderless", "transparent",
    ):
        if key in elem_style:
            style[key] = elem_style[key]

    # Padding merge (element overrides per-side)
    if elem_padding is not None:
        if isinstance(elem_padding, dict):
            for side in ("left", "right", "top", "bottom"):
                if side in elem_padding:
                    style["padding"][side] = elem_padding[side]
        elif isinstance(elem_padding, (int, float)):
            for side in ("left", "right", "top", "bottom"):
                style["padding"][side] = elem_padding
        style["_padding_explicit"] = True
    else:
        style["_padding_explicit"] = style.get("_padding_explicit", False)

    # Ensure color_preset is stored in resolved style dict
    if "color_preset" not in style:
        style["color_preset"] = elem_preset or (parent_style.get("color_preset") if parent_style else None)

    # Store element type for padding inheritance decisions
    style["_element_type"] = etype

    # Validate hex colours
    for ckey in ("fillColor", "strokeColor"):
        if style.get(ckey) and not _is_valid_hex(style[ckey]):
            style[ckey] = None

    # Remap custom dark hex colors if theme is light or white
    theme_name = th.get("name", "dark")
    if theme_name in ("light", "white"):
        if style.get("fillColor"):
            style["fillColor"] = adjust_color(style["fillColor"], theme_name)
        if style.get("strokeColor"):
            style["strokeColor"] = adjust_color(style["strokeColor"], theme_name)

    return style


_COLOR_MAPPINGS: dict[str, str] = {
    '#000000': '#ffffff',
    '#f4f0ee': '#111827',
    '#cfc7c5': '#4b5563',
    '#5c6265': '#6b7280',
    '#04171e': '#dbeafe',
    '#1d8be8': '#0284c7',
    '#22c86f': '#15803d',
    '#02160a': '#dcfce7',
    '#bd54d3': '#7c3aed',
    '#120814': '#ede9fe',
    '#7ee3d6': '#0891b2',
    '#081626': '#dbeafe',
    '#124238': '#99f6e4',
    '#f4b64e': '#b45309',
    '#ff7ab6': '#be185d',
    '#080711': '#ede9fe',
    '#04180d': '#d1fae5',
    '#04200f': '#dcfce7',
    '#17091d': '#ede9fe',
    '#052515': '#dcfce7',
}


def adjust_color(color: str | None, theme_name: str = "dark") -> str | None:
    if not color or not isinstance(color, str):
        return color
    if theme_name in ("light", "white"):
        color_lower = color.lower()
        return _COLOR_MAPPINGS.get(color_lower, color)
    return color


def _apply_color_preset(style: dict, preset: str, th: dict) -> None:
    """Resolve a named colour preset into fill / stroke colours."""
    if preset == "core":
        style.setdefault("strokeColor", th.get("core_stroke"))
        style.setdefault("fillColor", th.get("core_fill"))
        return
    if preset == "blue":
        style.setdefault("strokeColor", th.get("cyan"))
        style.setdefault("fillColor", th.get("blue_fill"))
        return
    if preset in th:
        if not style.get("strokeColor"):
            style["strokeColor"] = th[preset]
        fill_key = f"{preset}_fill"
        if not style.get("fillColor"):
            if fill_key in th:
                style["fillColor"] = th[fill_key]
            elif preset == "cyan":
                style["fillColor"] = th.get("blue_fill")
            else:
                style["fillColor"] = th.get("bg")


def _is_valid_hex(val: Any) -> bool:
    """Return True if *val* looks like ``#RRGGBB``."""
    if not val or not isinstance(val, str):
        return False
    v = val.lstrip("#")
    return len(v) == 6 and all(c in "0123456789abcdefABCDEF" for c in v)


# ═══════════════════════════════════════════════════════════════════════════
# Content measurement helpers
# ═══════════════════════════════════════════════════════════════════════════

def _measure_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    max_w: float,
    max_h: float,
    start_size: float,
    min_size: float = 10,
    *,
    hand: bool = False,
    bold: bool = False,
) -> tuple[str, float, float, float]:
    """Measure text via ``fit_text`` and return logical (unscaled) dimensions.

    Args:
        draw:       PIL draw surface for measurement.
        text:       The string to measure.
        max_w:      Maximum logical width for wrapping.
        max_h:      Maximum logical height.
        start_size: Starting font size (logical px).
        min_size:   Minimum font size.
        hand:       Use handwritten font.
        bold:       Use bold font.

    Returns:
        ``(fitted_text, fitted_size, logical_w, logical_h)``
    """
    if not text:
        return ("", start_size, 0.0, 0.0)

    fitted_text, fitted_size, fitted_font = fit_text(
        draw, str(text), max_w, max_h, start_size,
        min_size=min_size, hand=hand, bold=bold,
        wrap=True, allow_grow=True,
    )
    tw, th = text_size(draw, fitted_text, fitted_font)
    # text_size returns physical pixels → convert to logical
    return (fitted_text, fitted_size, tw / SCALE, th / SCALE)


# ═══════════════════════════════════════════════════════════════════════════
# Per-type measurers
# ═══════════════════════════════════════════════════════════════════════════

def _measure_card(
    element: dict,
    draw: ImageDraw.ImageDraw,
    style: dict,
) -> dict:
    """Compute width, height, and layout_offsets for a ``card`` element.

    Layout structure::

        ┌─────────────────────────────────────┐
        │ pad_top                              │
        │ ┌──────┐  gap  ┌──────────────────┐ │
        │ │ ICON │       │     TITLE        │ │
        │ └──────┘       └──────────────────┘ │
        │          content_gap                 │
        │ ┌───────────────────────────────────┐│
        │ │           BODY                    ││
        │ └───────────────────────────────────┘│
        │ pad_bottom                           │
        └─────────────────────────────────────┘
    """
    pad = style["padding"]
    pad_l: float = pad["left"]
    pad_r: float = pad["right"]
    pad_t: float = pad["top"]
    pad_b: float = pad["bottom"]

    has_icon = bool(element.get("icon"))
    title = element.get("title", "")
    body = element.get("body", "")

    min_w, min_h = _MIN_SIZES["card"]
    base_w = max(element.get("width", 0) or 0, min_w)
    base_h = max(element.get("height", 0) or 0, min_h)

    # ── Icon region ──────────────────────────────────────────────────
    icon_x = pad_l
    icon_y = pad_t
    icon_w = _ICON_W
    icon_h = _ICON_H
    icon_bottom = icon_y + icon_h if has_icon else icon_y

    # ── Title region (to the right of icon) ──────────────────────────
    if has_icon:
        title_x = icon_x + icon_w + _ICON_TITLE_GAP
    else:
        title_x = pad_l

    title_max_w = base_w - title_x - pad_r
    title_max_h = 60.0  # initial budget
    title_start_size = 20
    title_min_size = 12

    _, title_fitted_size, t_w, t_h = _measure_text(
        draw, title, title_max_w, title_max_h, title_start_size,
        min_size=title_min_size, hand=style.get("hand", True),
        bold=style.get("bold", True),
    )
    title_bottom = pad_t + max(t_h, 0)

    # ── Body region (below both icon and title) ──────────────────────
    content_gap = 4.0
    body_y = max(icon_bottom, title_bottom) + content_gap
    body_x = pad_l
    body_max_w = base_w - pad_l - pad_r
    body_max_h = max(20.0, base_h - body_y - pad_b)
    body_start_size = 14
    body_min_size = 11

    _, body_fitted_size, b_w, b_h = _measure_text(
        draw, body, body_max_w, body_max_h, body_start_size,
        min_size=body_min_size, hand=style.get("hand", True),
        bold=False,
    )

    # ── Compute final node size ──────────────────────────────────────
    # Grow if content overflows the initial budget
    content_bottom = body_y + b_h + pad_b if body else max(icon_bottom, title_bottom) + pad_b
    needed_w = max(
        base_w,
        title_x + t_w + pad_r,   # title may push width
        body_x + b_w + pad_r,    # body may push width
    )
    needed_h = max(base_h, content_bottom)

    card_w = needed_w
    card_h = needed_h

    # Recalculate title available width at final card_w
    final_title_w = card_w - title_x - pad_r
    final_body_w = card_w - pad_l - pad_r

    offsets: dict[str, dict] = {
        "icon": {
            "x": icon_x,
            "y": icon_y,
            "w": icon_w,
            "h": icon_h,
            "scale": _ICON_SCALE,
            "draw": has_icon,
        },
        "title": {
            "x": title_x,
            "y": pad_t,
            "w": final_title_w,
            "h": t_h if title else 0,
            "size": title_fitted_size,
            "min_size": title_min_size,
            "bold": style.get("bold", True),
            "hand": style.get("hand", True),
            "align": "left",
        },
    }
    if body:
        offsets["body"] = {
            "x": body_x,
            "y": body_y,
            "w": final_body_w,
            "h": b_h,
            "size": body_fitted_size,
            "min_size": body_min_size,
            "bold": False,
            "hand": style.get("hand", True),
            "align": "left",
        }

    return {"width": card_w, "height": card_h, "layout_offsets": offsets}


def _measure_diamond(
    element: dict,
    draw: ImageDraw.ImageDraw,
    style: dict,
) -> dict:
    """Compute width, height, and layout_offsets for a ``diamond`` element.

    The usable area inside a diamond is roughly 50 % of its bounding box
    in each axis.  We measure content to fill that inner area and then
    double outwards to get the outer diamond dimensions.
    """
    min_w, min_h = _MIN_SIZES["diamond"]
    base_w = max(element.get("width", 0) or 0, min_w)
    base_h = max(element.get("height", 0) or 0, min_h)

    title = element.get("title", "")
    body = element.get("body", "")

    # Inner usable area = 50 % of outer dimensions
    # Estimate text widths to find a better base width if width is not specified in element
    if "width" not in element or not element["width"]:
        _, _, natural_t_w, _ = _measure_text(
            draw, title, 500.0, 100.0, 18,
            min_size=12, hand=style.get("hand", True), bold=True
        )
        _, _, natural_b_w, _ = _measure_text(
            draw, body, 500.0, 100.0, 13,
            min_size=10, hand=style.get("hand", True), bold=style.get("bold", False)
        )
        max_natural_w = max(natural_t_w, natural_b_w)
        estimated_inner_w = max(70.0, min(140.0, max_natural_w))
        base_w = max(base_w, estimated_inner_w / 0.50)

    inner_w = base_w * 0.50
    inner_h = base_h * 0.50

    title_max_h = 100.0
    body_max_h = 150.0

    _, t_size, t_w, t_h = _measure_text(
        draw, title, inner_w, title_max_h, 18,
        min_size=12, hand=style.get("hand", True), bold=True,
    )
    _, b_size, b_w, b_h = _measure_text(
        draw, body, inner_w, body_max_h, 13,
        min_size=10, hand=style.get("hand", True), bold=style.get("bold", False),
    )

    # Grow inner area if content overflows, then map back to outer
    content_w = max(inner_w, t_w, b_w)
    usable_h = t_h + b_h + (3 if body else 0)
    content_h = max(inner_h, usable_h)
    outer_w = max(base_w, content_w / 0.50)
    outer_h = max(base_h, content_h / 0.50)

    # Ensure reasonable aspect ratio for diamonds (wider than tall)
    if outer_w < outer_h * 1.4:
        outer_w = outer_h * 1.4

    # Offsets relative to node origin, centred dynamically
    inset_x = (outer_w - content_w) / 2.0
    inset_y = (outer_h - usable_h) / 2.0
    content_gap = 3.0

    offsets: dict[str, dict] = {
        "title": {
            "x": inset_x,
            "y": inset_y,
            "w": content_w,
            "h": t_h if title else 0,
            "size": t_size,
            "min_size": 12,
            "bold": True,
            "hand": style.get("hand", True),
            "align": "center",
        },
    }
    if body:
        offsets["body"] = {
            "x": inset_x,
            "y": inset_y + (t_h if title else 0) + content_gap,
            "w": content_w,
            "h": b_h,
            "size": b_size,
            "min_size": 10,
            "bold": style.get("bold", False),
            "hand": style.get("hand", True),
            "align": "center",
        }

    return {"width": outer_w, "height": outer_h, "layout_offsets": offsets}


def _measure_input(
    element: dict,
    draw: ImageDraw.ImageDraw,
    style: dict,
) -> dict:
    """Compute width, height, and layout_offsets for an ``input`` chip.

    Layout::

        ┌─────────────────┐
        │   [icon 24×24]  │
        │     label        │
        └─────────────────┘
    """
    min_w, min_h = _MIN_SIZES["input"]
    base_w = max(element.get("width", 0) or 0, min_w)
    base_h = max(element.get("height", 0) or 0, min_h)

    label = element.get("label", "") or element.get("title", "")
    has_icon = bool(element.get("icon"))

    # Icon sits centred at the top
    icon_area_h = 28 if has_icon else 0
    icon_y = 6

    # Label below icon
    label_y = icon_area_h + 6
    label_max_w = base_w
    label_max_h = 60.0

    _, l_size, l_w, l_h = _measure_text(
        draw, label, label_max_w, label_max_h, 13,
        min_size=9, hand=style.get("hand", True), bold=False,
    )

    chip_w = max(base_w, l_w + 12)
    chip_h = max(base_h, label_y + l_h + 6)

    offsets: dict[str, dict] = {}
    if has_icon:
        offsets["icon"] = {
            "x": (chip_w - 24) / 2,
            "y": icon_y,
            "w": 24,
            "h": 24,
            "scale": 0.5,
            "draw": True,
        }
    offsets["title"] = {
        "x": 0,
        "y": label_y,
        "w": chip_w,
        "h": chip_h - label_y,
        "size": l_size,
        "min_size": 9,
        "bold": False,
        "hand": style.get("hand", True),
        "align": "center",
    }

    return {"width": chip_w, "height": chip_h, "layout_offsets": offsets}


def _measure_label(
    element: dict,
    draw: ImageDraw.ImageDraw,
    style: dict,
) -> dict:
    """Compute width, height, and layout_offsets for a ``label`` (free text)."""
    min_w, min_h = _MIN_SIZES["label"]
    base_w = max(element.get("width", 0) or 0, min_w)
    base_h = max(element.get("height", 0) or 0, min_h)

    text = element.get("title", "") or element.get("text", "")
    font_size = element.get("size", 14)

    _, t_size, t_w, t_h = _measure_text(
        draw, text, base_w, base_h, font_size,
        min_size=9, hand=style.get("hand", True),
        bold=style.get("bold", False),
    )

    lbl_w = max(base_w, t_w)
    lbl_h = max(base_h, t_h)

    offsets = {
        "title": {
            "x": 0,
            "y": 0,
            "w": lbl_w,
            "h": lbl_h,
            "size": t_size,
            "min_size": 9,
            "bold": style.get("bold", False),
            "hand": style.get("hand", True),
            "align": element.get("align", "center"),
        },
    }

    return {"width": lbl_w, "height": lbl_h, "layout_offsets": offsets}


def _measure_panel(
    element: dict,
    draw: ImageDraw.ImageDraw,
    style: dict,
) -> dict:
    """Return measurements for a ``panel``.

    Panels are containers whose final size is computed from their children
    during the layout phase.  Here we compute the minimum inner bounds
    required for their header text (title, subtitle, badge) instead of
    using hardcoded 100x100 placeholders.
    """
    pad = style["padding"]
    title = element.get("title", "")
    subtitle = element.get("subtitle", "")
    badge = element.get("badge", "")

    # Title region (always at top-left inside padding)
    title_w_budget = 400.0
    title_h_budget = 34.0

    _, t_size, t_w, t_h = _measure_text(
        draw, title, title_w_budget, title_h_budget, 22,
        min_size=12, hand=style.get("hand", True), bold=True,
    )

    offsets: dict[str, dict] = {
        "title": {
            "x": pad["left"],
            "y": 15,
            "w": title_w_budget,
            "h": max(title_h_budget, t_h),
            "size": t_size,
            "min_size": 12,
            "bold": True,
            "hand": style.get("hand", True),
            "align": "left",
        },
    }

    # Subtitle (below title in header area)
    s_w, s_h = 0.0, 0.0
    if subtitle:
        sub_y = offsets["title"]["y"] + offsets["title"]["h"] + 6.0
        _, s_size, s_w, s_h = _measure_text(
            draw, subtitle, title_w_budget, 24, 14,
            min_size=10, hand=style.get("hand", True), bold=False,
        )
        offsets["subtitle"] = {
            "x": pad["left"],
            "y": sub_y,
            "w": title_w_budget,
            "h": s_h,
            "size": s_size,
            "min_size": 10,
            "bold": False,
            "hand": style.get("hand", True),
            "align": "left",
        }

    # Badge (top-right corner chip)
    bg_w, bg_h = 0.0, 0.0
    if badge:
        _, bg_size, bg_w, bg_h = _measure_text(
            draw, badge, 120, 20, 11,
            min_size=8, hand=style.get("hand", True), bold=False,
        )
        offsets["badge"] = {
            "x_anchor": "right",   # renderer places relative to panel right edge
            "y": 15,
            "w": bg_w + 16,        # chip padding
            "h": bg_h + 8,
            "size": bg_size,
            "min_size": 8,
            "bold": False,
            "hand": style.get("hand", True),
            "align": "center",
        }

    t_w = t_w or 0.0
    t_h = t_h or 0.0

    # Compute minimum inner bounds required for header text
    if badge:
        min_w = pad["left"] + max(t_w, s_w) + 20.0 + (bg_w + 16.0) + pad["right"]
    else:
        min_w = pad["left"] + max(t_w, s_w) + pad["right"]

    header_content_h = 15.0 + t_h
    if subtitle:
        header_content_h += 2.0 + s_h
    if badge:
        header_content_h = max(header_content_h, 15.0 + bg_h + 8.0)

    min_h = header_content_h + 20.0 # add bottom buffer for header area

    panel_w = max(element.get("width", 0) or 0.0, min_w, 100.0)
    panel_h = max(element.get("height", 0) or 0.0, min_h, 100.0)

    return {
        "width": panel_w,
        "height": panel_h,
        "layout_offsets": offsets,
    }


# Dispatcher table: type → measurer function
_MEASURERS: dict[str, Any] = {
    "card":    _measure_card,
    "diamond": _measure_diamond,
    "input":   _measure_input,
    "label":   _measure_label,
    "panel":   _measure_panel,
}


# ═══════════════════════════════════════════════════════════════════════════
# Public: measure a single element
# ═══════════════════════════════════════════════════════════════════════════

def measure_element(
    element: dict,
    draw: ImageDraw.ImageDraw,
    parent_style: Optional[dict] = None,
) -> dict:
    """Compute ``width``, ``height``, and ``layout_offsets`` for *element*.

    The element dict is **mutated in-place** and also returned for convenience.

    Args:
        element:      A single element dict from the flat node list.
        draw:         PIL ImageDraw for text measurement (1×1 scratch image).
        parent_style: Resolved style of the element's parent (for cascade).

    Returns:
        The same *element* dict, now augmented with ``width``, ``height``,
        ``layout_offsets``, and ``_resolved_style``.
    """
    etype = element.get("type", "card")
    style = element.get("_resolved_style")
    if style is None:
        style = resolve_style(element, parent_style)
        element["_resolved_style"] = style

    measurer = _MEASURERS.get(etype, _measure_card)
    result = measurer(element, draw, style)

    element["width"] = result["width"]
    element["height"] = result["height"]
    element["layout_offsets"] = result["layout_offsets"]

    return element


# ═══════════════════════════════════════════════════════════════════════════
# Tree flattener — walk the elements hierarchy
# ═══════════════════════════════════════════════════════════════════════════

def _flatten_elements(
    elements: list[dict],
    parent_id: Optional[str] = None,
    id_prefix: str = "",
    id_counters: Optional[dict[str, int]] = None,
) -> list[dict]:
    """Recursively walk an element tree, producing a flat node list without measuring.

    Each element is assigned:
    - ``id``       (auto-generated if missing)
    - ``parent``   (parent element ID, or ``None`` for top-level)
    - ``children`` (list of child IDs, populated for panels)

    Args:
        elements:     List of raw element dicts.
        parent_id:    ID of the enclosing parent, or None.
        id_prefix:    Prefix for auto-generated IDs (e.g. ``"core_"``).
        id_counters:  Mutable dict tracking auto-ID indices per type.

    Returns:
        A flat list of node dicts.
    """
    if id_counters is None:
        id_counters = {}

    nodes: list[dict] = []

    for elem in elements:
        etype = elem.get("type", "card")

        # ── Auto-generate ID if missing ──────────────────────────────
        if "id" not in elem:
            counter_key = f"{id_prefix}{etype}"
            idx = id_counters.get(counter_key, 0)
            id_counters[counter_key] = idx + 1
            elem["id"] = f"{id_prefix}{etype}_{idx}"

        node_id = elem["id"]

        # ── Build the IR node (shallow copy + enrich) ────────────────
        node: dict[str, Any] = {
            "id": node_id,
            "type": etype,
            "title": elem.get("title") or elem.get("label", ""),
            "body": elem.get("body", ""),
            "icon": elem.get("icon"),
            "style": elem.get("style", {}),
            "color": elem.get("color"),
            "color_preset": elem.get("color_preset"),
            "parent": parent_id or elem.get("parent"),
            "children": [],
            # Preserve any explicit coordinates and sizes from spec
            "x": elem.get("x"),
            "y": elem.get("y"),
            "width": elem.get("width"),
            "height": elem.get("height"),
        }

        # Copy through auxiliary fields the renderer may need
        for aux_key in (
            "thought", "badge", "subtitle", "label",
            "size", "align", "opacity", "fixed", "out_of_flow",
        ):
            if aux_key in elem:
                node[aux_key] = elem[aux_key]

        # ── Recurse into children (panels have "cards" or "children") ─
        child_elements = (
            elem.get("children")
            or elem.get("cards")
            or elem.get("elements")
            or []
        )

        child_nodes: list[dict] = []
        if child_elements:
            child_nodes = _flatten_elements(
                child_elements,
                parent_id=node_id,
                id_prefix=f"{node_id}_",
                id_counters=id_counters,
            )
            node["children"] = [cn["id"] for cn in child_nodes]

        # Handle panel footer as a child card
        if "footer" in elem and isinstance(elem["footer"], dict):
            footer = elem["footer"].copy()
            footer.setdefault("type", "card")
            footer.setdefault("id", f"{node_id}_footer")
            footer_nodes = _flatten_elements(
                [footer],
                parent_id=node_id,
                id_prefix=f"{node_id}_",
                id_counters=id_counters,
            )
            node["children"].extend(fn["id"] for fn in footer_nodes)
            child_nodes.extend(footer_nodes)

        nodes.append(node)
        nodes.extend(child_nodes)

    return nodes


# ═══════════════════════════════════════════════════════════════════════════
# Scratch surface helper
# ═══════════════════════════════════════════════════════════════════════════

def _scratch_draw() -> ImageDraw.ImageDraw:
    """Create a tiny 1×1 PIL ImageDraw used only for text measurement."""
    img = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    return ImageDraw.Draw(img)


# ═══════════════════════════════════════════════════════════════════════════
# Public: compile_spec  (main entry point)
# ═══════════════════════════════════════════════════════════════════════════

def compile_spec(spec: dict) -> dict:
    """Compile a v2 spec into the Intermediate Representation.

    The IR is a flat dictionary with three keys:

    - ``nodes``       — flat list of measured node dicts, each with
      ``id``, ``type``, ``title``, ``body``, ``icon``, ``parent``,
      ``children``, ``width``, ``height``, ``layout_offsets``, and
      ``_resolved_style``.
    - ``connections`` — list of connection dicts (``{path, style}``).
    - ``annotations`` — list of annotation dicts (labels, watermarks).

    The compiler does **not** assign absolute ``(x, y)`` positions — that
    is the layout engine's job.  It only computes *sizes* and *relative
    layout_offsets* (icon / title / body positions relative to the node
    origin).

    Args:
        spec: The validated and normalised spec JSON dict.

    Returns:
        An IR dict ``{"nodes": [...], "connections": [...], "annotations": [...]}``.
    """
    draw = _scratch_draw()

    raw_elements = spec["elements"]
    connections = spec.get("connections", [])
    raw_annotations = spec.get("annotations", [])
    id_counters: dict[str, int] = {}
    
    # Pass 1: Flattening & Structure Discovery
    nodes = _flatten_elements(
        raw_elements,
        parent_id=None,
        id_prefix="",
        id_counters=id_counters,
    )

    # ── Rebuild children lists from parent back-references ────────────
    # The schema validator flattens children out of the parent dict
    # and sets `parent` on each child, but the parent's `children`
    # list may be empty.  Rebuild it here.
    nodes_map: dict[str, dict] = {n["id"]: n for n in nodes}
    for node in nodes:
        parent_id_val = node.get("parent")
        if parent_id_val and parent_id_val in nodes_map:
            parent_node = nodes_map[parent_id_val]
            if node["id"] not in parent_node.get("children", []):
                parent_node.setdefault("children", []).append(node["id"])
    # Also copy layout direction/gap/padding from spec elements to panel nodes
    _spec_elems_by_id = {e["id"]: e for e in raw_elements if isinstance(e, dict) and "id" in e}
    for node in nodes:
        if node["type"] == "panel" and node["id"] in _spec_elems_by_id:
            src = _spec_elems_by_id[node["id"]]
            if "layout" in src:
                node["layout"] = src["layout"]

    # Pass 2: Style & Theme Cascade
    spec_theme = spec.get("theme")
    theme_dict = THEME
    if isinstance(spec_theme, dict):
        theme_dict = THEME.copy()
        theme_dict.update(spec_theme)

    def cascade_styles_recursive(node_id: str, parent_style: Optional[dict] = None) -> None:
        node = nodes_map[node_id]
        style = resolve_style(node, parent_style, theme=theme_dict)
        node["_resolved_style"] = style
        for cid in node.get("children", []):
            if cid in nodes_map:
                cascade_styles_recursive(cid, style)

    for node in nodes:
        if not node.get("parent"):
            cascade_styles_recursive(node["id"], None)

    # Pass 3: Intrinsic Metric Capture
    for node in nodes:
        measure_element(node, draw)

    # ── Measure annotation labels ────────────────────────────────────
    annotation_nodes: list[dict] = []
    for ann in raw_annotations:
        ann_node = ann.copy()
        ann_node.setdefault("type", "label")
        # Resolve annotation style with theme dict first
        ann_node["_resolved_style"] = resolve_style(ann_node, theme=theme_dict)
        measure_element(ann_node, draw)
        annotation_nodes.append(ann_node)

    # ── Carry forward canvas / meta from the spec ────────────────────
    ir: dict[str, Any] = {
        "nodes": nodes,
        "connections": connections,
        "annotations": annotation_nodes,
    }

    # Preserve spec-level metadata the layout engine needs
    for meta_key in (
        "canvas", "theme", "hand", "auto_layout",
        "title", "signature", "layout",
    ):
        if meta_key in spec:
            ir[meta_key] = spec[meta_key]

    return ir
