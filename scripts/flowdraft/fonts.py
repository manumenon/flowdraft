"""
flowdraft.fonts
---------------
Font discovery, loading, CJK detection, and text measurement.
"""

from PIL import ImageFont, ImageDraw
import functools

from .color import c

# Minimum text size guaranteed to render even when a box is too small for the
# requested size.  Lower than this and text is unreadable.
EMERGENCY_MIN_TEXT_SIZE = 6


# ---------------------------------------------------------------------------
# Font discovery
# ---------------------------------------------------------------------------
def font_candidates(hand: bool = False, cjk: bool = False, bold: bool = False) -> list:
    """Return an ordered list of font paths/names to try for the given style.

    The renderer tries each candidate with ``ImageFont.truetype``; the first
    one that loads successfully is used.  Falling back through the list ensures
    cross-platform compatibility (macOS → Windows → Linux).

    Args:
        hand:  Return hand-written / cursive font candidates.
        cjk:   Return CJK (Chinese/Japanese/Korean) font candidates.
        bold:  Prefer bold variants where available.

    Returns:
        A list of font path strings or family name strings.
    """
    from . import constants as _c
    if not getattr(_c, "HAND", True):
        hand = False

    if hand:
        return [
            "/System/Library/Fonts/Supplemental/Chalkduster.ttf",
            "/System/Library/Fonts/MarkerFelt.ttc",
            "/System/Library/Fonts/Noteworthy.ttc",
            "/System/Library/Fonts/Supplemental/Bradley Hand Bold.ttf",
            "comic.ttf",
            "segoepr.ttf",
            "Comic Sans MS",
        ]
    if cjk:
        return [
            "/System/Library/Fonts/STHeiti Medium.ttc" if bold else "/System/Library/Fonts/STHeiti Light.ttc",
            "/System/Library/Fonts/Hiragino Sans GB.ttc",
            "/Library/Fonts/Arial Unicode.ttf",
            "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
            "msyh.ttc",
            "simsun.ttc",
            "Noto Sans CJK SC",
            "Noto Sans CJK JP",
            "wqy-microhei.ttc",
        ]
    return [
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "arial.ttf",
        "Arial",
        "LiberationSans-Regular.ttf",
        "DejaVuSans.ttf",
    ]


@functools.lru_cache(maxsize=128)
def load_font(size: float, hand: bool = False, cjk: bool = False, bold: bool = False):
    """Load the best available font for the given style at *size* logical px.

    Args:
        size: Logical (pre-scale) font size in pixels.
        hand: Load a hand-written font.
        cjk:  Load a CJK-capable font.
        bold: Prefer bold variants.

    Returns:
        A PIL ``ImageFont`` object.
    """
    for path in font_candidates(hand=hand, cjk=cjk, bold=bold):
        try:
            return ImageFont.truetype(path, c(size))
        except OSError:
            continue
    return ImageFont.load_default()


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------
def has_cjk(text: str) -> bool:
    """Return True if *text* contains any CJK Unified Ideograph, Japanese or Korean characters."""
    if text is None:
        text = ""
    return any(
        ("\u3400" <= ch <= "\u9fff") or
        ("\u3040" <= ch <= "\u30ff") or
        ("\uac00" <= ch <= "\ud7a3")
        for ch in text
    )


def text_size(draw: ImageDraw.ImageDraw, text: str, font, spacing: float = 3) -> tuple:
    """Return ``(width, height)`` of *text* rendered with *font*.

    Args:
        draw:    A PIL ``ImageDraw`` instance (used for measurement only).
        text:    The string to measure.
        font:    A PIL font object.
        spacing: Inter-line spacing in logical pixels.

    Returns:
        A ``(width, height)`` tuple in **physical** pixels.
    """
    if not text:
        return 0, 0
    box = draw.multiline_textbbox((0, 0), text, font=font, spacing=c(spacing))
    return box[2] - box[0], box[3] - box[1]
