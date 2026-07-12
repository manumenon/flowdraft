"""
flowdraft.color
---------------
Colour conversion utilities and the light-mode colour remapping table.
"""

from .constants import THEME, SCALE


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------
def hex_rgba(value: str, alpha: int = 255) -> tuple:
    """Convert a ``#RRGGBB`` hex string to an (R, G, B, A) tuple."""
    if not value or not isinstance(value, str):
        return (0, 0, 0, alpha)
    val = value.lstrip("#")
    if len(val) == 6 and all(c in "0123456789abcdefABCDEF" for c in val):
        try:
            return tuple(int(val[i: i + 2], 16) for i in (0, 2, 4)) + (alpha,)
        except ValueError:
            pass
    # Default fallback
    return (0, 0, 0, alpha)


def c(v: float) -> int:
    """Scale a logical coordinate to a physical (hi-DPI) pixel coordinate."""
    return int(round(v * SCALE))


def scaled_box(x: float, y: float, w: float, h: float) -> tuple:
    """Return a PIL bounding-box tuple ``(x0, y0, x1, y1)`` in physical pixels."""
    return (c(x), c(y), c(x + w), c(y + h))


# ---------------------------------------------------------------------------
# Theme-aware colour remapping
# ---------------------------------------------------------------------------
def adjust_color(color: str) -> str:
    """Remap a dark-theme colour to its light-theme equivalent.

    When the active theme background is white (``THEME["bg"] == "#ffffff"``),
    every dark fill/stroke is translated to the corresponding light-theme value.
    In dark mode the colour is returned unchanged.

    Args:
        color: A ``#RRGGBB`` hex string (or any value).

    Returns:
        The remapped hex string, or *color* unchanged.
    """
    if not color:
        return color
    color_lower = color.lower()
    if THEME["bg"] == "#ffffff":
        mappings = {
            "#000000": THEME["bg"],
            "#f4f0ee": THEME["white"],
            "#cfc7c5": THEME["muted"],
            "#5c6265": THEME["frame"],
            "#04171e": THEME["core_fill"],
            "#1d8be8": THEME["core_stroke"],
            "#22c86f": THEME["green"],
            "#02160a": THEME["green_fill"],
            "#bd54d3": THEME["purple"],
            "#120814": THEME["purple_fill"],
            "#7ee3d6": THEME["cyan"],
            "#081626": THEME["blue_fill"],
            "#124238": THEME["highlight"],
            "#f4b64e": THEME["amber"],
            "#ff7ab6": THEME["pink"],
            "#080711": THEME["archive_fill"],
            "#04180d": THEME["pack_fill"],
            "#04200f": THEME["green_fill"],
            "#17091d": THEME["purple_fill"],
            "#052515": THEME["green_fill"],
        }
        return mappings.get(color_lower, color)
    return color
