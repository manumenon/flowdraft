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
def draw_glow_dot(
    draw: ImageDraw.ImageDraw,
    x: float,
    y: float,
    color: str,
    strength: float = 1.0,
    size_factor: float = 1.0,
) -> None:
    """Draw a 4-layer concentric glow dot at ``(x, y)`` with dynamic size factor."""
    # Scale radii by size_factor
    for radius, alpha in [(12, 15), (8, 40), (5, 95), (2, 200)]:
        a = int(alpha * strength)
        r = radius * size_factor
        draw.ellipse((x - r, y - r, x + r, y + r), fill=hex_rgba(color, a))
    # Tiny bright white centre sparkle
    draw.ellipse((x - 1, y - 1, x + 1, y + 1), fill=hex_rgba(THEME["white"], min(255, int(245 * strength))))


def ease_in_out_quad(t: float) -> float:
    """Standard ease-in-out quadratic easing function."""
    if t < 0.5:
        return 2.0 * t * t
    else:
        return 1.0 - ((-2.0 * t + 2.0) ** 2.0) / 2.0


def hex_to_rgb(h: str) -> tuple[int, int, int]:
    """Convert hex string to RGB tuple."""
    h = h.lstrip('#')
    if len(h) == 6:
        return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
    return (255, 255, 255)


def interpolate_color(color1: str, color2: str, factor: float) -> str:
    """Interpolate between two hex colors based on factor [0, 1]."""
    r1, g1, b1 = hex_to_rgb(color1)
    r2, g2, b2 = hex_to_rgb(color2)
    r = int(r1 + (r2 - r1) * factor)
    g = int(g1 + (g2 - g1) * factor)
    b = int(b1 + (b2 - b1) * factor)
    return f"#{r:02x}{g:02x}{b:02x}"


def pulse_rect(
    draw: ImageDraw.ImageDraw,
    rect: tuple,
    color: str,
    glow_val: float,
    radius: float = 10,
) -> None:
    """Draw concentric pulsing outlines around a bounding box driven by glow_val.

    Args:
        draw:     PIL ImageDraw object.
        rect:     ``(x1, y1, x2, y2)`` bounding box in physical pixels.
        color:    Hex colour for the pulse outlines.
        glow_val: Eased value [0, 1] representing the pulse phase.
        radius:   Corner radius for the rounded outlines.
    """
    x1, y1, x2, y2 = rect
    alpha = int(30 + 110 * glow_val)
    for grow, width in [(0, 2), (4, 2), (8, 1)]:
        grow_scaled = grow * glow_val
        draw.rounded_rectangle(
            (x1 - grow_scaled, y1 - grow_scaled, x2 + grow_scaled, y2 + grow_scaled),
            radius=radius + grow_scaled,
            outline=hex_rgba(color, max(15, int(alpha - grow * 8))),
            width=width,
        )


# ---------------------------------------------------------------------------
# Frame compositor
# ---------------------------------------------------------------------------
def animate_frame(base: Image.Image, idx: int, total: int, spec: dict = None) -> Image.Image:
    """Composite one animation frame onto *base* with temporal interpolation.

    Draws:
    - Comets with dynamic opacity, size, and color interpolation.
    - Pulsing panel outlines driven by easing functions.
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

    # Fetch temporal variables
    canvas_meta = spec.get("canvas", {})
    fps = canvas_meta.get("fps", 30.0)
    duration = canvas_meta.get("duration", 3.0)
    speed = canvas_meta.get("speed", 1.0)
    t_seconds = idx / fps if fps > 0 else 0.0

    # Remap colours for white/light theme so dots pop on bright backgrounds
    _anim_remap = {
        THEME.get("green",        ""): THEME.get("_anim_green",  THEME.get("green",  "")),
        THEME.get("cyan",         ""): THEME.get("_anim_cyan",   THEME.get("cyan",   "")),
        THEME.get("purple",       ""): THEME.get("_anim_purple", THEME.get("purple", "")),
        THEME.get("amber",        ""): THEME.get("_anim_amber",  THEME.get("amber",  "")),
        THEME.get("white",        ""): THEME.get("_anim_white",  THEME.get("white",  "")),
        THEME.get("core_stroke",  ""): THEME.get("_anim_cyan",   THEME.get("core_stroke", "")),
    }

    # Animate comets
    for points, color, offset in paths:
        dot_color = _anim_remap.get(color, color)
        
        # Color interpolation factor driven by time
        color_cycle = 0.5 + 0.5 * math.sin(2.0 * math.pi * progress * speed + offset)
        interpolated_color = interpolate_color(dot_color, THEME.get("white", "#ffffff"), color_cycle * 0.4)
        
        # Size factor driven by time
        size_factor = 0.85 + 0.3 * (0.5 + 0.5 * math.sin(2.0 * math.pi * progress * speed * 2.0 + offset))

        # Comet tail parts
        for trail, base_strength in [(0, 1.0), (-0.030, 0.68), (-0.058, 0.42), (-0.086, 0.22)]:
            # Opacity variation over time
            opacity_factor = 0.8 + 0.2 * math.sin(2.0 * math.pi * progress * speed * 3.0 + trail)
            strength = base_strength * opacity_factor
            
            x, y = point_at_fraction(points, progress + offset + trail)
            draw_glow_dot(draw, x, y, interpolated_color, strength, size_factor)

    # Animate panel glows simultaneously but with staggered phases using easing functions
    pulse_targets = spec.get("_resolved_pulse_targets", [])
    num_targets = len(pulse_targets)
    
    if num_targets > 0:
        for pos, (rect, color) in enumerate(pulse_targets):
            # Phase staggered per panel
            panel_progress = (progress * speed + pos / num_targets) % 1.0
            glow_val = ease_in_out_quad(0.5 + 0.5 * math.sin(2.0 * math.pi * panel_progress))
            pulse_rect(draw, rect, color, glow_val, int(round(12 * min(SCALE_X, SCALE_Y))))

    frame.alpha_composite(overlay)
    return frame.convert("RGB")

