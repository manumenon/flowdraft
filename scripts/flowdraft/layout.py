"""
flowdraft.layout
----------------
Layout measurement helpers and the ``CollisionRegistry`` overlap detector.

Layout functions perform a *dry-run* text-fit measurement (using a 1×1 dummy
PIL canvas) to determine card dimensions before any actual drawing occurs.
This two-pass approach lets the renderer place elements precisely without
trial-and-error resizing.
"""

from PIL import Image, ImageDraw

from .constants import THEME, SCALE
from .fonts import text_size, has_cjk
from .text import fit_text


# ---------------------------------------------------------------------------
# Collision detection
# ---------------------------------------------------------------------------
class CollisionRegistry:
    """Track registered bounding boxes and detect non-nested overlaps.

    Usage::

        registry = CollisionRegistry()
        registry.register("Panel", 0, 0, 300, 200)
        registry.register("Card",  10, 10, 100, 80)
        overlaps = registry.check_overlaps()  # [] — card is nested inside panel
    """

    def __init__(self) -> None:
        self.elements: list = []

    def register(self, name: str, x: float, y: float, w: float, h: float) -> None:
        """Register a bounding box by name.

        Args:
            name: Human-readable identifier for warning messages.
            x, y: Top-left corner in logical pixels.
            w, h: Width and height in logical pixels.
        """
        self.elements.append({
            "name": name,
            "x1": x,
            "y1": y,
            "x2": x + w,
            "y2": y + h,
            "w": w,
            "h": h,
        })

    def check_overlaps(self) -> list:
        """Return a list of ``(name_a, name_b)`` pairs that overlap non-nestedly.

        Nested boxes (where one fully contains the other) are excluded because
        that is expected and intentional (cards inside panels).

        Returns:
            A list of overlapping name pairs.  Empty list means no overlaps.
        """
        overlaps = []
        for i in range(len(self.elements)):
            for j in range(i + 1, len(self.elements)):
                el1, el2 = self.elements[i], self.elements[j]
                no_overlap = (
                    el1["x2"] <= el2["x1"] or el2["x2"] <= el1["x1"]
                    or el1["y2"] <= el2["y1"] or el2["y2"] <= el1["y1"]
                )
                if no_overlap:
                    continue
                nested1 = (el1["x1"] <= el2["x1"] and el2["x2"] <= el1["x2"]
                           and el1["y1"] <= el2["y1"] and el2["y2"] <= el1["y2"])
                nested2 = (el2["x1"] <= el1["x1"] and el1["x2"] <= el2["x2"]
                           and el2["y1"] <= el1["y1"] and el1["y2"] <= el2["y2"])
                if not (nested1 or nested2):
                    overlaps.append((el1["name"], el2["name"]))
        return overlaps


# ---------------------------------------------------------------------------
# Shared text-fit measurement helper
# ---------------------------------------------------------------------------
def layout_text_fit(
    draw: ImageDraw.ImageDraw,
    text: str,
    default_w: float,
    default_h: float,
    start_size: float,
    min_size: float,
    hand: bool = False,
    bold: bool = False,
    spacing: float = 3,
    wrap: bool = True,
) -> tuple:
    """Measure how large *text* needs to be rendered and return fitted dimensions.

    Runs ``fit_text`` to find the optimal font size, then compares the measured
    text bounds against the default box.  If the text overflows, the box is
    expanded to fit.

    Args:
        draw:       PIL draw object (1×1 dummy is sufficient).
        text:       Text to measure.
        default_w:  Nominal box width in logical pixels.
        default_h:  Nominal box height in logical pixels.
        start_size: Maximum font size to try.
        min_size:   Minimum acceptable font size.
        hand:       Use hand-written font.
        bold:       Use bold font.
        spacing:    Inter-line spacing.
        wrap:       Allow text wrapping.

    Returns:
        ``(fitted_text, fitted_size, final_w, final_h)`` — all in logical px.
    """
    raw_text = str(text)
    fitted_text, fitted_size, fitted_font = fit_text(
        draw, raw_text, default_w, default_h, start_size,
        min_size=min_size, hand=hand, bold=bold, spacing=spacing, wrap=wrap,
    )
    tw, th = text_size(draw, fitted_text, fitted_font, spacing=spacing)
    unscaled_tw = tw / SCALE
    unscaled_th = th / SCALE
    if unscaled_tw <= default_w and unscaled_th <= default_h:
        return fitted_text, fitted_size, default_w, default_h
    return fitted_text, fitted_size, max(default_w, unscaled_tw), max(default_h, unscaled_th)


