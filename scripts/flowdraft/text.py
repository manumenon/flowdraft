"""
flowdraft.text
--------------
Text wrapping, auto-sizing (fit_text), and the draw_text() rendering call that
writes to both the PIL canvas and the Excalidraw JSON model simultaneously.
"""

from PIL import ImageDraw

from .constants import THEME
from .color import hex_rgba, c, adjust_color
from .fonts import (
    EMERGENCY_MIN_TEXT_SIZE,
    has_cjk,
    load_font,
    text_size,
)


# ---------------------------------------------------------------------------
# Text wrapping
# ---------------------------------------------------------------------------
def wrap_token(draw: ImageDraw.ImageDraw, token: str, font, max_width: float) -> list:
    """Break a single token (word) at character boundaries to fit *max_width*.

    Args:
        draw:      PIL draw object for measurement.
        token:     A single word / CJK character sequence.
        font:      PIL font object.
        max_width: Maximum pixel width (physical px).

    Returns:
        A list of sub-strings that each fit within *max_width*.
    """
    if not token:
        return [token]
    parts = []
    current = ""
    for char in token:
        candidate = current + char
        if current and text_size(draw, candidate, font)[0] > max_width:
            parts.append(current)
            current = char
        else:
            current = candidate
    if current:
        parts.append(current)
    return parts


def wrap_line(draw: ImageDraw.ImageDraw, line: str, font, max_width: float) -> list:
    """Wrap a single line of text to fit *max_width*, respecting CJK boundaries.

    Args:
        draw:      PIL draw object for measurement.
        line:      One line of text (no newlines).
        font:      PIL font object.
        max_width: Maximum pixel width (physical px).

    Returns:
        A list of wrapped line strings.
    """
    if not line:
        return [line]
    if has_cjk(line):
        KINK_START = set("）｝]｝,.}。，、？！?”’»)]｝")
        KINK_END = set("（｛[“‘«([｛")
        tokens = []
        current_group = ""
        for char in line:
            if char == " ":
                if current_group:
                    tokens.append(current_group)
                    current_group = ""
                tokens.append(" ")
            elif ("\u3400" <= char <= "\u9fff") or ("\u3040" <= char <= "\u30ff") or ("\uac00" <= char <= "\ud7a3"):
                if current_group:
                    tokens.append(current_group)
                    current_group = ""
                tokens.append(char)
            elif char in KINK_START:
                if current_group:
                    current_group += char
                elif tokens:
                    if tokens[-1] == " ":
                        if len(tokens) > 1:
                            tokens[-2] += char
                        else:
                            tokens.append(char)
                    else:
                        tokens[-1] += char
                else:
                    tokens.append(char)
            elif char in KINK_END:
                if current_group:
                    tokens.append(current_group)
                    current_group = ""
                tokens.append(char)
            else:
                current_group += char
        if current_group:
            tokens.append(current_group)
        separator = ""
    else:
        tokens = line.split(" ")
        separator = " "

    lines = []
    current = ""
    for token in tokens:
        candidate = token if not current else current + separator + token
        if text_size(draw, candidate, font)[0] <= max_width:
            current = candidate
            continue
        if current:
            lines.append(current)
        if text_size(draw, token, font)[0] <= max_width:
            current = token
        else:
            split_parts = wrap_token(draw, token, font, max_width)
            lines.extend(split_parts[:-1])
            current = split_parts[-1] if split_parts else ""
    if current:
        lines.append(current)
    return lines


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font, max_width: float) -> str:
    """Wrap multi-line text to fit *max_width*, preserving existing newlines.

    Args:
        draw:      PIL draw object for measurement.
        text:      Input text (may contain newlines).
        font:      PIL font object.
        max_width: Maximum pixel width (physical px).

    Returns:
        A newline-separated string of wrapped lines.
    """
    lines = []
    for raw_line in str(text).splitlines() or [""]:
        lines.extend(wrap_line(draw, raw_line, font, max_width))
    return "\n".join(lines)


