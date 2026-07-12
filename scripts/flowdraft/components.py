"""
flowdraft.components
--------------------
High-level reusable diagram components: brand mark, input chips, and card
drawers (core card, mini card, pack row).

Each function composes the primitive drawing calls from ``flowdraft.drawing``
and ``flowdraft.text`` to produce a complete, visually styled element.
"""

from .constants import THEME
from . import constants as _c  # live attribute access; never bind SCALE_X/Y at import time
from .drawing import draw_rect, draw_ellipse, draw_line, icon, draw_signature
from .text import draw_text


# ---------------------------------------------------------------------------
# Brand mark
# ---------------------------------------------------------------------------
def brand(ex, draw, signature: str, bx: float = None, by: float = None) -> None:
    """Draw the colourful dot-grid and signature watermark in the top-right area.

    The dots are arranged in a 4×2 grid with alternating accent colours.  The
    signature text is drawn to the right of the dots with a chromatic-aberration
    shadow effect (handled by ``draw_signature``).

    Args:
        ex:        Excal JSON builder.
        draw:      PIL ImageDraw.
        signature: Signature string (e.g. "@FlowDraft").
        bx:        X anchor in logical pixels (default: 955).
        by:        Y anchor in logical pixels (default: 143).
    """
    SCALE_X = _c.SCALE_X
    SCALE_Y = _c.SCALE_Y
    if bx is None:
        bx = 955 * SCALE_X
    else:
        bx = bx * SCALE_X
    if by is None:
        by = 143 * SCALE_Y
    else:
        by = by * SCALE_Y

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
        draw_ellipse(
            ex, draw,
            bx + dx * SCALE_X, by + dy * SCALE_Y,
            5 * SCALE_X, 5 * SCALE_Y,
            color, color,
            1 * min(SCALE_X, SCALE_Y),
            scaled=True,
        )
    draw_signature(ex, draw, signature, bx + 43 * SCALE_X, by - 8 * SCALE_Y)


# ---------------------------------------------------------------------------
# Input chip
# ---------------------------------------------------------------------------
def small_input(ex, draw, x: float, y: float, item: dict) -> None:
    """Draw a single data-source input chip.

    The chip consists of an icon above a centred label.  ``x`` is the
    horizontal centre of the chip; ``y`` is the top of the icon area.
    All coordinates are already scaled (physical pixels).

    Args:
        ex:   Excal JSON builder.
        draw: PIL ImageDraw.
        x:    Horizontal centre of the chip (physical pixels).
        y:    Top of the icon area (physical pixels).
        item: Dict with keys: "icon", "color", optionally "txt"/"sz"/"w"/"h"
              for pre-fitted text, or "label" for auto-fitted text.
    """
    SCALE_X = _c.SCALE_X
    SCALE_Y = _c.SCALE_Y
    kind    = item.get("icon", "file")
    color   = item.get("color", THEME["cyan"])
    chip_w  = item.get("w", 78) * SCALE_X

    # Icon centred horizontally inside the chip
    icon(ex, draw, kind, x - 16 * SCALE_X, y + 1 * SCALE_Y, color, 0.65 * min(SCALE_X, SCALE_Y), scaled=True)

    if "txt" in item:
        # Pre-fitted text dimensions supplied by layout phase
        draw_text(
            ex, draw, item["txt"],
            x - chip_w / 2, y + 34 * SCALE_Y,
            chip_w, item["h"] * SCALE_Y,
            item["sz"] * min(SCALE_X, SCALE_Y),
            THEME["white"], "center", fit=False, scaled=True,
        )
    else:
        chip_w_px = 78 * SCALE_X
        draw_text(
            ex, draw, item.get("label", ""),
            x - chip_w_px / 2, y + 34 * SCALE_Y,
            chip_w_px, 24 * SCALE_Y,
            13 * min(SCALE_X, SCALE_Y),
            THEME["white"], "center",
            fit=True, min_size=9 * min(SCALE_X, SCALE_Y), scaled=True,
        )


