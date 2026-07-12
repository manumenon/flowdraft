"""
flowdraft.render
----------------
Two-pass rendering pipeline:

1. ``render_static`` — layout measurement pass + full raster + Excalidraw draw.
2. ``premium_finish`` — post-processing (3-pass glow, grain, vignette, gradient).
"""

import math
import random
import sys

from PIL import Image, ImageDraw, ImageFilter

from .constants import (
    DEFAULT_W, DEFAULT_H, SCALE, SCALE_X, SCALE_Y,
    THEME,
)
from . import constants as _constants  # mutable reference for SCALE_X/Y globals
from .color import hex_rgba, c, adjust_color
from .fonts import load_font
from .text import draw_text, fit_text
from .geometry import path_len, point_at_distance
from .drawing import draw_rect, draw_ellipse, draw_line, draw_diamond, icon
from .excal import Excal
from .layout import (
    CollisionRegistry,
    layout_text_fit, layout_core_card, layout_mini_card,
    layout_pack_row, layout_layer_card,
)
from .components import brand, small_input, core_card, mini_card, pack_row
from .fonts import text_size


# ---------------------------------------------------------------------------
# Static render pass
# ---------------------------------------------------------------------------
def render_static(spec: dict) -> tuple:
    """Full two-pass render of a diagram spec.

    **Pass 1 (layout):** A 1×1 dummy PIL canvas is used to measure text and
    compute all card/panel dimensions without touching the real canvas.  The
    resolved layout is stored back into *spec* under ``_resolved_layout`` and
    ``_resolved_paths`` so that ``premium_finish`` and ``animate_frame`` can
    use the exact coordinates.

    **Pass 2 (draw):** The real hi-DPI canvas is created and all elements are
    drawn in order: title → outer border → input panel → core panel → bottom
    panels.

    Args:
        spec: Diagram spec dict (see ``assets/default-spec.json`` for schema).

    Returns:
        ``(ex, img)`` where *ex* is the populated ``Excal`` instance and *img*
        is a ``PIL.Image.Image`` (RGB, at logical canvas resolution).
    """
    # Allow render_static to update the module-level SCALE_X / SCALE_Y globals
    global SCALE_X, SCALE_Y
    _constants.SCALE_X = SCALE_X
    _constants.SCALE_Y = SCALE_Y
    _constants.HAND    = spec.get("hand", True)

    # ---- 1×1 dummy canvas for text measurement ---------------------------
    dummy_img  = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    dummy_draw = ImageDraw.Draw(dummy_img)
    registry   = CollisionRegistry()

    # ---- 1. Inputs --------------------------------------------------------
    inputs = list(spec.get("inputs") or [])
    while len(inputs) < 3:
        inputs.append({"label": "", "icon": "file"})
    n_inputs = min(len(inputs), 5)

    inputs_data   = []
    max_input_h   = 0
    for item in inputs[:n_inputs]:
        item_dict = item or {}
        label = item_dict.get("label", "")
        txt, sz, w, h = layout_text_fit(dummy_draw, label, 78, 24, 13, 9)
        inputs_data.append({
            "txt": txt, "sz": sz,
            "w": max(78, w), "h": h,
            "icon":  item_dict.get("icon",  "file"),
            "color": item_dict.get("color", THEME["cyan"]),
        })
        max_input_h = max(max_input_h, h)

    input_panel_y = 138
    # Dynamic input centres: 109 px gap between chips (matches original 4-input spacing)
    _inp_gap      = 109
    input_centers = [423 + i * _inp_gap for i in range(n_inputs)]
    resolved_input_centers = []
    curr_center = input_centers[0]
    resolved_input_centers.append(curr_center)
    for i in range(1, len(inputs_data)):
        prev_w = inputs_data[i - 1]["w"]
        curr_w = inputs_data[i]["w"]
        gap    = input_centers[i] - input_centers[i - 1]
        curr_center = resolved_input_centers[i - 1] + max(gap, prev_w / 2 + curr_w / 2)
        resolved_input_centers.append(curr_center)

    input_panel_x = min(resolved_input_centers[0] - inputs_data[0]["w"] / 2 - 5, 389)
    input_panel_w = max(430, resolved_input_centers[-1] + inputs_data[-1]["w"] / 2 + 5 - input_panel_x)
    input_panel_h = max(128, 62 + max_input_h + 36)

    registry.register("InputPanel", input_panel_x, input_panel_y, input_panel_w, input_panel_h)
    for i, inp in enumerate(inputs_data):
        registry.register(f"Input_{i}",
                           resolved_input_centers[i] - inp["w"] / 2,
                           input_panel_y + 42, inp["w"], inp["h"])

    # ---- 2. Core panel and cards -----------------------------------------
    core  = spec.get("core") or {}
    cards = list(core.get("cards") or [])
    while len(cards) < 3:
        cards.append({"title": "", "body": "", "icon": "file"})
    n_cards = min(len(cards), 5)
    core_cards_data = [layout_core_card(dummy_draw, card or {}) for card in cards[:n_cards]]

    core_panel_x = 53
    core_panel_y = input_panel_y + input_panel_h + 78

    card_y = core_panel_y + 82   # extra room for title + subtitle stack without vertical overlaps
    # Dynamic card positions: standard 20 px gap between cards, except a wider
    # 150 px gap before the LAST card — that gap hosts the decision diamond.
    _card_gap_std  = 20
    _card_gap_pred = 150
    resolved_card_x = []
    curr_x = 95
    for i in range(n_cards):
        resolved_card_x.append(curr_x)
        if i < n_cards - 1:
            gap = _card_gap_pred if i == n_cards - 2 else _card_gap_std
            curr_x += core_cards_data[i]["w"] + gap

    # Decision diamond
    decision_spec = spec.get("decision") or {"title": "Ready?", "body": "safe, traced\nusable"}
    dec_title = decision_spec.get("title", "Ready?")
    dec_body  = decision_spec.get("body",  "")
    dec_body  = decision_spec.get("body",  "")
    dec_title_txt, dec_title_sz, dec_title_w, dec_title_h = layout_text_fit(dummy_draw, dec_title, 90, 26, 20, 14)
    dec_body_txt,  dec_body_sz,  dec_body_w,  dec_body_h  = layout_text_fit(dummy_draw, dec_body,  90, 42, 14, 12)
    extra_w_dec = max(0, dec_title_w - 90, dec_body_w - 90)
    extra_h_dec = max(0, (dec_title_h - 26) + (dec_body_h - 42))
    dec_w = 120 + extra_w_dec
    dec_h = 120 + extra_h_dec

    max_card_bottom = max(card_y + card["h"] for card in core_cards_data)
    decision_y = max_card_bottom + 52
    # Decision centred in the 150 px gap between the last two cards
    _cn_m2_right = resolved_card_x[n_cards - 2] + core_cards_data[n_cards - 2]["w"]
    _cn_m1_left  = resolved_card_x[n_cards - 1]
    decision_x   = _cn_m2_right + (_cn_m1_left - _cn_m2_right - dec_w) / 2

    # Output panel
    out_spec   = spec.get("output") or {"label": "Report", "icon": "file"}
    out_label  = out_spec.get("label", "Report")
    out_txt, out_sz, out_w, out_h = layout_text_fit(dummy_draw, out_label, 70, 24, 18, 12, bold=True)
    out_w_final = max(100, 30 + out_w)
    out_h_final = max(94,  51 + out_h)

    output_x = decision_x + dec_w + 196
    output_y = decision_y + (dec_h - out_h_final) / 2

    _last_card_right = resolved_card_x[n_cards - 1] + core_cards_data[n_cards - 1]["w"]
    core_panel_w = max(1104,
                       _last_card_right - core_panel_x + 47,
                       output_x + out_w_final - core_panel_x + 35)
    core_panel_h = max(320,
                       decision_y + dec_h - core_panel_y + 9,
                       output_y + out_h_final - core_panel_y + 16)

    registry.register("CorePanel",   core_panel_x, core_panel_y, core_panel_w, core_panel_h)
    for i in range(n_cards):
        registry.register(f"CoreCard_{i}", resolved_card_x[i], card_y, core_cards_data[i]["w"], core_cards_data[i]["h"])
    registry.register("Decision",    decision_x, decision_y, dec_w, dec_h)
    registry.register("OutputPanel", output_x,   output_y,   out_w_final, out_h_final)

    # ---- 3. Bottom panels ------------------------------------------------
    bottom_y = core_panel_y + core_panel_h + 97

    # Left panel
    left_panel_x   = 39
    left_panel_y   = bottom_y
    left_spec      = spec.get("left_panel") or {}
    left_cards_raw = (left_spec.get("cards") or [])[:3]
    left_cards_data = []
    for i, c_raw in enumerate(left_cards_raw):
        base_h = 95 if i < 2 else 80
        left_cards_data.append(layout_mini_card(dummy_draw, c_raw or {}, 258, base_h))

    left_card_x  = left_panel_x + 12
    left_card_ys = []
    curr_y       = left_panel_y + 62
    for c_data in left_cards_data:
        left_card_ys.append(curr_y)
        curr_y += c_data["h"] + 17

    left_panel_w = max(281, max((cd["w"] for cd in left_cards_data), default=258) + 23)
    left_panel_h = max(344, (left_card_ys[-1] + left_cards_data[-1]["h"] - left_panel_y + 30) if left_cards_data else 344)

    # Center panel
    center_panel_x   = left_panel_x + left_panel_w + 13
    center_panel_y   = bottom_y
    center_spec      = spec.get("center_panel") or {}
    layer_cards_raw  = list((center_spec.get("cards") or [])[:4])
    while len(layer_cards_raw) < 4:
        layer_cards_raw.append({"title": "", "body": "", "icon": "file"})
    layer_cards_data = [layout_layer_card(dummy_draw, card or {}) for card in layer_cards_raw]

    layer_card_y  = center_panel_y + 93
    layer_card_xs = []
    curr_x        = center_panel_x + 13
    for c_data in layer_cards_data:
        layer_card_xs.append(curr_x)
        curr_x += c_data["w"] + 28
    max_layer_h = max(cd["h"] for cd in layer_cards_data)

    footer_text = center_spec.get("footer") or "Redact + Dedup"
    ft_txt, ft_sz, ft_w, ft_h = layout_text_fit(dummy_draw, footer_text, 165, 33, 20, 14, hand=True, bold=True)
    footer_w = max(220, ft_w + 55)
    footer_h = max(50,  ft_h + 17)

    center_panel_w = max(522, layer_card_xs[-1] + layer_cards_data[-1]["w"] - center_panel_x + 13)
    footer_x       = center_panel_x + (center_panel_w - footer_w) / 2
    footer_y       = layer_card_y + max_layer_h + 41
    center_panel_h = max(346, footer_y + footer_h - center_panel_y + 20)

    # Right panel
    right_panel_x   = center_panel_x + center_panel_w + 110
    right_panel_y   = bottom_y
    right            = spec.get("right_panel") or {}
    right_cards_raw  = (right.get("cards") or [])[:3]
    right_cards_data = [layout_pack_row(dummy_draw, card or {}) for card in right_cards_raw]

    right_card_x  = right_panel_x + 14
    right_card_ys = []
    curr_y        = right_panel_y + 51
    for c_data in right_cards_data:
        right_card_ys.append(curr_y)
        curr_y += c_data["h"] + 14

    right_panel_w = max(258, max((cd["w"] for cd in right_cards_data), default=228) + 30)
    right_panel_h = max(344, (right_card_ys[-1] + right_cards_data[-1]["h"] - right_panel_y + 18) if right_cards_data else 344)

    # Register all bottom-panel elements
    registry.register("LeftPanel", left_panel_x, left_panel_y, left_panel_w, left_panel_h)
    for i, c_data in enumerate(left_cards_data):
        registry.register(f"LeftCard_{i}", left_card_x, left_card_ys[i], c_data["w"], c_data["h"])

    registry.register("CenterPanel", center_panel_x, center_panel_y, center_panel_w, center_panel_h)
    for i, c_data in enumerate(layer_cards_data):
        registry.register(f"CenterCard_{i}", layer_card_xs[i], layer_card_y, c_data["w"], c_data["h"])
    registry.register("CenterFooter", footer_x, footer_y, footer_w, footer_h)

    registry.register("RightPanel", right_panel_x, right_panel_y, right_panel_w, right_panel_h)
    for i, c_data in enumerate(right_cards_data):
        registry.register(f"RightCard_{i}", right_card_x, right_card_ys[i], c_data["w"], c_data["h"])

    # ---- Canvas dimensions and SCALE_X/Y ----------------------------------
    outer_border_x = 18
    outer_border_y = 117
    outer_border_w = max(right_panel_x + right_panel_w + 30, core_panel_x + core_panel_w + 30) - outer_border_x
    outer_border_h = max(left_panel_y + left_panel_h, center_panel_y + center_panel_h, right_panel_y + right_panel_h) + 55 - outer_border_y

    ref_w = int(max(DEFAULT_W, outer_border_x + outer_border_w + 18))
    ref_h = int(max(DEFAULT_H, outer_border_y + outer_border_h + 70))

    canvas_spec = spec.get("canvas") or {}
    width  = canvas_spec.get("width")
    height = canvas_spec.get("height")
    if width  is None or not isinstance(width,  (int, float)) or width  <= 0:
        width  = ref_w
    if height is None or not isinstance(height, (int, float)) or height <= 0:
        height = ref_h
    # PIL requires integer canvas dimensions
    width  = int(round(width))
    height = int(round(height))

    SCALE_X = width  / ref_w
    SCALE_Y = height / ref_h
    _constants.SCALE_X = SCALE_X
    _constants.SCALE_Y = SCALE_Y

    # Emit overlap warnings
    overlaps = registry.check_overlaps()
    if overlaps:
        print(f"WARNING: Overlaps detected: {overlaps}", file=sys.stderr)

    # ---- Store resolved layout for post-processing -----------------------
    spec["_resolved_layout"] = {
        "outer_border":    (outer_border_x, outer_border_y, outer_border_x + outer_border_w, outer_border_y + outer_border_h),
        "core_panel":      (core_panel_x,   core_panel_y,   core_panel_x + core_panel_w,   core_panel_y + core_panel_h),
        "center_panel":    (center_panel_x,  center_panel_y,  center_panel_x + center_panel_w,  center_panel_y + center_panel_h),
        "left_panel":      (left_panel_x,   left_panel_y,   left_panel_x + left_panel_w,   left_panel_y + left_panel_h),
        "right_panel":     (right_panel_x,  right_panel_y,  right_panel_x + right_panel_w,  right_panel_y + right_panel_h),
        "highlight_panel": (600, 27, 992, 99),
    }

    # ---- Resolved animated paths ----------------------------------------
    # ---- Resolved animated paths ----------------------------------------
    def scale_path(pts):
        return [(px * SCALE_X, py * SCALE_Y) for px, py in pts]

    # Orthogonal input-to-core path: straight down, horizontally left (above core panel), then down
    y_input_mid = input_panel_y + input_panel_h + (core_panel_y - (input_panel_y + input_panel_h)) / 2
    path_input_to_core = [
        (input_panel_x + input_panel_w / 2, input_panel_y + input_panel_h),
        (input_panel_x + input_panel_w / 2, y_input_mid),
        (resolved_card_x[0] + core_cards_data[0]["w"] / 2, y_input_mid),
        (resolved_card_x[0] + core_cards_data[0]["w"] / 2, card_y),
    ]

    # Dynamic card-to-card horizontal connectors
    card_connector_paths = []
    for i in range(n_cards - 1):
        sx  = resolved_card_x[i] + core_cards_data[i]["w"]
        ex_ = resolved_card_x[i + 1]
        yv  = card_y + core_cards_data[i]["h"] / 2
        card_connector_paths.append([(sx, yv), (ex_, yv)])

    # Last card to decision (S-curve)
    _last_i  = n_cards - 1
    p2_start = (resolved_card_x[_last_i] + core_cards_data[_last_i]["w"] / 2,
                card_y + core_cards_data[_last_i]["h"])
    p2_end   = (decision_x + dec_w / 2, decision_y)
    p2_ymid  = p2_start[1] + (p2_end[1] - p2_start[1]) / 2
    path_last_card_to_decision = [p2_start, (p2_start[0], p2_ymid), (p2_end[0], p2_ymid), p2_end]

    path_decision_to_output = [(decision_x + dec_w, decision_y + dec_h / 2),
                                (output_x, output_y + out_h_final / 2)]

    # Orthogonal path from output bottom to right panel top
    y_out_mid = output_y + out_h_final + (right_panel_y - (output_y + out_h_final)) / 2
    path_output_to_fabric = [
        (output_x + out_w_final / 2, output_y + out_h_final),
        (output_x + out_w_final / 2, y_out_mid),
        (right_panel_x + right_panel_w / 2, y_out_mid),
        (right_panel_x + right_panel_w / 2, right_panel_y),
    ]

    p_loop_start = (decision_x, decision_y + dec_h / 2)
    p_loop_end   = (resolved_card_x[0] + core_cards_data[0]["w"] / 2, card_y + core_cards_data[0]["h"])
    path_decision_to_card0   = [p_loop_start, (p_loop_end[0], p_loop_start[1]), p_loop_end]
    path_core_to_left_down   = []
    
    # Orthogonal upward ingestion path: straight up, horizontally right (clear of label), then up
    y_ingest_mid = core_panel_y + core_panel_h + 15
    path_left_to_core_up     = [
        (left_panel_x + left_panel_w / 2, left_panel_y),
        (left_panel_x + left_panel_w / 2, y_ingest_mid),
        (resolved_card_x[0] + core_cards_data[0]["w"] / 2, y_ingest_mid),
        (resolved_card_x[0] + core_cards_data[0]["w"] / 2, core_panel_y + core_panel_h),
    ]

    # Parallel orthogonal storage paths: go straight down below core panel, horizontally, then down
    y_storage_mid = core_panel_y + core_panel_h + (center_panel_y - (core_panel_y + core_panel_h)) / 2
    path_embeddings_to_db = [
        (resolved_card_x[2] + core_cards_data[2]["w"] / 2, card_y + core_cards_data[2]["h"]),
        (resolved_card_x[2] + core_cards_data[2]["w"] / 2, y_storage_mid),
        (center_panel_x + center_panel_w * 0.35, y_storage_mid),
        (center_panel_x + center_panel_w * 0.35, center_panel_y),
    ]
    path_graph_to_db = [
        (resolved_card_x[3] + core_cards_data[3]["w"] / 2, card_y + core_cards_data[3]["h"]),
        (resolved_card_x[3] + core_cards_data[3]["w"] / 2, y_storage_mid),
        (center_panel_x + center_panel_w * 0.65, y_storage_mid),
        (center_panel_x + center_panel_w * 0.65, center_panel_y),
    ]

    path_layer_connectors    = [] # Removed horizontal chain connectors between storage nodes
    path_center_to_right = [(center_panel_x + center_panel_w, center_panel_y + 155),
                             (right_panel_x, right_panel_y + 155)]
    pr_start = (right_panel_x + 132, right_panel_y)
    pr_end   = (decision_x + dec_w / 2, decision_y + dec_h)
    pr_ymid  = pr_end[1] + (pr_start[1] - pr_end[1]) / 2
    path_right_to_decision = [pr_start, (pr_start[0], pr_ymid), (pr_end[0], pr_ymid), pr_end]

    # Spread card connector timings evenly in the 0.10-0.36 window
    _cc_start, _cc_end = 0.10, 0.36
    _cc_step = (_cc_end - _cc_start) / max(n_cards - 1, 1) if n_cards > 1 else 0
    _card_anim_entries = [
        (scale_path(p), THEME["cyan"], _cc_start + idx * _cc_step)
        for idx, p in enumerate(card_connector_paths)
    ]
    spec["_resolved_paths"] = (
        [(scale_path(path_input_to_core),            THEME["green"],       0.00)]
        + _card_anim_entries
        + [
            (scale_path(path_last_card_to_decision), THEME["core_stroke"], 0.38),
            (scale_path(path_decision_to_output),    THEME["green"],       0.54),
            (scale_path(path_output_to_fabric),      THEME["cyan"],        0.62),
            (scale_path(path_decision_to_card0),     THEME["purple"],      0.66),
            (scale_path(path_left_to_core_up),       THEME["green"],       0.18),
            (scale_path(path_embeddings_to_db),      THEME["cyan"],        0.28),
            (scale_path(path_graph_to_db),           THEME["purple"],      0.34),
            (scale_path(path_center_to_right),       THEME["white"],       0.46),
            (scale_path(path_right_to_decision),     THEME["amber"],       0.72),
        ]
    )
    _pulse_colors = [THEME["core_stroke"], THEME["green"], THEME["core_stroke"], THEME["green"], THEME["core_stroke"]]
    spec["_resolved_pulse_targets"] = (
        [((input_panel_x * SCALE_X, input_panel_y * SCALE_Y,
           (input_panel_x + input_panel_w) * SCALE_X, (input_panel_y + input_panel_h) * SCALE_Y), THEME["green"])]
        + [
            ((resolved_card_x[i] * SCALE_X, card_y * SCALE_Y,
              (resolved_card_x[i] + core_cards_data[i]["w"]) * SCALE_X, (card_y + core_cards_data[i]["h"]) * SCALE_Y),
             _pulse_colors[i % len(_pulse_colors)])
            for i in range(n_cards)
        ]
        + [
            ((decision_x * SCALE_X, decision_y * SCALE_Y,
              (decision_x + dec_w) * SCALE_X, (decision_y + dec_h) * SCALE_Y), THEME["green"]),
            ((center_panel_x * SCALE_X, center_panel_y * SCALE_Y,
              (center_panel_x + center_panel_w) * SCALE_X, (center_panel_y + center_panel_h) * SCALE_Y), THEME["purple"]),
            ((right_panel_x * SCALE_X, right_panel_y * SCALE_Y,
              (right_panel_x + right_panel_w) * SCALE_X, (right_panel_y + right_panel_h) * SCALE_Y), THEME["green"]),
        ]
    )

    # ---- Real canvas and draw pass ---------------------------------------
    ex_doc = Excal(width, height)
    img    = Image.new("RGBA", (width * SCALE, height * SCALE), hex_rgba(THEME["bg"]))
    draw   = ImageDraw.Draw(img)

    title = spec.get("title") or {}

    def _sanitise(s):
        """Replace typographic dashes that most fonts cannot render."""
        if not isinstance(s, str):
            return s
        return s.replace("\u2011", "-").replace("\u2012", "-").replace("\u2013", "-").replace("\u2014", "-").replace("\u2015", "-")

    highlight_text = _sanitise(title.get("highlight", "Memory Pack"))
    prefix_text    = _sanitise(title.get("prefix",    "The internals of"))
    subtitle_text  = _sanitise(title.get("subtitle",  ""))

    _hl_font = load_font(44, hand=True, bold=True)
    _hl_tw, _ = text_size(draw, highlight_text, _hl_font)
    _hl_tw    = max(int(_hl_tw / SCALE), 200)
    _hl_pad_x = 22
    hl_rect_x = 600
    hl_rect_y = 27
    hl_rect_w = _hl_tw + _hl_pad_x * 2
    hl_rect_h = 72

    draw_line(ex_doc, draw, [(29, 31), (29, 78)], THEME["purple"], 11)
    draw_text(ex_doc, draw, prefix_text, 45, 14, 535, 66, 47, THEME["white"], "left", hand=True, bold=True)
    draw_rect(ex_doc, draw, hl_rect_x, hl_rect_y, hl_rect_w, hl_rect_h, THEME["highlight"], THEME["highlight"], 2, 16)
    draw_text(ex_doc, draw, highlight_text, hl_rect_x + _hl_pad_x, 19, hl_rect_w - _hl_pad_x * 2, 76, 44, THEME["green"], "center", hand=True, bold=True)
    draw_text(ex_doc, draw, subtitle_text, 104, 90, 420, 25, 15, THEME["muted"], "left")

    draw_rect(ex_doc, draw, outer_border_x, outer_border_y, outer_border_w, outer_border_h, THEME["frame"], None, 2, 29)
    brand(ex_doc, draw, spec.get("signature", "@FlowDraft"),
          bx=resolved_input_centers[-1] + inputs_data[-1]["w"] / 2 + 30, by=143)

    # Input panel
    draw_rect(ex_doc, draw, input_panel_x, input_panel_y, input_panel_w, input_panel_h, THEME["green"], None, 2, 8)
    draw_text(ex_doc, draw, spec.get("input_title", "Source / Input"),
              input_panel_x + 109, input_panel_y + 16, 210, 31, 22, THEME["white"], "center", hand=True, bold=True)
    for i, inp in enumerate(inputs_data):
        small_input(ex_doc, draw, resolved_input_centers[i] * SCALE_X, (input_panel_y + 62) * SCALE_Y, inp)

    # Core panel
    draw_rect(ex_doc, draw, core_panel_x, core_panel_y, core_panel_w, core_panel_h,
              THEME["core_stroke"], THEME["core_fill"], 2, 20)
    draw_line(ex_doc, draw, path_input_to_core, THEME["white"], 2, "solid", arrow=True)
    draw_text(ex_doc, draw, core.get("title", "Archive Core"),
              core_panel_x + 390, core_panel_y + 6, 280, 26, 18, THEME["white"], "center", hand=True, bold=True, fit=True, min_size=12)
    draw_text(ex_doc, draw, core.get("subtitle", "(local read-only pipeline)"),
              core_panel_x + 390, core_panel_y + 38, 720, 20, 11, THEME["muted"], "left")
    for i, card_data in enumerate(core_cards_data):
        core_card(ex_doc, draw, resolved_card_x[i] * SCALE_X, card_y * SCALE_Y, card_data)

    for path in card_connector_paths:
        draw_line(ex_doc, draw, path, THEME["white"], 2, "solid", arrow=True)
    draw_line(ex_doc, draw, path_last_card_to_decision, THEME["core_stroke"], 2, "solid", arrow=True)

    # Decision diamond
    draw_diamond(ex_doc, draw, decision_x, decision_y, dec_w, dec_h, THEME["green"], "#052515", 2)
    draw_text(ex_doc, draw, dec_title_txt, decision_x + 22, decision_y + 30, dec_w - 42, dec_title_h, dec_title_sz, THEME["white"], "center", fit=False)
    draw_text(ex_doc, draw, dec_body_txt,  decision_x + 22, decision_y + 30 + dec_title_h + 3, dec_w - 42, dec_body_h, dec_body_sz, THEME["white"], "center", fit=False)

    # Output
    draw_rect(ex_doc, draw, output_x, output_y, out_w_final, out_h_final, THEME["core_stroke"], THEME["blue_fill"], 2, 9)
    icon(ex_doc, draw, out_spec.get("icon", "file"), output_x + 13, output_y + 10, THEME["cyan"])
    draw_text(ex_doc, draw, out_txt, output_x + 15, output_y + 51, out_w_final - 30, out_h, out_sz, THEME["white"], "center", bold=True, fit=False)

    draw_line(ex_doc, draw, path_decision_to_output, THEME["white"], 2, "solid", arrow=True)

    yes_x = decision_x + dec_w + (output_x - (decision_x + dec_w) - 45) / 2
    yes_y = decision_y + dec_h / 2 - 25
    draw_text(ex_doc, draw, "Yes", yes_x, yes_y, 45, 25, 15, THEME["white"], "center")

    draw_line(ex_doc, draw, path_decision_to_card0, THEME["muted"], 2, "dashed", arrow=True)

    loop_lbl_x = p_loop_end[0] + (p_loop_start[0] - p_loop_end[0] - 540) / 2
    loop_lbl_y = p_loop_start[1] - 64
    draw_text(ex_doc, draw, spec.get("loop_label", "Loop until checked and updated"), loop_lbl_x, loop_lbl_y, 540, 25, 14, THEME["white"], "center")

    retry_lbl_x = p_loop_end[0] + (p_loop_start[0] - p_loop_end[0] - 250) / 2
    retry_lbl_y = p_loop_start[1] + 12
    draw_text(ex_doc, draw, spec.get("retry_label", "No / missing source or conflict"), retry_lbl_x, retry_lbl_y, 250, 24, 14, THEME["white"], "center")
    draw_line(ex_doc, draw, path_left_to_core_up,   THEME["white"], 2, "solid", arrow=True)

    # Output to fabric context dispatcher connection
    draw_line(ex_doc, draw, path_output_to_fabric, THEME["white"], 2, "solid", arrow=True)

    draw_text(ex_doc, draw, "Ingest Events", (left_panel_x + left_panel_w / 2) - 80, left_panel_y - 25, 160, 22, 14, THEME["white"], "center")

    # Left panel
    draw_rect(ex_doc, draw, left_panel_x, left_panel_y, left_panel_w, left_panel_h, THEME["green"], THEME["source_fill"], 2, 14)
    # Left panel title: auto-fit to container width to avoid border collision
    _left_title_w = max(180, left_panel_w - 28)
    draw_text(ex_doc, draw, left_spec.get("title", "Memory Sources"), left_panel_x + 19, left_panel_y + 17, _left_title_w, 30, 22, THEME["white"], "left", hand=True, bold=True, fit=True, min_size=14)
    draw_text(ex_doc, draw, left_spec.get("badge", "read only"), left_panel_x + 205, left_panel_y + 44, 62, 18, 11, THEME["green"], "center")
    for i, c_data in enumerate(left_cards_data):
        mini_card(ex_doc, draw, left_card_x * SCALE_X, left_card_ys[i] * SCALE_Y,
                  c_data["w"] * SCALE_X, c_data["h"] * SCALE_Y,
                  c_data, THEME["green"], "#04200f")
        # Internal sequential flow: connect stacked buffers to parsers to aggregators
        if i < len(left_cards_data) - 1:
            sy = left_card_ys[i] + c_data["h"]
            ey = left_card_ys[i + 1]
            cx = left_card_x + c_data["w"] / 2
            draw_line(ex_doc, draw, [(cx, sy), (cx, ey)], THEME["white"], 1.5, "solid", arrow=True)

    # Center panel
    draw_rect(ex_doc, draw, center_panel_x, center_panel_y, center_panel_w, center_panel_h, THEME["purple"], THEME["archive_fill"], 2, 14)
    draw_text(ex_doc, draw, center_spec.get("title", "Archive Layers"), center_panel_x + 179, center_panel_y + 22, 180, 34, 23, THEME["white"], "center", hand=True, bold=True)
    draw_text(ex_doc, draw, center_spec.get("subtitle", "(local, readable, traceable storage)"), center_panel_x + 111, center_panel_y + 56, 300, 24, 14, THEME["white"], "center")
    for i, c_data in enumerate(layer_cards_data):
        lx = layer_card_xs[i]
        ly = layer_card_y
        draw_rect(ex_doc, draw, lx, ly, c_data["w"], c_data["h"], THEME["purple"], "#17091d", 2, 8)
        icon(ex_doc, draw, c_data["icon"], lx + 24, ly + 13, c_data.get("color", THEME["cyan"]), 0.8)
        draw_text(ex_doc, draw, c_data["title_txt"], lx + 10, ly + 83, c_data["title_w"], c_data["title_h"], c_data["title_sz"], THEME["white"], "center", bold=True, fit=False)
        draw_text(ex_doc, draw, c_data["body_txt"],  lx + 8,  ly + 83 + c_data["title_h"] + 1, c_data["body_w"], c_data["body_h"], c_data["body_sz"], THEME["white"], "center", spacing=2, fit=False)

    # Parallel storage paths from embedding/stitching nodes to database panels below
    draw_line(ex_doc, draw, path_embeddings_to_db, THEME["white"], 2, "solid", arrow=True)
    draw_line(ex_doc, draw, path_graph_to_db, THEME["white"], 2, "solid", arrow=True)

    draw_rect(ex_doc, draw, footer_x, footer_y, footer_w, footer_h, THEME["purple"], THEME["archive_fill"], 2, 8)
    draw_text(ex_doc, draw, ft_txt, footer_x + 37, footer_y + 7, footer_w - 74, footer_h - 17, ft_sz, THEME["white"], "center", hand=True, bold=True, fit=False)
    draw_line(ex_doc, draw,
              [(center_panel_x + center_panel_w / 2, layer_card_y + max_layer_h),
               (center_panel_x + center_panel_w / 2, footer_y)],
              THEME["muted"], 2, "dashed", True)

    # Right panel
    draw_line(ex_doc, draw, path_center_to_right, THEME["white"], 2, "solid", arrow=True)
    # Incoming-label: sized to fit within the actual inter-panel gap
    _lbl_gap = right_panel_x - (center_panel_x + center_panel_w)
    _lbl_w   = max(40, _lbl_gap - 8)   # 4 px margin each side
    _lbl_x   = center_panel_x + center_panel_w + (_lbl_gap - _lbl_w) / 2
    draw_text(ex_doc, draw, right.get("incoming_label", "Compile"), _lbl_x, center_panel_y + 116, _lbl_w, 44, 12, THEME["white"], "center", fit=True, min_size=9)
    draw_rect(ex_doc, draw, right_panel_x, right_panel_y, right_panel_w, right_panel_h, THEME["green"], THEME["pack_fill"], 2, 14)
    draw_text(ex_doc, draw, right.get("title", "Memory Pack"), right_panel_x + 44, right_panel_y + 15, 170, 34, 22, THEME["white"], "center", hand=True, bold=True)
    for i, c_data in enumerate(right_cards_data):
        pack_row(ex_doc, draw, right_card_x * SCALE_X, right_card_ys[i] * SCALE_Y, c_data)
        # Internal sequential flow: connect planner to tools to registry
        if i < len(right_cards_data) - 1:
            sy = right_card_ys[i] + c_data["h"]
            ey = right_card_ys[i + 1]
            cx = right_card_x + c_data["w"] / 2
            draw_line(ex_doc, draw, [(cx, sy), (cx, ey)], THEME["white"], 1.5, "solid", arrow=True)
    draw_line(ex_doc, draw, path_right_to_decision, THEME["white"], 2, "solid", arrow=True)

    reusable_x = pr_end[0] + (pr_start[0] - pr_end[0] - 75) / 2
    draw_text(ex_doc, draw, right.get("return_label", "Reusable"), reusable_x, pr_ymid - 22, 75, 23, 16, THEME["white"], "center")


    return ex_doc, img.resize((width, height), Image.Resampling.LANCZOS).convert("RGB")


