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
    "card":    {"left": 16, "right": 16, "top": 12, "bottom": 12},
    "diamond": {"left": 0,  "right": 0,  "top": 0,  "bottom": 0},
    "panel":   {"left": 20, "right": 20, "top": 60, "bottom": 20},
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
    "input":   (78,  50),
    "panel":   (100, 100),   # panels are resized from children later
    "label":   (40,  20),
}

# Icon dimensions in logical pixels (pre-scale)
_ICON_W = 32
_ICON_H = 32
_ICON_SCALE = 0.8          # draw-time icon scale multiplier
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
        ``padding``.
    """
    th = theme or THEME
    etype = element.get("type", "card")

    # 1. Start with built-in defaults
    style = copy.deepcopy(_DEFAULT_STYLE.get(etype, _DEFAULT_STYLE["card"]))
    style["padding"] = copy.deepcopy(
        _DEFAULT_PADDING.get(etype, _DEFAULT_PADDING["card"])
    )

    # 2. Resolve color_preset from theme
    preset = (
        element.get("color_preset")
        or element.get("style", {}).get("color_preset")
    )
    if preset:
        preset_lower = preset.lower()
        _apply_color_preset(style, preset_lower, th)

    # Fallback: use element-level "color" for strokeColor
    if not style["strokeColor"] and element.get("color"):
        style["strokeColor"] = element["color"]

    # 3. Inherit from parent style (selective keys only)
    if parent_style:
        for key in ("hand",):
            if key in parent_style and style.get(key) is None:
                style[key] = parent_style[key]

    # 4. Apply element-level overrides
    elem_style = element.get("style", {})
    for key in (
        "fillColor", "strokeColor", "strokeWidth", "strokeStyle",
        "cornerRadius", "bold", "hand",
    ):
        if key in elem_style:
            style[key] = elem_style[key]

    # Padding merge (element overrides per-side)
    elem_padding = elem_style.get("padding") or element.get("padding")
    if isinstance(elem_padding, dict):
        for side in ("left", "right", "top", "bottom"):
            if side in elem_padding:
                style["padding"][side] = elem_padding[side]
    elif isinstance(elem_padding, (int, float)):
        for side in ("left", "right", "top", "bottom"):
            style["padding"][side] = elem_padding

    # Validate hex colours
    for ckey in ("fillColor", "strokeColor"):
        if style.get(ckey) and not _is_valid_hex(style[ckey]):
            style[ckey] = None

    return style


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
    title_max_h = 30.0  # initial budget
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
    body_min_size = 9

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
    inner_w = base_w * 0.5
    inner_h = base_h * 0.5

    title_max_h = inner_h * 0.45
    body_max_h = inner_h * 0.55

    _, t_size, t_w, t_h = _measure_text(
        draw, title, inner_w, title_max_h, 18,
        min_size=10, hand=style.get("hand", True), bold=True,
    )
    _, b_size, b_w, b_h = _measure_text(
        draw, body, inner_w, body_max_h, 13,
        min_size=6, hand=style.get("hand", True), bold=style.get("bold", False),
    )

    # Grow inner area if content overflows, then map back to outer
    content_w = max(inner_w, t_w, b_w)
    content_h = max(inner_h, t_h + b_h + (3 if body else 0))
    outer_w = max(base_w, content_w / 0.5)
    outer_h = max(base_h, content_h / 0.5)

    # Offsets relative to node origin, centred in the diamond
    inset_x = outer_w * 0.25
    inset_y = outer_h * 0.25
    usable_w = outer_w * 0.5
    content_gap = 3.0

    offsets: dict[str, dict] = {
        "title": {
            "x": inset_x,
            "y": inset_y,
            "w": usable_w,
            "h": t_h if title else 0,
            "size": t_size,
            "min_size": 10,
            "bold": True,
            "hand": style.get("hand", True),
            "align": "center",
        },
    }
    if body:
        offsets["body"] = {
            "x": inset_x,
            "y": inset_y + (t_h if title else 0) + content_gap,
            "w": usable_w,
            "h": b_h,
            "size": b_size,
            "min_size": 6,
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
    label_max_h = max(20.0, base_h - label_y)

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
    """Return placeholder measurements for a ``panel``.

    Panels are containers whose final size is computed from their children
    during the layout phase.  Here we only set up the title / subtitle /
    badge offsets that live in the panel's header area.
    """
    pad = style["padding"]
    title = element.get("title", "")
    subtitle = element.get("subtitle", "")
    badge = element.get("badge", "")

    # Title region (always at top-left inside padding)
    # We use a generous width budget; the panel will grow to fit children.
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
            "h": title_h_budget,
            "size": t_size,
            "min_size": 12,
            "bold": True,
            "hand": style.get("hand", True),
            "align": "left",
        },
    }

    # Subtitle (below title in header area)
    if subtitle:
        sub_y = 15 + t_h + 2
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

    # Placeholder size — layout phase will overwrite
    return {
        "width": element.get("width", 100),
        "height": element.get("height", 100),
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
    parent_style: Optional[dict] = None,
    draw: Optional[ImageDraw.ImageDraw] = None,
    id_prefix: str = "",
    id_counters: Optional[dict[str, int]] = None,
) -> list[dict]:
    """Recursively walk an element tree, producing a flat node list.

    Each element is assigned:
    - ``id``       (auto-generated if missing)
    - ``parent``   (parent element ID, or ``None`` for top-level)
    - ``children`` (list of child IDs, populated for panels)
    - ``width``, ``height``, ``layout_offsets`` (from ``measure_element``)

    Args:
        elements:     List of raw element dicts.
        parent_id:    ID of the enclosing parent, or None.
        parent_style: Resolved style of the parent for cascade.
        draw:         PIL ImageDraw for measurement.
        id_prefix:    Prefix for auto-generated IDs (e.g. ``"core_"``).
        id_counters:  Mutable dict tracking auto-ID indices per type.

    Returns:
        A flat list of fully-measured node dicts.
    """
    if id_counters is None:
        id_counters = {}
    if draw is None:
        draw = _scratch_draw()

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
            # Preserve any explicit coordinates from spec
            "x": elem.get("x"),
            "y": elem.get("y"),
        }

        # Copy through auxiliary fields the renderer may need
        for aux_key in (
            "thought", "badge", "subtitle", "label",
            "size", "align", "opacity", "fixed",
        ):
            if aux_key in elem:
                node[aux_key] = elem[aux_key]

        # ── Measure the node ─────────────────────────────────────────
        measure_element(node, draw, parent_style)

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
                parent_style=node.get("_resolved_style"),
                draw=draw,
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
                parent_style=node.get("_resolved_style"),
                draw=draw,
                id_prefix=f"{node_id}_",
                id_counters=id_counters,
            )
            node["children"].extend(fn["id"] for fn in footer_nodes)
            child_nodes.extend(footer_nodes)

        nodes.append(node)
        nodes.extend(child_nodes)

    return nodes


# ═══════════════════════════════════════════════════════════════════════════
# Spec → IR: legacy spec shape adapter
# ═══════════════════════════════════════════════════════════════════════════

def _adapt_legacy_spec(spec: dict) -> tuple[list[dict], list[dict], list[dict]]:
    """Convert the current (v1-ish) spec shape into a flat elements + connections list.

    The default-spec.json uses top-level keys like ``inputs``, ``core``,
    ``decision``, ``output``, ``left_panel``, ``center_panel``, ``right_panel``.
    This function normalises those into a list of elements and connections that
    ``_flatten_elements`` can walk.

    Returns:
        ``(elements, connections, annotations)``
    """
    elements: list[dict] = []
    connections: list[dict] = []
    annotations: list[dict] = []

    # ── Input panel ──────────────────────────────────────────────────
    if "inputs" in spec:
        input_panel: dict[str, Any] = {
            "id": "input_panel",
            "type": "panel",
            "title": spec.get("input_title", "Inputs"),
            "style": spec.get("input_panel_style", {}),
            "children": [],
        }
        for i, inp in enumerate(spec["inputs"]):
            child = inp.copy()
            child.setdefault("type", "input")
            child.setdefault("id", f"input_{i}")
            # Input chips use "label" as display text
            if "label" in child and "title" not in child:
                child["title"] = child["label"]
            input_panel["children"].append(child)
        elements.append(input_panel)

    # ── Core panel ───────────────────────────────────────────────────
    if "core" in spec:
        core_spec = spec["core"]
        core_panel: dict[str, Any] = {
            "id": "core_panel",
            "type": "panel",
            "title": core_spec.get("title", "Core"),
            "subtitle": core_spec.get("subtitle", ""),
            "color_preset": core_spec.get("color_preset"),
            "style": core_spec.get("style", {}),
            "children": [],
        }
        for i, card in enumerate(core_spec.get("cards", [])):
            child = card.copy()
            child.setdefault("type", "card")
            child.setdefault("id", f"core_card_{i}")
            core_panel["children"].append(child)
        elements.append(core_panel)

        # Build a linear chain connection through core cards
        core_ids = [c["id"] for c in core_panel["children"]]
        if core_ids:
            connections.append({"path": core_ids, "style": "solid"})

    # ── Decision diamond ─────────────────────────────────────────────
    if "decision" in spec:
        dec = spec["decision"].copy()
        dec.setdefault("type", "diamond")
        dec.setdefault("id", "decision")
        elements.append(dec)

    # ── Output chip ──────────────────────────────────────────────────
    if "output" in spec:
        out = spec["output"].copy()
        out.setdefault("type", "card")
        out.setdefault("id", "output")
        if "label" in out and "title" not in out:
            out["title"] = out["label"]
        elements.append(out)

    # ── Side panels (left, center, right) ────────────────────────────
    for panel_key in ("left_panel", "center_panel", "right_panel"):
        if panel_key not in spec:
            continue
        panel_spec = spec[panel_key]
        panel: dict[str, Any] = {
            "id": panel_key,
            "type": "panel",
            "title": panel_spec.get("title", ""),
            "subtitle": panel_spec.get("subtitle", ""),
            "badge": panel_spec.get("badge", ""),
            "color_preset": panel_spec.get("color_preset"),
            "style": panel_spec.get("style", {}),
            "children": [],
        }
        for i, card in enumerate(panel_spec.get("cards", [])):
            child = card.copy()
            child.setdefault("type", "card")
            child.setdefault("id", f"{panel_key.replace('_panel', '')}_card_{i}")
            panel["children"].append(child)

        # Footer sub-card
        if "footer" in panel_spec:
            panel["footer"] = panel_spec["footer"]

        elements.append(panel)

    # ── Free-standing labels ─────────────────────────────────────────
    if spec.get("loop_label"):
        annotations.append({
            "id": "loop_label",
            "type": "label",
            "title": spec["loop_label"],
        })
    if spec.get("retry_label"):
        annotations.append({
            "id": "retry_label",
            "type": "label",
            "title": spec["retry_label"],
        })

    # ── Core → decision → output connections ─────────────────────────
    core_card_ids = [
        el["id"] for el in elements
        if el.get("type") == "panel" and el["id"] == "core_panel"
        for child in el.get("children", [])
        for el in [child]  # flatten
    ]
    if "decision" in spec and "core" in spec:
        core_cards = spec["core"].get("cards", [])
        if core_cards:
            last_core = f"core_card_{len(core_cards) - 1}"
            connections.append({"path": [last_core, "decision"], "style": "solid"})
    if "decision" in spec and "output" in spec:
        connections.append({"path": ["decision", "output"], "style": "solid"})

    # ── Explicit connections from spec ───────────────────────────────
    for conn in spec.get("connections", []):
        if isinstance(conn, dict):
            connections.append(conn)
        elif isinstance(conn, list):
            connections.append({"path": conn, "style": "solid"})

    return elements, connections, annotations


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
    """Compile a v2 (or adapted v1) spec into the Intermediate Representation.

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
        spec: The raw spec JSON dict.

    Returns:
        An IR dict ``{"nodes": [...], "connections": [...], "annotations": [...]}``.
    """
    draw = _scratch_draw()

    # ── Detect spec shape ────────────────────────────────────────────
    #  v2 specs have a top-level "elements" list.
    #  Legacy specs use named top-level keys (core, inputs, …).
    if "elements" in spec:
        raw_elements = spec["elements"]
        raw_connections = spec.get("connections", [])
        raw_annotations = spec.get("annotations", [])
        # Normalise connections
        connections = []
        for conn in raw_connections:
            if isinstance(conn, dict):
                connections.append(conn)
            elif isinstance(conn, list):
                connections.append({"path": conn, "style": "solid"})
    else:
        raw_elements, connections, raw_annotations = _adapt_legacy_spec(spec)

    # ── Flatten + measure ────────────────────────────────────────────
    id_counters: dict[str, int] = {}
    nodes = _flatten_elements(
        raw_elements,
        parent_id=None,
        parent_style=None,
        draw=draw,
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

    # ── Measure annotation labels ────────────────────────────────────
    annotation_nodes: list[dict] = []
    for ann in raw_annotations:
        ann_node = ann.copy()
        ann_node.setdefault("type", "label")
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