# ---------------------------------------------------------------------------
# Card drawers
# ---------------------------------------------------------------------------
def core_card(ex, draw, x: float, y: float, card: dict) -> None:
    """Draw a core pipeline card (blue border, icon + title + body).

    Accepts either a pre-fitted layout dict (from ``layout_core_card``) or a
    raw spec dict with "title"/"body"/"icon"/"color" keys.

    Args:
        ex:   Excal JSON builder.
        draw: PIL ImageDraw.
        x, y: Top-left in physical pixels.
        card: Layout dict or raw spec dict.
    """
    SCALE_X = _c.SCALE_X
    SCALE_Y = _c.SCALE_Y
    if "title_txt" in card:
        w = card["w"]
        h = card["h"]
        draw_rect(ex, draw, x, y, w * SCALE_X, h * SCALE_Y,
                  THEME["core_stroke"], THEME["blue_fill"],
                  1.5 * min(SCALE_X, SCALE_Y), 14 * min(SCALE_X, SCALE_Y), scaled=True)
        icon(ex, draw, card.get("icon", "file"),
             x + 14 * SCALE_X, y + 13 * SCALE_Y,
             card.get("color", THEME["cyan"]), 0.85 * min(SCALE_X, SCALE_Y), scaled=True)
        draw_text(ex, draw, card["title_txt"],
                  x + 110 * SCALE_X, y + 11 * SCALE_Y,
                  card["title_w"] * SCALE_X, card["title_h"] * SCALE_Y,
                  card["title_sz"] * min(SCALE_X, SCALE_Y),
                  THEME["white"], "center", hand=True, bold=True, fit=False, scaled=True)
        draw_text(ex, draw, card["body_txt"],
                  x + 92 * SCALE_X, y + (42 + (card["title_h"] - 28)) * SCALE_Y,
                  card["body_w"] * SCALE_X, card["body_h"] * SCALE_Y,
                  card["body_sz"] * min(SCALE_X, SCALE_Y),
                  THEME["white"], "center", spacing=3, fit=False, scaled=True)
    else:
        draw_rect(ex, draw, x, y, 260 * SCALE_X, 90 * SCALE_Y,
                  THEME["core_stroke"], THEME["blue_fill"],
                  1.5 * min(SCALE_X, SCALE_Y), 14 * min(SCALE_X, SCALE_Y), scaled=True)
        icon(ex, draw, card.get("icon", "file"),
             x + 14 * SCALE_X, y + 13 * SCALE_Y,
             card.get("color", THEME["cyan"]), 0.85 * min(SCALE_X, SCALE_Y), scaled=True)
        draw_text(ex, draw, card.get("title", ""),
                  x + 110 * SCALE_X, y + 11 * SCALE_Y, 100 * SCALE_X, 28 * SCALE_Y,
                  20 * min(SCALE_X, SCALE_Y), THEME["white"], "center",
                  hand=True, bold=True, fit=True, min_size=15 * min(SCALE_X, SCALE_Y), scaled=True)
        draw_text(ex, draw, card.get("body", ""),
                  x + 92 * SCALE_X, y + 42 * SCALE_Y, 150 * SCALE_X, 38 * SCALE_Y,
                  14 * min(SCALE_X, SCALE_Y), THEME["white"], "center",
                  spacing=3, fit=True, min_size=12 * min(SCALE_X, SCALE_Y), scaled=True)


def mini_card(ex, draw, x: float, y: float, w: float, h: float, card: dict, stroke: str, fill: str) -> None:
    """Draw a mini card (used in left-panel memory sources and similar panels).

    Args:
        ex:          Excal JSON builder.
        draw:        PIL ImageDraw.
        x, y:        Top-left in physical pixels.
        w, h:        Card dimensions in physical pixels.
        card:        Layout dict or raw spec dict.
        stroke:      Border colour.
        fill:        Background fill colour.
    """
    _draw_mini = lambda title, body, title_w, title_h, title_sz, body_w, body_h, body_sz: None  # noqa — defined inline below

    SCALE_X = _c.SCALE_X
    SCALE_Y = _c.SCALE_Y
    draw_rect(ex, draw, x, y, w, h, stroke, fill,
              1.5 * min(SCALE_X, SCALE_Y), 13 * min(SCALE_X, SCALE_Y), scaled=True)
    scale = 0.65 if h < 70 * SCALE_Y else 0.75
    icon(ex, draw, card.get("icon", "file"),
         x + 10 * SCALE_X, y + 10 * SCALE_Y,
         card.get("color", THEME["cyan"]), scale * min(SCALE_X, SCALE_Y), scaled=True)

    if "title_txt" in card:
        draw_text(ex, draw, card["title_txt"],
                  x + 78 * SCALE_X, y + 12 * SCALE_Y,
                  card["title_w"] * SCALE_X, card["title_h"] * SCALE_Y,
                  card["title_sz"] * min(SCALE_X, SCALE_Y),
                  THEME["white"], "left", bold=True, fit=False, scaled=True)
        draw_text(ex, draw, card["body_txt"],
                  x + 78 * SCALE_X, y + (12 + card["title_h"] + 2) * SCALE_Y,
                  card["body_w"] * SCALE_X, card["body_h"] * SCALE_Y,
                  card["body_sz"] * min(SCALE_X, SCALE_Y),
                  THEME["white"], "left", spacing=3, fit=False, scaled=True)
    else:
        draw_text(ex, draw, card.get("title", ""),
                  x + 78 * SCALE_X, y + 12 * SCALE_Y, 115 * SCALE_X, 24 * SCALE_Y,
                  17 * min(SCALE_X, SCALE_Y), THEME["white"], "left",
                  bold=True, fit=True, min_size=12 * min(SCALE_X, SCALE_Y), scaled=True)
        draw_text(ex, draw, card.get("body", ""),
                  x + 78 * SCALE_X, y + 38 * SCALE_Y,
                  w - 92 * SCALE_X, h - 43 * SCALE_Y,
                  12 * min(SCALE_X, SCALE_Y), THEME["white"], "left",
                  spacing=3, fit=True, min_size=10 * min(SCALE_X, SCALE_Y), scaled=True)