# ---------------------------------------------------------------------------
# Per-card-type layout functions
# ---------------------------------------------------------------------------
def layout_core_card(draw: ImageDraw.ImageDraw, card: dict) -> dict:
    """Measure a core pipeline card and return its fitted layout dict.

    Args:
        draw: PIL draw object for text measurement.
        card: Spec dict with optional "title", "body", "icon", "color" keys.

    Returns:
        Layout dict with keys: w, h, title_txt/sz/w/h, body_txt/sz/w/h, icon, color.
    """
    title = card.get("title", "")
    body  = card.get("body", "")
    title_txt, title_sz, title_w, title_h = layout_text_fit(draw, title, 100, 28, 20, 15, hand=True, bold=True)
    body_txt,  body_sz,  body_w,  body_h  = layout_text_fit(draw, body,  150, 38, 14, 11)
    extra_w = max(0, title_w - 100, body_w - 150)
    extra_h = max(0, (title_h - 28) + (body_h - 38))
    return {
        "w": 260 + extra_w, "h": 90 + extra_h,
        "title_txt": title_txt, "title_sz": title_sz,
        "title_w": 100 + extra_w, "title_h": title_h,
        "body_txt":  body_txt,  "body_sz":  body_sz,
        "body_w": 150 + extra_w, "body_h": body_h,
        "icon": card.get("icon", "file"),
        "color": card.get("color", THEME["cyan"]),
    }


def layout_mini_card(draw: ImageDraw.ImageDraw, card: dict, base_w: float, base_h: float) -> dict:
    """Measure a mini card (used in left/right panels).

    Args:
        draw:   PIL draw object.
        card:   Spec dict.
        base_w: Default card width in logical pixels.
        base_h: Default card height in logical pixels.

    Returns:
        Layout dict.
    """
    title = card.get("title", "")
    body  = card.get("body", "")
    title_txt, title_sz, title_w, title_h = layout_text_fit(draw, title, 115, 24, 17, 13, bold=True)
    body_w_base = base_w - 92
    body_h_base = base_h - 43
    body_txt, body_sz, body_w, body_h = layout_text_fit(draw, body, body_w_base, body_h_base, 12, 11)
    extra_w = max(0, title_w - 115, body_w - body_w_base)
    extra_h = max(0, (title_h - 24) + (body_h - body_h_base))
    return {
        "w": base_w + extra_w, "h": base_h + extra_h,
        "title_txt": title_txt, "title_sz": title_sz,
        "title_w": 115 + extra_w, "title_h": title_h,
        "body_txt":  body_txt,  "body_sz":  body_sz,
        "body_w": body_w_base + extra_w, "body_h": body_h,
        "icon": card.get("icon", "file"),
        "color": card.get("color", THEME["cyan"]),
    }


def layout_pack_row(draw: ImageDraw.ImageDraw, card: dict) -> dict:
    """Measure a pack row card (used in the right panel).

    Args:
        draw: PIL draw object.
        card: Spec dict.

    Returns:
        Layout dict.
    """
    title = card.get("title", "")
    body  = card.get("body", "")
    title_txt, title_sz, title_w, title_h = layout_text_fit(draw, title, 120, 25, 17, 13, bold=True)
    body_txt,  body_sz,  body_w,  body_h  = layout_text_fit(draw, body,  135, 40, 12, 11)
    extra_w = max(0, title_w - 120, body_w - 135)
    extra_h = max(0, (title_h - 25) + (body_h - 40))
    return {
        "w": 228 + extra_w, "h": 92 + extra_h,
        "title_txt": title_txt, "title_sz": title_sz,
        "title_w": 120 + extra_w, "title_h": title_h,
        "body_txt":  body_txt,  "body_sz":  body_sz,
        "body_w": 135 + extra_w, "body_h": body_h,
        "icon": card.get("icon", "file"),
        "color": card.get("color", THEME["cyan"]),
    }


def layout_layer_card(draw: ImageDraw.ImageDraw, card: dict) -> dict:
    """Measure a layer card (used in the centre panel).

    Args:
        draw: PIL draw object.
        card: Spec dict.

    Returns:
        Layout dict.
    """
    title = card.get("title", "")
    body  = card.get("body", "")
    title_txt, title_sz, title_w, title_h = layout_text_fit(draw, title, 92, 25, 18, 13, bold=True)
    body_txt,  body_sz,  body_w,  body_h  = layout_text_fit(draw, body,  96, 36, 11, 10)
    extra_w = max(0, title_w - 92, body_w - 96)
    extra_h = max(0, (title_h - 25) + (body_h - 36))
    return {
        "w": 112 + extra_w, "h": 150 + extra_h,
        "title_txt": title_txt, "title_sz": title_sz,
        "title_w": 92 + extra_w, "title_h": title_h,
        "body_txt":  body_txt,  "body_sz":  body_sz,
        "body_w": 96 + extra_w, "body_h": body_h,
        "icon": card.get("icon", "file"),
        "color": card.get("color", THEME["cyan"]),
    }
