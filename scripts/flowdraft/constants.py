"""
flowdraft.constants
-------------------
Global rendering constants, the active THEME dict, and the set_theme() function.
"""

# ---------------------------------------------------------------------------
# Canvas / scale defaults
# ---------------------------------------------------------------------------
DEFAULT_W      = 1210
DEFAULT_H      = 1138
DEFAULT_FRAMES = 41
DEFAULT_FPS    = 20
SCALE          = 2          # hi-DPI: every logical pixel becomes 2 physical pixels
UPDATED        = 1782475200000  # Excalidraw element timestamp

# Dynamic scale factors (set by render_static based on canvas size in spec)
SCALE_X = 1.0
SCALE_Y = 1.0
HAND    = True

# ---------------------------------------------------------------------------
# Dark (default) theme
# ---------------------------------------------------------------------------
THEME: dict = {
    "bg":           "#000000",
    "white":        "#f4f0ee",
    "muted":        "#cfc7c5",
    "frame":        "#5c6265",
    "core_fill":    "#04171e",
    "core_stroke":  "#1d8be8",
    "green":        "#22c86f",
    "green_fill":   "#02160a",
    "purple":       "#bd54d3",
    "purple_fill":  "#120814",
    "cyan":         "#7ee3d6",
    "blue_fill":    "#081626",
    "highlight":    "#124238",
    "amber":        "#f4b64e",
    "pink":         "#ff7ab6",
    "archive_fill": "#080711",
    "source_fill":  "#02160a",
    "pack_fill":    "#04180d",
}

# Snapshot of the dark theme used for reset
DEFAULT_DARK_THEME: dict = THEME.copy()


# ---------------------------------------------------------------------------
# Theme switching
# ---------------------------------------------------------------------------
def set_theme(theme_name: str) -> None:
    """Switch the global THEME in-place.

    Args:
        theme_name: "dark" | "light" | "white"
    """
    global THEME
    if theme_name in ("light", "white"):
        THEME.update({
            # --- Base colours ---
            "bg":           "#ffffff",
            "white":        "#111827",
            "muted":        "#4b5563",
            "frame":        "#6b7280",   # contrast ~4.6:1 on white — WCAG 3.0:1 pass
            # --- Panel fills: stronger tints so cards read clearly on white ---
            "core_fill":    "#dbeafe",
            "core_stroke":  "#0284c7",   # kept for test contract compatibility
            "green":        "#15803d",
            "green_fill":   "#dcfce7",
            "purple":       "#7c3aed",
            "purple_fill":  "#ede9fe",
            "cyan":         "#0891b2",
            "blue_fill":    "#dbeafe",
            "highlight":    "#99f6e4",
            "amber":        "#b45309",
            "pink":         "#be185d",
            "archive_fill": "#ede9fe",
            "source_fill":  "#dcfce7",
            "pack_fill":    "#d1fae5",
            # --- White-theme animation colours (deeper/saturated for light bg) ---
            "_anim_green":  "#059669",
            "_anim_cyan":   "#0284c7",
            "_anim_purple": "#7c3aed",
            "_anim_amber":  "#d97706",
            "_anim_white":  "#374151",
        })
    elif theme_name == "dark":
        THEME.update(DEFAULT_DARK_THEME)