def pack_row(ex, draw, x: float, y: float, card: dict) -> None:
    """Draw a green-bordered pack row card (used in the right memory-pack panel).

    Args:
        ex:   Excal JSON builder.
        draw: PIL ImageDraw.
        x, y: Top-left in physical pixels.
        card: Layout dict or raw spec dict.
    """
    SCALE_X = _c.SCALE_X
    SCALE_Y = _c.SCALE_Y
    if "title_txt" in card:
        w = card["w"]
        h = card["h"]
        draw_rect(ex, draw, x, y, w * SCALE_X, h * SCALE_Y,
                  THEME["green"], "#04200f",
                  2 * min(SCALE_X, SCALE_Y), 8 * min(SCALE_X, SCALE_Y), scaled=True)
        icon(ex, draw, card.get("icon", "file"),
             x + 12 * SCALE_X, y + 10 * SCALE_Y,
             card.get("color", THEME["cyan"]), 0.75 * min(SCALE_X, SCALE_Y), scaled=True)
        draw_text(ex, draw, card["title_txt"],
                  x + 86 * SCALE_X, y + 12 * SCALE_Y,
                  card["title_w"] * SCALE_X, card["title_h"] * SCALE_Y,
                  card["title_sz"] * min(SCALE_X, SCALE_Y),
                  THEME["white"], "center", bold=True, fit=False, scaled=True)
        draw_text(ex, draw, card["body_txt"],
                  x + 80 * SCALE_X, y + (12 + card["title_h"] + 5) * SCALE_Y,
                  card["body_w"] * SCALE_X, card["body_h"] * SCALE_Y,
                  card["body_sz"] * min(SCALE_X, SCALE_Y),
                  THEME["white"], "center", spacing=3, fit=False, scaled=True)
    else:
        draw_rect(ex, draw, x, y, 228 * SCALE_X, 84 * SCALE_Y,
                  THEME["green"], "#04200f",
                  2 * min(SCALE_X, SCALE_Y), 8 * min(SCALE_X, SCALE_Y), scaled=True)
        icon(ex, draw, card.get("icon", "file"),
             x + 12 * SCALE_X, y + 10 * SCALE_Y,
             card.get("color", THEME["cyan"]), 0.75 * min(SCALE_X, SCALE_Y), scaled=True)
        draw_text(ex, draw, card.get("title", ""),
                  x + 86 * SCALE_X, y + 12 * SCALE_Y, 120 * SCALE_X, 25 * SCALE_Y,
                  17 * min(SCALE_X, SCALE_Y), THEME["white"], "center",
                  bold=True, fit=True, min_size=12 * min(SCALE_X, SCALE_Y), scaled=True)
        draw_text(ex, draw, card.get("body", ""),
                  x + 80 * SCALE_X, y + 42 * SCALE_Y, 135 * SCALE_X, 30 * SCALE_Y,
                  12 * min(SCALE_X, SCALE_Y), THEME["white"], "center",
                  spacing=3, fit=True, min_size=10 * min(SCALE_X, SCALE_Y), scaled=True)