def text_variants(draw: ImageDraw.ImageDraw, text: str, font, max_width: float, wrap: bool) -> list:
    """Return candidate text strings to try during fit_text iteration.

    If *wrap* is enabled, the first candidate is the wrapped version; the
    second is the unwrapped original (so the caller can try without wrapping
    if the wrapped form still doesn't fit).

    Args:
        draw:      PIL draw object.
        text:      Raw text string.
        font:      PIL font object.
        max_width: Maximum pixel width.
        wrap:      Whether to include wrapped variants.

    Returns:
        A list of candidate strings (1 or 2 items).
    """
    raw = str(text)
    if not wrap:
        return [raw]
    wrapped = wrap_text(draw, raw, font, max_width)
    if wrapped == raw:
        return [wrapped]
    return [wrapped, raw]


# ---------------------------------------------------------------------------
# Auto-sizing
# ---------------------------------------------------------------------------
def fit_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    w: float,
    h: float,
    size: float,
    min_size: float = 10,
    hand: bool = False,
    bold: bool = False,
    spacing: float = 3,
    wrap: bool = True,
    allow_grow: bool = False,
) -> tuple:
    """Reduce font size until *text* fits inside a ``w × h`` box.

    Iterates from *size* down to ``max(min_size, EMERGENCY_MIN_TEXT_SIZE)``.
    For each candidate size it tries all ``text_variants``.  The first
    ``(text, size, font)`` triple that fits is returned; if nothing fits,
    the emergency minimum size is used and the text is hard-wrapped.

    Args:
        draw:       PIL draw object for measurement.
        text:       The string to fit.
        w:          Box width in logical pixels.
        h:          Box height in logical pixels.
        size:       Starting (maximum) font size.
        min_size:   Minimum font size before emergency fallback.
        hand:       Use hand-written font.
        bold:       Use bold font.
        spacing:    Inter-line spacing in logical pixels.
        wrap:       Allow text wrapping.
        allow_grow: Allow text box height to exceed h (for auto-growing boxes).

    Returns:
        ``(fitted_text, fitted_size, fitted_font)``
    """
    raw_text = str(text)[:1000]
    has_cjk_text = has_cjk(raw_text)
    max_width = c(w)
    max_height = c(h)
    
    # Apply a safety margin to ensure text wraps before hitting edges
    effective_max_width = max(c(min_size), max_width - 12)
    effective_max_height = max(c(min_size), max_height - 6)
    
    start_size = max(1, int(size))
    emergency_min = max(1, min(start_size, int(min_size), EMERGENCY_MIN_TEXT_SIZE))

    low = emergency_min
    high = start_size
    best_fit = None

    while low <= high:
        mid = (low + high) // 2
        candidate_font = load_font(
            mid,
            hand=hand and not has_cjk_text,
            cjk=has_cjk_text,
            bold=bold,
        )
        fits = False
        for candidate_text in text_variants(draw, raw_text, candidate_font, effective_max_width, wrap):
            tw, th = text_size(draw, candidate_text, candidate_font, spacing=spacing)
            if tw <= effective_max_width and th <= effective_max_height:
                best_fit = (candidate_text, mid, candidate_font)
                fits = True
                break
        if fits:
            low = mid + 1
        else:
            high = mid - 1

    if best_fit is not None:
        return best_fit

    fallback_font = load_font(
        emergency_min,
        hand=hand and not has_cjk_text,
        cjk=has_cjk_text,
        bold=bold,
    )
    fallback_text = wrap_text(draw, raw_text, fallback_font, effective_max_width) if wrap else raw_text
    tw, th = text_size(draw, fallback_text, fallback_font, spacing=spacing)
    if tw <= effective_max_width and (th <= effective_max_height or allow_grow):
        return fallback_text, emergency_min, fallback_font

    # Binary search fallback truncation algorithm for O(log N) font text fitting with word-boundary preservation
    low_idx, high_idx = 0, len(raw_text)
    best_truncated = None

    while low_idx <= high_idx:
        mid_idx = (low_idx + high_idx) // 2
        slice_str = raw_text[:mid_idx]
        words = slice_str.rstrip().split()
        if len(words) > 1 and not slice_str.endswith(" "):
            words = words[:-1]
        candidate = (" ".join(words) + "...") if words else (slice_str[:mid_idx] + "...")
        wrapped_candidate = wrap_text(draw, candidate, fallback_font, effective_max_width) if wrap else candidate
        tw, th = text_size(draw, wrapped_candidate, fallback_font, spacing=spacing)

        if tw <= effective_max_width and th <= effective_max_height:
            best_truncated = (wrapped_candidate, emergency_min, fallback_font)
            low_idx = mid_idx + 1
        else:
            high_idx = mid_idx - 1

    if best_truncated is not None:
        return best_truncated

    dots = wrap_text(draw, "...", fallback_font, effective_max_width) if wrap else "..."
    return dots, emergency_min, fallback_font


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------
def draw_text(
    ex,
    draw: ImageDraw.ImageDraw,
    text: str,
    x: float,
    y: float,
    w: float,
    h: float,
    size: float,
    color: str = None,
    align: str = "center",
    hand: bool = False,
    bold: bool = False,
    spacing: float = 3,
    fit: bool = False,
    min_size: float = 10,
    wrap: bool = True,
    scaled: bool = False,
    opacity: float = None,
) -> None:
    """Draw *text* onto the PIL canvas and register it in the Excalidraw model.

    When *fit* is True, the font size is reduced automatically to fit the box.
    The text is centred vertically inside the box and aligned horizontally
    according to *align*.

    Args:
        ex:      Excal JSON builder instance.
        draw:    PIL ImageDraw object.
        text:    String to render.
        x, y:   Top-left corner (logical px unless *scaled* is True).
        w, h:    Box dimensions (logical px unless *scaled* is True).
        size:    Font size (logical px unless *scaled* is True).
        color:   Hex colour string; defaults to ``THEME["white"]``.
        align:   ``"left"`` | ``"center"`` | ``"right"``.
        hand:    Use hand-written font.
        bold:    Use bold font.
        spacing: Inter-line spacing (logical px).
        fit:     Auto-shrink font to fit *w × h*.
        min_size: Minimum font size for auto-shrink.
        wrap:    Allow text wrapping during auto-shrink.
        scaled:  If True, all coordinates are already in scaled/physical units.
        opacity: Optional 0-1 float for transparency.
    """
    # Import here to avoid circular dependency with drawing → text
    from . import constants as _c
    SCALE_X = _c.SCALE_X
    SCALE_Y = _c.SCALE_Y

    if text is None:
        text = ""

    if not scaled:
        x = x * SCALE_X
        y = y * SCALE_Y
        w = w * SCALE_X
        h = h * SCALE_Y
        size = size * min(SCALE_X, SCALE_Y)
        min_size = min_size * min(SCALE_X, SCALE_Y)
        spacing = spacing * min(SCALE_X, SCALE_Y)

    color = adjust_color(color or THEME["white"])

    if fit:
        text, size, font = fit_text(
            draw, text, w, h, size,
            min_size=min_size, hand=hand, bold=bold, spacing=spacing, wrap=wrap,
        )
    else:
        font = load_font(size, hand=hand and not has_cjk(text), cjk=has_cjk(text), bold=bold)

    ex.text(text, x, y, w, h, size, color, align=align, bold=bold, hand=hand, opacity=opacity)

    if not text:
        return

    _cache_key = (text, id(font), c(spacing))
    if not hasattr(draw_text, "_bbox_cache"):
        draw_text._bbox_cache = {}
    if _cache_key not in draw_text._bbox_cache:
        draw_text._bbox_cache[_cache_key] = draw.multiline_textbbox((0, 0), text, font=font, spacing=c(spacing))
    box = draw_text._bbox_cache[_cache_key]

    tw = box[2] - box[0]
    th = box[3] - box[1]
    actual_w = c(x + w) - c(x)
    actual_h = c(y + h) - c(y)

    # Horizontal alignment
    tx = c(x)
    if align == "center":
        tx = c(x) + (actual_w - tw) // 2
    elif align == "right":
        tx = c(x + w) - tw

    # Vertical centering
    ty = c(y) + (actual_h - th) // 2

    alpha = int(opacity * 255) if opacity is not None else 255
    draw.multiline_text(
        (tx - box[0], ty - box[1]),
        text,
        font=font,
        fill=hex_rgba(color, alpha),
        spacing=c(spacing),
        align=align,
    )
