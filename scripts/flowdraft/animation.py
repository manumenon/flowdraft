"""
flowdraft.animation
-------------------
Per-frame animation helpers: glow dot particles, pulsing panel outlines,
and the ``animate_frame`` compositor.
"""

import math

from PIL import Image, ImageDraw

from .constants import THEME
from . import constants as _c  # live attribute access; never bind SCALE_X/Y at import time
from .color import hex_rgba
from .geometry import point_at_fraction


# ---------------------------------------------------------------------------
# Particle effects
# ---------------------------------------------------------------------------
def draw_glow_dot(draw: ImageDraw.ImageDraw, x: float, y: float, color: str, strength: float = 1.0) -> None:
    """Draw a 4-layer concentric glow dot at ``(x, y)``.

    The layers radiate outward from a bright white centre spark, creating a
    subtle, clean moving indicator suitable for professional workflows.
    """
    # Subtle compact layers to prevent oversized lens flares
    for radius, alpha in [(12, 15), (8, 40), (5, 95), (2, 200)]:
        a = int(alpha * strength)
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=hex_rgba(color, a))
    # Tiny bright white centre sparkle
    draw.ellipse((x - 1, y - 1, x + 1, y + 1), fill=hex_rgba(THEME["white"], min(255, int(245 * strength))))


def pulse_rect(
    draw: ImageDraw.ImageDraw,
    rect: tuple,
    color: str,
    phase: float,
    radius: float = 10,
) -> None:
    """Draw three concentric pulsing outlines around a bounding box.

    The pulse amplitude is driven by a sine wave keyed to *phase* so that
    the brightness oscillates smoothly over time.

    Args:
        draw:   PIL ImageDraw object.
        rect:   ``(x1, y1, x2, y2)`` bounding box in physical pixels.
        color:  Hex colour for the pulse outlines.
        phase:  Current animation phase in radians.
        radius: Corner radius for the rounded outlines.
    """
    x1, y1, x2, y2 = rect
    alpha = int(70 + 70 * (0.5 + 0.5 * math.sin(phase)))
    for grow, width in [(0, 2), (4, 2), (8, 1)]:
        draw.rounded_rectangle(
            (x1 - grow, y1 - grow, x2 + grow, y2 + grow),
            radius=radius + grow,
            outline=hex_rgba(color, max(25, alpha - grow * 8)),
            width=width,
        )


# ---------------------------------------------------------------------------
# Frame compositor
# ---------------------------------------------------------------------------
def animate_frame(base: Image.Image, idx: int, total: int, spec: dict = None) -> Image.Image:
    """Composite one animation frame onto *base*.

    Draws:
    - A 4-comet trailing particle on each flow path.
    - A pulsing outline on the currently active panel.

    If *spec* contains ``_resolved_paths`` and ``_resolved_pulse_targets``
    (written by ``render_static``), those are used.  Otherwise hardcoded
    fallback paths are used (for standalone/test usage).

    Args:
        base:  The static, post-processed base image (RGB PIL Image).
        idx:   Current frame index (0-based).
        total: Total number of frames in the loop.
        spec:  Optional spec dict with ``_resolved_paths`` and
               ``_resolved_pulse_targets``.

    Returns:
        A composited RGB PIL Image for this frame.
    """
    frame   = base.convert("RGBA")
    overlay = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    draw    = ImageDraw.Draw(overlay)
    progress = idx / total if total > 0 else 0.0

    # Refresh SCALE_X/Y from the live constants (updated by render_static)
    SCALE_X = _c.SCALE_X
    SCALE_Y = _c.SCALE_Y

    if spec is None:
        spec = {}
    paths = spec.get("_resolved_paths", [])

    # Remap colours for white/light theme so dots pop on bright backgrounds
    _anim_remap = {
        THEME.get("green",        ""): THEME.get("_anim_green",  THEME.get("green",  "")),
        THEME.get("cyan",         ""): THEME.get("_anim_cyan",   THEME.get("cyan",   "")),
        THEME.get("purple",       ""): THEME.get("_anim_purple", THEME.get("purple", "")),
        THEME.get("amber",        ""): THEME.get("_anim_amber",  THEME.get("amber",  "")),
        THEME.get("white",        ""): THEME.get("_anim_white",  THEME.get("white",  "")),
        THEME.get("core_stroke",  ""): THEME.get("_anim_cyan",   THEME.get("core_stroke", "")),
    }

    for points, color, offset in paths:
        dot_color = _anim_remap.get(color, color)
        # 4-copy comet tail: head + 3 ghosts at decreasing strength
        for trail, strength in [(0, 1.0), (-0.030, 0.68), (-0.058, 0.42), (-0.086, 0.22)]:
            x, y = point_at_fraction(points, progress + offset + trail)
            draw_glow_dot(draw, x, y, dot_color, strength)

    pulse_targets = spec.get("_resolved_pulse_targets", [])

    if len(pulse_targets) > 0:
        active = (idx // 6) % len(pulse_targets)
        for pos, (rect, color) in enumerate(pulse_targets):
            if pos == active:
                pulse_rect(draw, rect, color, progress * math.tau * 2, int(round(12 * min(SCALE_X, SCALE_Y))))

    frame.alpha_composite(overlay)
    return frame.convert("RGB")
