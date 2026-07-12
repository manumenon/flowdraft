#!/usr/bin/env python3
"""
render_flowdraft_diagram.py — public façade (backward-compatibility shim).

All rendering logic lives in ``scripts/flowdraft/``.  This file re-exports
every public symbol so that the existing test suite — which does::

    import scripts.render_flowdraft_diagram as render_flowdraft_diagram

— continues to work without any changes.

New code should import directly from the ``flowdraft`` sub-modules, e.g.::

    from scripts.flowdraft.render import render_static, premium_finish
    from scripts.flowdraft.constants import THEME, set_theme
"""

# ---------------------------------------------------------------------------
# Ensure the project root is on sys.path so `from scripts.flowdraft...` works
# whether this file is imported as a module OR run directly as a subprocess.
# ---------------------------------------------------------------------------
import sys
import types
from pathlib import Path

_project_root = str(Path(__file__).resolve().parents[1])
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


# ---------------------------------------------------------------------------
# Re-export every public symbol from the flowdraft package
# ---------------------------------------------------------------------------
from scripts.flowdraft.constants import (       # noqa: F401, F403
    DEFAULT_W, DEFAULT_H, DEFAULT_FRAMES, DEFAULT_FPS, SCALE, UPDATED,
    SCALE_X, SCALE_Y,
    THEME, DEFAULT_DARK_THEME,
    set_theme,
)
from scripts.flowdraft.color import (           # noqa: F401, F403
    hex_rgba, c, scaled_box, adjust_color,
)
from scripts.flowdraft.fonts import (           # noqa: F401, F403
    EMERGENCY_MIN_TEXT_SIZE,
    font_candidates, load_font, has_cjk, text_size,
)
from scripts.flowdraft.text import (            # noqa: F401, F403
    wrap_token, wrap_line, wrap_text,
    text_variants, fit_text,
    draw_text,
)
from scripts.flowdraft.geometry import (        # noqa: F401, F403
    path_len, point_at_distance, point_at_fraction, arrow_head,
)
from scripts.flowdraft.excal import Excal       # noqa: F401
from scripts.flowdraft.drawing import (         # noqa: F401, F403
    draw_rect, draw_ellipse, draw_line, draw_diamond,
    icon, draw_signature,
)
from scripts.flowdraft.svg import (             # noqa: F401, F403
    excalidraw_to_svg,
)
from scripts.flowdraft.layout import (          # noqa: F401, F403
    CollisionRegistry,
    layout_text_fit, layout_core_card, layout_mini_card,
    layout_pack_row, layout_layer_card,
)
from scripts.flowdraft.components import (      # noqa: F401, F403
    brand, small_input, core_card, mini_card, pack_row,
)
from scripts.flowdraft.animation import (       # noqa: F401, F403
    draw_glow_dot, pulse_rect, animate_frame,
)
from scripts.flowdraft.render import (          # noqa: F401, F403
    render_static, premium_finish,
)
from scripts.flowdraft.pipeline import (        # noqa: F401, F403
    apply_rebranding,
    write_outputs, frame_diff_report, check_outputs,
    main,
)

# ---------------------------------------------------------------------------
# Live proxy for SCALE_X / SCALE_Y
#
# Tests written against the original single-file module do:
#
#   renderer.SCALE_X = 2.0          # write – set a test scale factor
#   scale_x = renderer.SCALE_X      # read  – verify render_static updated it
#
# In the original single-file code SCALE_X/Y were plain module globals shared
# across all functions. After splitting into sub-modules, the live source of
# truth is scripts.flowdraft.constants.SCALE_X/Y. We need:
#
#   * Every READ  of renderer.SCALE_X  -> return _flowdraft_constants.SCALE_X
#   * Every WRITE of renderer.SCALE_X  -> propagate to _flowdraft_constants
#
# __getattr__ only fires on attribute misses (i.e. not in __dict__), so we
# must use __getattribute__ to intercept EVERY read for these two names.
# ---------------------------------------------------------------------------
import scripts.flowdraft.constants as _flowdraft_constants  # noqa: E402

# Keep as a class-level frozenset to avoid __getattribute__ recursion.
_PROXY_NAMES = frozenset({"SCALE_X", "SCALE_Y"})


class _FacadeModule(types.ModuleType):
    """ModuleType subclass whose SCALE_X/SCALE_Y always proxy the constants."""

    # Class-level constant -- accessible via object.__getattribute__ without
    # touching the instance __dict__ or triggering our override.
    _PROXY_NAMES = _PROXY_NAMES

    def __getattribute__(self, name: str):
        # object.__getattribute__ reads class attrs without recursion.
        if name in object.__getattribute__(self, "_PROXY_NAMES"):
            return getattr(_flowdraft_constants, name)
        return super().__getattribute__(name)

    def __setattr__(self, name: str, value):
        if name in _PROXY_NAMES:
            # Propagate to the constants module so every sub-module that does
            # `_c.SCALE_X` sees the updated value immediately.
            setattr(_flowdraft_constants, name, value)
            # Do NOT write to __dict__ -- keep __getattribute__ redirecting
            # to _flowdraft_constants on every read.
        else:
            super().__setattr__(name, value)


# Replace this module's entry in sys.modules with the proxy subclass instance.
_this_module = sys.modules[__name__]
_proxy_module = _FacadeModule(__name__, __doc__)
_proxy_module.__dict__.update(_this_module.__dict__)
sys.modules[__name__] = _proxy_module

# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    main()
