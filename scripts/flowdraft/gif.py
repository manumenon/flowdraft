"""
flowdraft.gif
-------------
GIF output animation helpers and comet tail particle motion evaluation.
"""

import math
from PIL import Image

from .animation import animate_frame


def fix_comet_position(pos: float) -> float:
    """Fix negative modulo evaluation for comet tail particles (e.g. (-0.030) % 1.0 = 0.970).

    In Python, negative modulo evaluation like (-0.030) % 1.0 evaluates to 0.970,
    which causes comet tail particles to teleport to the end of the path at the start
    of the animation loop. This function clamps negative positions to 0.0 or wraps
    positive positions via modulo 1.0, ensuring smooth continuous particle motion.
    """
    if pos < 0.0:
        return max(0.0, pos)
    return pos % 1.0


def render_gif_frames(base_img: Image.Image, num_frames: int, spec: dict = None) -> list[Image.Image]:
    """Generate all animated GIF frames using animate_frame compositor."""
    if spec is None:
        spec = {}
    return [animate_frame(base_img, i, num_frames, spec) for i in range(num_frames)]