# ---------------------------------------------------------------------------
# Post-processing
# ---------------------------------------------------------------------------
def premium_finish(base: Image.Image, spec: dict = None) -> Image.Image:
    """Apply multi-pass glow, grain, vignette, and bottom-gradient post-processing.

    Effects applied in order:

    1. **3-pass progressive glow** — ambient haze (wide blur), mid glow, sharp ring.
    2. **Bottom gradient anchor strip** — subtle dark/light strip at the bottom edge.
    3. **Film grain** — seeded random noise for a premium print texture.
    4. **Vignette** — centred radial darkening for a cinematic frame.

    Args:
        base: RGB or RGBA PIL Image (the output of ``render_static``).
        spec: Optional spec dict with ``_resolved_layout`` for accurate glow
              rectangle coordinates.

    Returns:
        A processed RGB PIL Image.
    """
    width, height = base.size
    img      = base.convert("RGBA")
    is_light = THEME["bg"] in ("#ffffff", "#f8f9fa")

    layout = spec.get("_resolved_layout") if spec else None

    if layout:
        rects = [
            (layout["outer_border"],    THEME["frame"],       3),
            (layout["core_panel"],      THEME["core_stroke"], 3),
            (layout["center_panel"],    THEME["purple"],      3),
            (layout["left_panel"],      THEME["green"],       3),
            (layout["right_panel"],     THEME["green"],       3),
            (layout["highlight_panel"], THEME["green"],       2),
        ]
    else:
        rects = [
            ((18 * SCALE_X,  117 * SCALE_Y, 1192 * SCALE_X, 1111 * SCALE_Y), THEME["frame"],       3),
            ((53 * SCALE_X,  317 * SCALE_Y, 1157 * SCALE_X,  637 * SCALE_Y), THEME["core_stroke"], 3),
            ((333 * SCALE_X, 734 * SCALE_Y,  855 * SCALE_X, 1080 * SCALE_Y), THEME["purple"],      3),
            ((39 * SCALE_X,  735 * SCALE_Y,  320 * SCALE_X, 1079 * SCALE_Y), THEME["green"],       3),
            ((904 * SCALE_X, 735 * SCALE_Y, 1162 * SCALE_X, 1079 * SCALE_Y), THEME["green"],       3),
            ((600 * SCALE_X,  27 * SCALE_Y,  992 * SCALE_X,   99 * SCALE_Y), THEME["green"],       2),
        ]

    def _build_glow_layer(alpha_mul: float) -> Image.Image:
        glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        g    = ImageDraw.Draw(glow)
        s_radius = int(round(18 * min(SCALE_X, SCALE_Y)))
        for rect, color, line_width in rects:
            if layout:
                x1, y1, x2, y2 = rect
                sr = (x1 * SCALE_X, y1 * SCALE_Y, x2 * SCALE_X, y2 * SCALE_Y)
            else:
                sr = rect
            s_lw = max(1, int(round(line_width * min(SCALE_X, SCALE_Y))))
            g.rounded_rectangle(sr, radius=s_radius, outline=hex_rgba(color, int(90 * alpha_mul)), width=s_lw)
        return glow

    # 3-pass progressive glow
    img.alpha_composite(_build_glow_layer(0.40).filter(ImageFilter.GaussianBlur(max(2, int(round(14 * min(SCALE_X, SCALE_Y)))))))
    img.alpha_composite(_build_glow_layer(0.60).filter(ImageFilter.GaussianBlur(max(1, int(round( 6 * min(SCALE_X, SCALE_Y)))))))
    img.alpha_composite(_build_glow_layer(1.00).filter(ImageFilter.GaussianBlur(max(1, int(round( 2 * min(SCALE_X, SCALE_Y)))))))

    # Bottom gradient strip
    strip_h = int(height * 0.06)
    for row in range(strip_h):
        t    = row / max(strip_h - 1, 1)
        a    = int(35 * (1.0 - t)) if not is_light else int(15 * (1.0 - t))
        tint = (200, 200, 200, a) if is_light else (0, 0, 0, a)
        ImageDraw.Draw(img).line([(0, height - strip_h + row), (width, height - strip_h + row)], fill=tint)

    # Film grain
    grain = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    gd    = ImageDraw.Draw(grain)
    rng   = random.Random(2069769416930414980)
    for _ in range(5500):
        gx   = rng.randrange(width)
        gy   = rng.randrange(height)
        tone = rng.randrange(80, 240)
        gd.point((gx, gy), fill=(tone, tone, tone, rng.randrange(5, 18)))
    img.alpha_composite(grain)

    # Centred vignette
    cx_v, cy_v = width // 2, height // 2
    max_dist   = math.dist((0, 0), (cx_v, cy_v))
    mask_arr   = []
    for vy in range(height):
        for vx in range(width):
            dist = math.dist((vx, vy), (cx_v, cy_v)) / max_dist
            val  = int(max(0, min(145, (dist - 0.30) * 180)))
            mask_arr.append(val)
    mask = Image.new("L", (width, height))
    mask.putdata(mask_arr)
    vignette_color = (200, 200, 200) if is_light else (0, 0, 0)
    vignette       = Image.new("RGBA", (width, height), vignette_color + (0,))
    vignette.putalpha(mask)
    img.alpha_composite(vignette)

    return img.convert("RGB")
