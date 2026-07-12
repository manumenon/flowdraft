#!/usr/bin/env python3
"""
render_dynamic_diagram.py — Dynamic diagram rendering engine and CLI.
"""

import argparse
import json
import math
import sys
import random
from pathlib import Path
from PIL import Image, ImageDraw, ImageChops, ImageFilter

# Add project root to sys.path
_project_root = str(Path(__file__).resolve().parents[1])
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from scripts.flowdraft.constants import (
    DEFAULT_W, DEFAULT_H, DEFAULT_FRAMES, DEFAULT_FPS, SCALE, THEME, set_theme
)
import scripts.flowdraft.constants as fc
from scripts.flowdraft.color import hex_rgba, adjust_color
from scripts.flowdraft.fonts import load_font, text_size
from scripts.flowdraft.text import draw_text, fit_text
from scripts.flowdraft.drawing import (
    draw_rect, draw_ellipse, draw_line, draw_diamond, icon, draw_signature
)
from scripts.flowdraft.excal import Excal
from scripts.flowdraft.svg import excalidraw_to_svg
from scripts.flowdraft.animation import animate_frame
from scripts.flowdraft.layout import resolve_diagram_layout, resolve_node_style



# ---------------------------------------------------------------------------
# Rebranding helper
# ---------------------------------------------------------------------------
def apply_rebranding(data, replacement: str = "FlowDraft"):
    if isinstance(data, dict):
        return {k: apply_rebranding(v, replacement) for k, v in data.items()}
    elif isinstance(data, list):
        return [apply_rebranding(item, replacement) for item in data]
    elif isinstance(data, str):
        key_chinese = "\u5c9a\u53d4"
        key_title   = "Lanshu"
        key_lower   = "lanshu"
        return (
            data
            .replace(key_chinese, replacement)
            .replace(key_title,   replacement)
            .replace(key_lower,   replacement.lower())
        )
    return data


# ---------------------------------------------------------------------------
# Layout conversion helpers
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
    raw_text = str(text)
    fitted_text, fitted_size, fitted_font = fit_text(
        draw, raw_text, default_w, default_h, start_size,
        min_size=min_size, hand=hand, bold=bold, spacing=spacing, wrap=wrap,
        allow_grow=True,
    )
    tw, th = text_size(draw, fitted_text, fitted_font, spacing=spacing)
    unscaled_tw = tw / SCALE
    unscaled_th = th / SCALE
    if unscaled_tw <= default_w and unscaled_th <= default_h:
        return fitted_text, fitted_size, default_w, default_h
    return fitted_text, fitted_size, max(default_w, unscaled_tw), max(default_h, unscaled_th)


def layout_core_card(draw: ImageDraw.ImageDraw, card: dict) -> dict:
    title = card.get("title", "")
    body  = card.get("body", "")
    title_txt, title_sz, title_w, title_h = layout_text_fit(draw, title, 100, 28, 20, 15, hand=fc.HAND, bold=True)
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


def convert_legacy_spec_to_dynamic(spec: dict) -> dict:
    dummy_img  = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    dummy_draw = ImageDraw.Draw(dummy_img)

    # 1. Inputs
    raw_inputs = list(spec.get("inputs") or [])
    inputs = []
    for item in raw_inputs:
        if not isinstance(item, dict):
            inputs.append({"label": str(item) if item is not None else "", "icon": "file"})
        else:
            inputs.append(item)
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

    # 2. Core panel and cards
    core  = spec.get("core") or {}
    if not isinstance(core, dict):
        core = {}
    raw_cards = list(core.get("cards") or [])
    cards = []
    for card in raw_cards:
        if not isinstance(card, dict):
            cards.append({"title": str(card) if card is not None else "", "body": "", "icon": "file"})
        else:
            cards.append(card)
    while len(cards) < 3:
        cards.append({"title": "", "body": "", "icon": "file"})
    n_cards = min(len(cards), 5)
    core_cards_data = [layout_core_card(dummy_draw, card or {}) for card in cards[:n_cards]]

    core_panel_x = 53
    core_panel_y = input_panel_y + input_panel_h + 78
    card_y = core_panel_y + 82

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
    if not isinstance(decision_spec, dict):
        decision_spec = {"title": str(decision_spec), "body": ""}
    dec_title = decision_spec.get("title", "Ready?")
    dec_body  = decision_spec.get("body",  "")
    dec_title_txt, dec_title_sz, dec_title_w, dec_title_h = layout_text_fit(dummy_draw, dec_title, 90, 26, 20, 14)
    dec_body_txt,  dec_body_sz,  dec_body_w,  dec_body_h  = layout_text_fit(dummy_draw, dec_body,  90, 55, 14, 12)
    extra_w_dec = max(0, dec_title_w - 90, dec_body_w - 90)
    extra_h_dec = max(0, (dec_title_h - 26) + (dec_body_h - 55))
    dec_w = 120 + extra_w_dec
    dec_h = 120 + extra_h_dec

    max_card_bottom = max(card_y + card["h"] for card in core_cards_data)
    decision_y = max_card_bottom + 52
    _cn_m2_right = resolved_card_x[n_cards - 2] + core_cards_data[n_cards - 2]["w"]
    _cn_m1_left  = resolved_card_x[n_cards - 1]
    decision_x   = _cn_m2_right + (_cn_m1_left - _cn_m2_right - dec_w) / 2

    # Output panel
    out_spec   = spec.get("output") or {"label": "Report", "icon": "file"}
    if not isinstance(out_spec, dict):
        out_spec = {"label": str(out_spec), "icon": "file"}
    out_label  = out_spec.get("label", "Report")
    out_txt, out_sz, out_w, out_h = layout_text_fit(dummy_draw, out_label, 160, 26, 18, 12, bold=True)
    out_w_final = max(200, 50 + out_w)
    out_h_final = max(90,  40 + out_h)

    output_x = decision_x + dec_w + 196
    output_y = decision_y + (dec_h - out_h_final) / 2

    _last_card_right = resolved_card_x[n_cards - 1] + core_cards_data[n_cards - 1]["w"]
    core_panel_w = max(1104,
                       _last_card_right - core_panel_x + 47,
                       output_x + out_w_final - core_panel_x + 35)
    core_panel_h = max(320,
                       decision_y + dec_h - core_panel_y + 9,
                       output_y + out_h_final - core_panel_y + 16)

    # 3. Bottom panels
    bottom_y = core_panel_y + core_panel_h + 97

    # Left panel
    left_panel_x   = 39
    left_panel_y   = bottom_y
    left_spec      = spec.get("left_panel") or {}
    if not isinstance(left_spec, dict):
        left_spec = {}
    raw_left_cards = list(left_spec.get("cards") or [])
    left_cards_raw = []
    for card in raw_left_cards:
        if not isinstance(card, dict):
            left_cards_raw.append({"title": str(card) if card is not None else "", "body": "", "icon": "file"})
        else:
            left_cards_raw.append(card)
    left_cards_raw = left_cards_raw[:3]
    left_cards_data = []
    for i, c_raw in enumerate(left_cards_raw):
        base_h = 95 if i < 2 else 90
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
    if not isinstance(center_spec, dict):
        center_spec = {}
    raw_layer_cards  = list(center_spec.get("cards") or [])
    layer_cards_raw = []
    for card in raw_layer_cards:
        if not isinstance(card, dict):
            layer_cards_raw.append({"title": str(card) if card is not None else "", "body": "", "icon": "file"})
        else:
            layer_cards_raw.append(card)
    layer_cards_raw = layer_cards_raw[:4]
    while len(layer_cards_raw) < 4:
        layer_cards_raw.append({"title": "", "body": "", "icon": "file"})
    layer_cards_data = [layout_layer_card(dummy_draw, card or {}) for card in layer_cards_raw]

    layer_card_y  = center_panel_y + 100
    layer_card_xs = []
    curr_x        = center_panel_x + 13
    for c_data in layer_cards_data:
        layer_card_xs.append(curr_x)
        curr_x += c_data["w"] + 28
    max_layer_h = max(cd["h"] for cd in layer_cards_data)

    _footer_raw = center_spec.get("footer")
    if isinstance(_footer_raw, dict):
        footer_text = _footer_raw.get("title", "Redact + Dedup")
    elif isinstance(_footer_raw, str):
        footer_text = _footer_raw
    else:
        footer_text = "Redact + Dedup"
    ft_txt, ft_sz, ft_w, ft_h = layout_text_fit(dummy_draw, footer_text, 165, 33, 20, 14, hand=fc.HAND, bold=True)
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
    if not isinstance(right, dict):
        right = {}
    raw_right_cards  = list(right.get("cards") or [])
    right_cards_raw = []
    for card in raw_right_cards:
        if not isinstance(card, dict):
            right_cards_raw.append({"title": str(card) if card is not None else "", "body": "", "icon": "file"})
        else:
            right_cards_raw.append(card)
    right_cards_raw = right_cards_raw[:3]
    right_cards_data = [layout_pack_row(dummy_draw, card or {}) for card in right_cards_raw]

    right_card_x  = right_panel_x + 14
    right_card_ys = []
    curr_y        = right_panel_y + 51
    for c_data in right_cards_data:
        right_card_ys.append(curr_y)
        curr_y += c_data["h"] + 14

    right_panel_w = max(258, max((cd["w"] for cd in right_cards_data), default=228) + 30)
    right_panel_h = max(344, (right_card_ys[-1] + right_cards_data[-1]["h"] - right_panel_y + 18) if right_cards_data else 344)

    nodes = []

    def copy_styling(src_dict, dest_dict):
        for key in ("style", "color_preset", "fixed"):
            if key in src_dict:
                dest_dict[key] = src_dict[key]

    # Panels
    input_panel_node = {"id": "input_panel", "x": input_panel_x, "y": input_panel_y, "width": input_panel_w, "height": input_panel_h, "type": "panel", "title": spec.get("input_title", "Source / Input")}
    if "input_panel_style" in spec:
        input_panel_node["style"] = spec["input_panel_style"]
    nodes.append(input_panel_node)

    core_panel_node = {"id": "core_panel", "x": core_panel_x, "y": core_panel_y, "width": core_panel_w, "height": core_panel_h, "type": "panel", "title": core.get("title", "Archive Core")}
    copy_styling(core, core_panel_node)
    nodes.append(core_panel_node)

    left_panel_node = {"id": "left_panel", "x": left_panel_x, "y": left_panel_y, "width": left_panel_w, "height": left_panel_h, "type": "panel", "title": left_spec.get("title", "Memory Sources")}
    copy_styling(left_spec, left_panel_node)
    nodes.append(left_panel_node)

    center_panel_node = {"id": "center_panel", "x": center_panel_x, "y": center_panel_y, "width": center_panel_w, "height": center_panel_h, "type": "panel", "title": center_spec.get("title", "Archive Layers")}
    copy_styling(center_spec, center_panel_node)
    nodes.append(center_panel_node)

    right_panel_node = {"id": "right_panel", "x": right_panel_x, "y": right_panel_y, "width": right_panel_w, "height": right_panel_h, "type": "panel", "title": right.get("title", "Memory Pack")}
    copy_styling(right, right_panel_node)
    nodes.append(right_panel_node)

    # Input chips
    for i, inp in enumerate(inputs_data):
        node_item = {"id": f"input_{i}", "x": resolved_input_centers[i] - inp["w"] / 2, "y": input_panel_y + 42, "width": inp["w"], "height": inp["h"], "type": "input", "title": inputs[i].get("label", ""), "icon": inp["icon"], "color": inp["color"]}
        copy_styling(inputs[i], node_item)
        nodes.append(node_item)

    # Core cards
    for i in range(n_cards):
        node_item = {"id": f"core_card_{i}", "x": resolved_card_x[i], "y": card_y, "width": core_cards_data[i]["w"], "height": core_cards_data[i]["h"], "type": "card", "title": cards[i].get("title", ""), "body": cards[i].get("body", ""), "icon": core_cards_data[i]["icon"], "color": core_cards_data[i]["color"]}
        copy_styling(cards[i], node_item)
        nodes.append(node_item)

    # Decision diamond
    decision_node = {"id": "decision", "x": decision_x, "y": decision_y, "width": dec_w, "height": dec_h, "type": "diamond", "title": dec_title, "body": dec_body}
    copy_styling(decision_spec, decision_node)
    nodes.append(decision_node)

    # Output card
    output_node = {"id": "output", "x": output_x, "y": output_y, "width": out_w_final, "height": out_h_final, "type": "card", "title": out_label, "body": "", "icon": out_spec.get("icon", "file"), "color": THEME["cyan"]}
    copy_styling(out_spec, output_node)
    nodes.append(output_node)

    # Left cards
    for i in range(len(left_cards_raw)):
        node_item = {"id": f"left_card_{i}", "x": left_card_x, "y": left_card_ys[i], "width": left_cards_data[i]["w"], "height": left_cards_data[i]["h"], "type": "card", "title": left_cards_raw[i].get("title", ""), "body": left_cards_raw[i].get("body", ""), "icon": left_cards_data[i]["icon"], "color": left_cards_data[i]["color"]}
        copy_styling(left_cards_raw[i], node_item)
        nodes.append(node_item)

    # Center cards
    for i in range(len(layer_cards_raw)):
        node_item = {"id": f"center_card_{i}", "x": layer_card_xs[i], "y": layer_card_y, "width": layer_cards_data[i]["w"], "height": layer_cards_data[i]["h"], "type": "card", "title": layer_cards_raw[i].get("title", ""), "body": layer_cards_raw[i].get("body", ""), "icon": layer_cards_data[i]["icon"], "color": layer_cards_data[i]["color"]}
        copy_styling(layer_cards_raw[i], node_item)
        nodes.append(node_item)

    # Center footer card
    center_footer_node = {"id": "center_footer", "x": footer_x, "y": footer_y, "width": footer_w, "height": footer_h, "type": "card", "title": footer_text, "body": "", "icon": "file", "color": THEME["purple"]}
    if isinstance(center_spec.get("footer"), dict):
        copy_styling(center_spec["footer"], center_footer_node)
    nodes.append(center_footer_node)

    # Right cards
    for i in range(len(right_cards_raw)):
        node_item = {"id": f"right_card_{i}", "x": right_card_x, "y": right_card_ys[i], "width": right_cards_data[i]["w"], "height": right_cards_data[i]["h"], "type": "card", "title": right_cards_raw[i].get("title", ""), "body": right_cards_raw[i].get("body", ""), "icon": right_cards_data[i]["icon"], "color": right_cards_data[i]["color"]}
        copy_styling(right_cards_raw[i], node_item)
        nodes.append(node_item)

    connections = []
    # 1. Connect all inputs to core_card_0
    for i in range(n_inputs):
        connections.append({
            "path": [f"input_{i}", "core_card_0"],
            "exit_port": "bottom",
            "entry_port": "top"
        })
    # 2. core card connectors
    for i in range(n_cards - 1):
        connections.append({
            "path": [f"core_card_{i}", f"core_card_{i+1}"],
            "exit_port": "right",
            "entry_port": "left"
        })
    # 3. core_card_last -> decision
    connections.append({
        "path": [f"core_card_{n_cards-1}", "decision"],
        "exit_port": "right",
        "entry_port": "left"
    })
    # 4. decision -> output
    connections.append({
        "path": ["decision", "output"],
        "exit_port": "right",
        "entry_port": "left"
    })
    # 5. output -> right_card_0
    connections.append({
        "path": ["output", "right_card_0"],
        "exit_port": "bottom",
        "entry_port": "top"
    })
    # 6. decision -> core_card_0
    connections.append({
        "path": ["decision", "core_card_0"],
        "exit_port": "top",
        "entry_port": "top"
    })
    # 7. left_card_0 -> core_card_0
    connections.append({
        "path": ["left_card_0", "core_card_0"],
        "exit_port": "top",
        "entry_port": "bottom"
    })
    # 8. core_card_2 -> center_card_2 (embeddings to db)
    if n_cards > 2:
        connections.append({
            "path": ["core_card_2", "center_card_2"],
            "exit_port": "bottom",
            "entry_port": "top"
        })
    # 9. core_card_3 -> center_card_3 (graph to db)
    if n_cards > 3:
        connections.append({
            "path": ["core_card_3", "center_card_3"],
            "exit_port": "bottom",
            "entry_port": "top"
        })
    # 10. center_card_3 -> right_card_0
    connections.append({
        "path": ["center_card_3", "right_card_0"],
        "exit_port": "right",
        "entry_port": "left"
    })
    # 11. right_card_0 -> decision
    connections.append({
        "path": ["right_card_0", "decision"],
        "exit_port": "left",
        "entry_port": "bottom"
    })
    
    # 12. left_cards internal flow
    for i in range(len(left_cards_raw) - 1):
        connections.append({
            "path": [f"left_card_{i}", f"left_card_{i+1}"],
            "exit_port": "bottom",
            "entry_port": "top"
        })
    # 13. right_cards internal flow
    for i in range(len(right_cards_raw) - 1):
        connections.append({
            "path": [f"right_card_{i}", f"right_card_{i+1}"],
            "exit_port": "bottom",
            "entry_port": "top"
        })
    # 14. center_card_1 -> center_footer
    connections.append({
        "path": ["center_card_1", "center_footer"],
        "exit_port": "bottom",
        "entry_port": "top"
    })

    spec["nodes"] = nodes
    spec["connections"] = connections
    return spec


# ---------------------------------------------------------------------------
# Node coloring logic
# ---------------------------------------------------------------------------
def get_node_color(node):
    style = resolve_node_style(node)
    if style.get("strokeColor"):
        return style["strokeColor"]
    if node.get("color"):
        return node["color"]
    nid = node["id"]
    if nid == "input_panel": return THEME["green"]
    if nid == "core_panel": return THEME["core_stroke"]
    if nid == "left_panel": return THEME["green"]
    if nid == "center_panel": return THEME["purple"]
    if nid == "right_panel": return THEME["green"]
    if node.get("type") == "diamond": return THEME["green"]
    return THEME["core_stroke"]


def get_segment_color(node_a, node_b):
    nid_a = node_a["id"]
    nid_b = node_b["id"]
    if nid_a == "decision" and nid_b == "core_card_0":
        return THEME["purple"]
    if nid_a == "center_panel" and nid_b == "right_panel":
        return THEME["white"]
    if nid_a == "right_panel" and nid_b == "decision":
        return THEME["amber"]
    
    style_a = resolve_node_style(node_a)
    if style_a.get("strokeColor"):
        return style_a["strokeColor"]
    if node_a.get("color"):
        return node_a["color"]
    if nid_a == "input_panel": return THEME["green"]
    if nid_a == "core_panel": return THEME["core_stroke"]
    if nid_a == "left_panel": return THEME["green"]
    if nid_a == "center_panel": return THEME["purple"]
    if nid_a == "right_panel": return THEME["green"]
    if node_a.get("type") == "diamond": return THEME["green"]
    return THEME["core_stroke"]



# ---------------------------------------------------------------------------
# Brand drawer
# ---------------------------------------------------------------------------
def draw_brand(ex, draw, signature: str, bx: float, by: float) -> None:
    dots = [
        (0,  0,  THEME["cyan"]),
        (10, 8,  THEME["white"]),
        (0,  16, THEME["purple"]),
        (10, 24, THEME["white"]),
        (20, 0,  THEME["white"]),
        (30, 8,  THEME["pink"]),
        (20, 16, THEME["white"]),
        (30, 24, THEME["green"]),
    ]
    for dx, dy, color in dots:
        draw_ellipse(
            ex, draw,
            bx + dx, by + dy,
            5, 5,
            color, color,
            1,
            scaled=False,
        )
    phys_x = (bx + 43) * fc.SCALE_X
    phys_y = (by - 8) * fc.SCALE_Y
    draw_signature(ex, draw, signature, phys_x, phys_y)


# ---------------------------------------------------------------------------
# Post-processing (premium finish)
# ---------------------------------------------------------------------------
def premium_finish(base: Image.Image, spec: dict = None) -> Image.Image:
    width, height = base.size
    img      = base.convert("RGBA")
    is_light = THEME["bg"] in ("#ffffff", "#f8f9fa")

    layout = spec.get("_resolved_layout") if spec else None
    SCALE_X = fc.SCALE_X
    SCALE_Y = fc.SCALE_Y

    if layout:
        rects = []
        if "outer_border" in layout: rects.append((layout["outer_border"], THEME["frame"], 3))
        if "core_panel" in layout: rects.append((layout["core_panel"], THEME["core_stroke"], 3))
        if "center_panel" in layout: rects.append((layout["center_panel"], THEME["purple"], 3))
        if "left_panel" in layout: rects.append((layout["left_panel"], THEME["green"], 3))
        if "right_panel" in layout: rects.append((layout["right_panel"], THEME["green"], 3))
        if "highlight_panel" in layout: rects.append((layout["highlight_panel"], THEME["green"], 2))
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

    img.alpha_composite(_build_glow_layer(0.40).filter(ImageFilter.GaussianBlur(max(2, int(round(14 * min(SCALE_X, SCALE_Y)))))))
    img.alpha_composite(_build_glow_layer(0.60).filter(ImageFilter.GaussianBlur(max(1, int(round( 6 * min(SCALE_X, SCALE_Y)))))))
    img.alpha_composite(_build_glow_layer(1.00).filter(ImageFilter.GaussianBlur(max(1, int(round( 2 * min(SCALE_X, SCALE_Y)))))))

    strip_h = int(height * 0.06)
    for row in range(strip_h):
        t    = row / max(strip_h - 1, 1)
        a    = int(35 * (1.0 - t)) if not is_light else int(15 * (1.0 - t))
        tint = (200, 200, 200, a) if is_light else (0, 0, 0, a)
        ImageDraw.Draw(img).line([(0, height - strip_h + row), (width, height - strip_h + row)], fill=tint)

    grain = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    gd    = ImageDraw.Draw(grain)
    rng   = random.Random(2069769416930414980)
    for _ in range(5500):
        gx   = rng.randrange(width)
        gy   = rng.randrange(height)
        tone = rng.randrange(80, 240)
        gd.point((gx, gy), fill=(tone, tone, tone, rng.randrange(5, 18)))
    img.alpha_composite(grain)

    # Generate vignette mask at a lower resolution and scale up to avoid quadratic CPU complexity
    temp_w = min(width, 256)
    temp_h = min(height, 256)
    cx_v, cy_v = temp_w // 2, temp_h // 2
    max_dist = math.dist((0, 0), (cx_v, cy_v))
    mask_arr = []
    for vy in range(temp_h):
        for vx in range(temp_w):
            dist = math.dist((vx, vy), (cx_v, cy_v)) / max_dist
            val = int(max(0, min(145, (dist - 0.30) * 180)))
            mask_arr.append(val)
    mask_small = Image.new("L", (temp_w, temp_h))
    mask_small.putdata(mask_arr)
    mask = mask_small.resize((width, height), Image.Resampling.BILINEAR)
    vignette_color = (200, 200, 200) if is_light else (0, 0, 0)
    vignette       = Image.new("RGBA", (width, height), vignette_color + (0,))
    vignette.putalpha(mask)
    img.alpha_composite(vignette)

    return img.convert("RGB")


# ---------------------------------------------------------------------------
# Verification and checking
# ---------------------------------------------------------------------------
def frame_diff_report(gif_path: Path) -> dict:
    with Image.open(gif_path) as im:
        raw_picks = [0, max(1, im.n_frames // 4), max(2, im.n_frames // 2),
                     max(3, 3 * im.n_frames // 4), im.n_frames - 1]
        picks  = sorted(set(min(im.n_frames - 1, max(0, p)) for p in raw_picks))
        frames = []
        for idx in picks:
            try:
                im.seek(idx)
                frames.append(im.convert("RGB"))
            except EOFError:
                break
        frame_count = im.n_frames

    diffs = []
    for left, right, a, b in zip(frames, frames[1:], picks, picks[1:]):
        diff  = ImageChops.difference(left, right)
        bbox  = diff.getbbox()
        changed = 0
        if bbox:
            cropped = diff.crop(bbox)
            data    = (cropped.get_flattened_data()
                       if hasattr(cropped, "get_flattened_data")
                       else cropped.getdata())
            changed = sum(1 for px in data if px != (0, 0, 0))
        diffs.append({"from": a, "to": b, "changed_pixels": changed})

    return {"frames": frame_count, "diffs": diffs}


def check_outputs(result: dict, spec: dict) -> dict:
    canvas          = spec.get("canvas", {})
    expected_width  = canvas.get("width",  DEFAULT_W)
    expected_height = canvas.get("height", DEFAULT_H)
    expected_frames = canvas.get("frames", DEFAULT_FRAMES)
    expected_fps    = canvas.get("fps",    DEFAULT_FPS)

    checks = []

    gif_path = Path(result["gif"])
    with Image.open(gif_path) as gif:
        gif_width  = gif.width
        gif_height = gif.height
        gif_frames = gif.n_frames
        duration_ms = gif.info.get("duration")
    actual_fps    = round(1000 / duration_ms, 3) if duration_ms else None
    _raw_duration = int(1000 / expected_fps)
    _gif_duration = max(10, (_raw_duration // 10) * 10)

    checks.extend([
        {"name": "gif_exists",  "ok": gif_path.is_file()},
        {"name": "gif_width",   "ok": gif_width  == expected_width,  "expected": expected_width,  "actual": gif_width},
        {"name": "gif_height",  "ok": gif_height == expected_height, "expected": expected_height, "actual": gif_height},
        {"name": "gif_frames",  "ok": gif_frames == expected_frames, "expected": expected_frames, "actual": gif_frames},
        {"name": "gif_fps",     "ok": duration_ms == _gif_duration,  "expected": expected_fps,   "actual": actual_fps},
    ])

    diff_report = frame_diff_report(gif_path)
    checks.append({
        "name": "gif_has_motion",
        "ok": any(item["changed_pixels"] > 0 for item in diff_report["diffs"]),
        "diffs": diff_report["diffs"],
    })

    excalidraw_path = Path(result["excalidraw"])
    excalidraw      = json.loads(excalidraw_path.read_text(encoding="utf-8"))
    elements        = excalidraw.get("elements", [])
    ids             = [el.get("id") for el in elements]
    text_elements   = [el for el in elements if el.get("type") == "text"]
    expected_family = 5 if spec.get("hand", True) else 1
    checks.extend([
        {"name": "excalidraw_exists",       "ok": excalidraw_path.is_file()},
        {"name": "excalidraw_unique_ids",   "ok": len(ids) == len(set(ids))},
        {"name": "excalidraw_text_font_family", "ok": all(el.get("fontFamily") == expected_family for el in text_elements)},
        {"name": "excalidraw_files_empty",  "ok": excalidraw.get("files") == {}},
    ])

    png_path = Path(result["png"])
    with Image.open(png_path) as png:
        png_width  = png.width
        png_height = png.height
    checks.extend([
        {"name": "png_exists",  "ok": png_path.is_file()},
        {"name": "png_width",   "ok": png_width  == expected_width,  "expected": expected_width,  "actual": png_width},
        {"name": "png_height",  "ok": png_height == expected_height, "expected": expected_height, "actual": png_height},
    ])

    svg_path = Path(result["svg"])
    checks.append({"name": "svg_exists", "ok": svg_path.is_file()})

    return {"ok": all(check["ok"] for check in checks), "checks": checks}


def route_connection_path(
    node_a: dict,
    node_b: dict,
    conn_dict: dict,
    nodes: list,
    normalized_connections: list,
    seg_idx: int,
    total_paths: int,
    path_index: int,
    segment_groups: dict
) -> list:
    """
    Routes a connection segment from node_a to node_b.
    Returns a list of (x, y) coordinate tuples on the logical canvas.
    """
    id_a = node_a["id"]
    id_b = node_b["id"]
    
    # --- 1. Handle Self-Loop ---
    if id_a == id_b:
        x, y = node_a["x"], node_a["y"]
        w, h = node_a["width"], node_a["height"]
        margin = 20
        # 5-point orthogonal polyline around bottom-right corner
        P_start = (x + w, y + h * 0.5)
        P1 = (x + w + margin, y + h * 0.5)
        P2 = (x + w + margin, y + h + margin)
        P3 = (x + w * 0.5, y + h + margin)
        P_end = (x + w * 0.5, y + h)
        path_points = [P_start, P1, P2, P3, P_end]
        
        # Apply parallel offset to self-loop if needed
        key = tuple(sorted([id_a, id_b]))
        group = segment_groups.get(key, [])
        if len(group) > 1:
            idx_in_group = 0
            for idx, item in enumerate(group):
                if item["conn_idx"] == path_index and item["seg_idx"] == seg_idx:
                    idx_in_group = idx
                    break
            spacing = 8
            L = (idx_in_group - (len(group) - 1) / 2) * spacing
            path_points = [
                (P_start[0], P_start[1] + L),
                (P1[0] + L, P1[1] + L),
                (P2[0] + L, P2[1] + L),
                (P3[0] + L, P3[1] + L),
                (P_end[0] + L, P_end[1])
            ]
        return path_points

    # --- 2. Determine Port Directions & Coordinates ---
    C_A = (node_a["x"] + node_a["width"] / 2, node_a["y"] + node_a["height"] / 2)
    C_B = (node_b["x"] + node_b["width"] / 2, node_b["y"] + node_b["height"] / 2)
    dx_centers = C_B[0] - C_A[0]
    dy_centers = C_B[1] - C_A[1]
    
    if abs(dx_centers) >= abs(dy_centers):
        default_start = "right" if dx_centers > 0 else "left"
        default_end = "left" if dx_centers > 0 else "right"
    else:
        default_start = "bottom" if dy_centers > 0 else "top"
        default_end = "top" if dy_centers > 0 else "bottom"

    # Respect overrides
    exit_port = conn_dict.get("exit_port")
    entry_port = conn_dict.get("entry_port")
    
    dir_start = (exit_port if seg_idx == 0 else None) or default_start
    dir_end = (entry_port if seg_idx == len(conn_dict["path"]) - 2 else None) or default_end

    def get_port_coords(node, port_name):
        nx, ny = node["x"], node["y"]
        nw, nh = node["width"], node["height"]
        # Inset port by corner radius to avoid arrowhead clipping on rounded cards
        cr = 0
        if node.get("type") in ("card",):
            node_style = node.get("style", {})
            cr = min(node_style.get("cornerRadius", 12) * 0.5, nw * 0.1, nh * 0.1)
        if port_name == "left":
            return (nx + cr, ny + nh / 2)
        elif port_name == "right":
            return (nx + nw - cr, ny + nh / 2)
        elif port_name == "top":
            return (nx + nw / 2, ny + cr)
        elif port_name == "bottom":
            return (nx + nw / 2, ny + nh - cr)
        return (nx + nw / 2, ny + nh / 2)

    P_start = get_port_coords(node_a, dir_start)
    P_end = get_port_coords(node_b, dir_end)

    # --- 3. Handle Adjacent/Touching Nodes ---
    def nodes_touch_or_overlap(n1, n2, epsilon=1e-2):
        ax1, ay1 = n1["x"], n1["y"]
        ax2, ay2 = ax1 + n1["width"], ay1 + n1["height"]
        bx1, by1 = n2["x"], n2["y"]
        bx2, by2 = bx1 + n2["width"], by1 + n2["height"]
        h_overlap = not (ax2 < bx1 - epsilon or bx2 < ax1 - epsilon)
        v_overlap = not (ay2 < by1 - epsilon or by2 < ay1 - epsilon)
        if h_overlap and v_overlap:
            return True

        if n1.get("orig_x") is not None and n1.get("orig_y") is not None and n2.get("orig_x") is not None and n2.get("orig_y") is not None:
            o_ax1, o_ay1 = n1["orig_x"], n1["orig_y"]
            o_ax2 = o_ax1 + (n1.get("orig_width") if n1.get("orig_width") is not None else n1["width"])
            o_ay2 = o_ay1 + (n1.get("orig_height") if n1.get("orig_height") is not None else n1["height"])
            o_bx1, o_by1 = n2["orig_x"], n2["orig_y"]
            o_bx2 = o_bx1 + (n2.get("orig_width") if n2.get("orig_width") is not None else n2["width"])
            o_by2 = o_by1 + (n2.get("orig_height") if n2.get("orig_height") is not None else n2["height"])
            o_h_overlap = not (o_ax2 < o_bx1 - epsilon or o_bx2 < o_ax1 - epsilon)
            o_v_overlap = not (o_ay2 < o_by1 - epsilon or o_by2 < o_ay1 - epsilon)
            if o_h_overlap and o_v_overlap:
                return True
        return False

    if nodes_touch_or_overlap(node_a, node_b):
        path_points = [P_start, P_start, P_end, P_end]
        key = tuple(sorted([id_a, id_b]))
        group = segment_groups.get(key, [])
        if len(group) > 1:
            idx_in_group = 0
            for idx, item in enumerate(group):
                if item["conn_idx"] == path_index and item["seg_idx"] == seg_idx:
                    idx_in_group = idx
                    break
            spacing = 8
            L = (idx_in_group - (len(group) - 1) / 2) * spacing
            line_dx = P_end[0] - P_start[0]
            line_dy = P_end[1] - P_start[1]
            line_len = math.hypot(line_dx, line_dy)
            if line_len > 0:
                px = -line_dy / line_len
                py = line_dx / line_len
                path_points = [
                    (P_start[0] + px * L, P_start[1] + py * L),
                    (P_start[0] + px * L, P_start[1] + py * L),
                    (P_end[0] + px * L, P_end[1] + py * L),
                    (P_end[0] + px * L, P_end[1] + py * L)
                ]
        return path_points

    # --- 4. A* Pathfinding Grid Algorithm with Port Adapters & Parallel Offsets ---
    import heapq

    # Get grouping & offset index for parallel paths
    key = tuple(sorted([id_a, id_b]))
    group = segment_groups.get(key, [])
    L = 0.0
    if len(group) > 1:
        idx_in_group = 0
        for idx, item in enumerate(group):
            if item["conn_idx"] == path_index and item["seg_idx"] == seg_idx:
                idx_in_group = idx
                break
        spacing = 8.0
        L = (idx_in_group - (len(group) - 1) / 2) * spacing

    # Shift start and end ports along node boundary
    if dir_start in ("left", "right"):
        P_start_offset = (P_start[0], P_start[1] + L)
    else:
        P_start_offset = (P_start[0] + L, P_start[1])

    if dir_end in ("left", "right"):
        P_end_offset = (P_end[0], P_end[1] + L)
    else:
        P_end_offset = (P_end[0] + L, P_end[1])

    # Define helper functions for port stubs
    if abs(L) > 1e-2:
        adapter_len = 12.0
        # start stub:
        if dir_start == "left":
            start_stub = [P_start_offset, (P_start_offset[0] - adapter_len, P_start_offset[1])]
        elif dir_start == "right":
            start_stub = [P_start_offset, (P_start_offset[0] + adapter_len, P_start_offset[1])]
        elif dir_start == "top":
            start_stub = [P_start_offset, (P_start_offset[0], P_start_offset[1] - adapter_len)]
        elif dir_start == "bottom":
            start_stub = [P_start_offset, (P_start_offset[0], P_start_offset[1] + adapter_len)]
        else:
            start_stub = [P_start_offset]

        # end stub:
        if dir_end == "left":
            end_stub = [(P_end_offset[0] - adapter_len, P_end_offset[1]), P_end_offset]
        elif dir_end == "right":
            end_stub = [(P_end_offset[0] + adapter_len, P_end_offset[1]), P_end_offset]
        elif dir_end == "top":
            end_stub = [(P_end_offset[0], P_end_offset[1] - adapter_len), P_end_offset]
        elif dir_end == "bottom":
            end_stub = [(P_end_offset[0], P_end_offset[1] + adapter_len), P_end_offset]
        else:
            end_stub = [P_end_offset]

        a_start = start_stub[-1]
        a_end = end_stub[0]
    else:
        start_stub = []
        end_stub = []
        a_start = P_start
        a_end = P_end

    # Determine obstacles to avoid
    obstacles = []
    for node in nodes:
        if node["id"] in (id_a, id_b):
            continue
        if node.get("type") == "panel":
            # Check if either node_a or node_b is inside this panel
            def is_inside(child, parent):
                return (parent["x"] - 5 <= child["x"] and 
                        child["x"] + child["width"] <= parent["x"] + parent["width"] + 5 and 
                        parent["y"] - 5 <= child["y"] and 
                        child["y"] + child["height"] <= parent["y"] + parent["height"] + 5)
            if is_inside(node_a, node) or is_inside(node_b, node):
                continue
        obstacles.append(node)

    # Helper function to check if a segment intersects any obstacle
    def intersects_obstacle(p1, p2, obs, tolerance=1.0):
        ox1 = obs["x"] + tolerance
        oy1 = obs["y"] + tolerance
        ox2 = obs["x"] + obs["width"] - tolerance
        oy2 = obs["y"] + obs["height"] - tolerance
        
        # Segment bounds
        sx1 = min(p1[0], p2[0])
        sy1 = min(p1[1], p2[1])
        sx2 = max(p1[0], p2[0])
        sy2 = max(p1[1], p2[1])
        
        if sx2 < ox1 or sx1 > ox2 or sy2 < oy1 or sy1 > oy2:
            return False
        return True

    # Construct the routing grid coordinate sets
    margin = 15.0
    x_coords = {a_start[0], a_end[0]}
    y_coords = {a_start[1], a_end[1]}
    for obs in obstacles:
        x_coords.add(obs["x"] - margin)
        x_coords.add(obs["x"] + obs["width"] + margin)
        y_coords.add(obs["y"] - margin)
        y_coords.add(obs["y"] + obs["height"] + margin)

    # Sort coordinates
    sorted_x = sorted(list(x_coords))
    sorted_y = sorted(list(y_coords))

    # Fast lookup for coordinate index
    x_to_idx = {x: i for i, x in enumerate(sorted_x)}
    y_to_idx = {y: j for j, y in enumerate(sorted_y)}

    # A* Search
    start_state = (0.0, 0, a_start, None, [a_start])
    queue = [start_state]
    visited = {}
    path_found = None
    cnt = 0

    while queue:
        cost, _, curr_pt, curr_dir, path = heapq.heappop(queue)
        
        if abs(curr_pt[0] - a_end[0]) < 1e-2 and abs(curr_pt[1] - a_end[1]) < 1e-2:
            path_found = path
            break
            
        state_key = (curr_pt, curr_dir)
        if state_key in visited and visited[state_key] <= cost:
            continue
        visited[state_key] = cost
        
        i = x_to_idx.get(curr_pt[0])
        j = y_to_idx.get(curr_pt[1])
        if i is None or j is None:
            continue
        
        neighbors = []
        if i > 0:
            neighbors.append((sorted_x[i-1], curr_pt[1]))
        if i < len(sorted_x) - 1:
            neighbors.append((sorted_x[i+1], curr_pt[1]))
        if j > 0:
            neighbors.append((curr_pt[0], sorted_y[j-1]))
        if j < len(sorted_y) - 1:
            neighbors.append((curr_pt[0], sorted_y[j+1]))
            
        for nb_pt in neighbors:
            blocked = False
            for obs in obstacles:
                if intersects_obstacle(curr_pt, nb_pt, obs):
                    blocked = True
                    break
            if blocked:
                continue
                
            nb_dir = "H" if abs(curr_pt[1] - nb_pt[1]) < 1e-2 else "V"
            step_dist = math.hypot(nb_pt[0] - curr_pt[0], nb_pt[1] - curr_pt[1])
            
            bend_penalty = 0.0
            if curr_dir is not None and nb_dir != curr_dir:
                bend_penalty = 300.0
                
            new_cost = cost + step_dist + bend_penalty
            nb_key = (nb_pt, nb_dir)
            if nb_key not in visited or new_cost < visited[nb_key]:
                heuristic = abs(nb_pt[0] - a_end[0]) + abs(nb_pt[1] - a_end[1])
                cnt += 1
                heapq.heappush(queue, (new_cost, cnt, nb_pt, nb_dir, path + [nb_pt]))

    # Fallback if no collision-free path found
    if not path_found:
        preferred_shape = "A" if dir_start in ("left", "right") else "B"
        if preferred_shape == "A":
            X_mid = (a_start[0] + a_end[0]) / 2
            path_found = [a_start, (X_mid, a_start[1]), (X_mid, a_end[1]), a_end]
        else:
            Y_mid = (a_start[1] + a_end[1]) / 2
            path_found = [a_start, (a_start[0], Y_mid), (a_end[0], Y_mid), a_end]

    # Apply parallel offset shift to the intermediate points of path_found
    if abs(L) > 1e-2 and len(path_found) > 2:
        # Start shift
        if dir_start in ("left", "right"):
            S_start = (0.0, L)
        else:
            S_start = (L, 0.0)

        # End shift
        if dir_end in ("left", "right"):
            S_end = (0.0, L)
        else:
            S_end = (L, 0.0)

        for idx in range(1, len(path_found) - 1):
            t = idx / (len(path_found) - 1)
            S_x = (1 - t) * S_start[0] + t * S_end[0]
            S_y = (1 - t) * S_start[1] + t * S_end[1]
            path_found[idx] = (path_found[idx][0] + S_x, path_found[idx][1] + S_y)

    # Combine path with stubs
    if start_stub and end_stub:
        routed_path = start_stub[:-1] + path_found + end_stub[1:]
    elif start_stub:
        routed_path = start_stub[:-1] + path_found
    elif end_stub:
        routed_path = path_found + end_stub[1:]
    else:
        routed_path = path_found

    # Simplify collinear path points
    def simplify_path(path):
        if len(path) < 3:
            return path
        simplified = [path[0]]
        for idx in range(1, len(path) - 1):
            prev = simplified[-1]
            curr = path[idx]
            nxt = path[idx + 1]
            
            is_collinear = False
            if abs(prev[0] - curr[0]) < 1e-2 and abs(curr[0] - nxt[0]) < 1e-2:
                is_collinear = True
            elif abs(prev[1] - curr[1]) < 1e-2 and abs(curr[1] - nxt[1]) < 1e-2:
                is_collinear = True
                
            if not is_collinear:
                simplified.append(curr)
        simplified.append(path[-1])
        return simplified

    routed_path = simplify_path(routed_path)
    return routed_path


# ---------------------------------------------------------------------------
# Main rendering entry point
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Dynamic diagram rendering CLI.")
    parser.add_argument("--spec", required=True, help="Spec JSON path.")
    parser.add_argument("--outdir", required=True, help="Output directory.")
    parser.add_argument("--basename", default="animated-diagram", help="Output basename.")
    parser.add_argument("--verify", action="store_true", help="Print frame diff statistics.")
    parser.add_argument("--check", action="store_true", help="Validate output contracts.")
    parser.add_argument("--theme", default="dark", help="Color theme.")
    parser.add_argument("--rebrand", action="store_true", help="Rebrand strings.")
    args = parser.parse_args()

    # Load and potentially convert spec
    spec_path = Path(args.spec)
    try:
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
    except Exception as e:
        sys.stderr.write(f"Validation Error: Failed to parse JSON spec: {e}\n")
        sys.exit(1)

    # 1. Validate nodes list type if present
    if "nodes" in spec and not isinstance(spec["nodes"], list):
        sys.stderr.write("Validation Error: nodes must be a list\n")
        sys.exit(1)

    # Set global hands setting
    fc.HAND = spec.get("hand", True)

    spec_had_nodes = "nodes" in spec
    if not spec_had_nodes:
        # Convert legacy layout format to dynamic nodes & connections
        spec = convert_legacy_spec_to_dynamic(spec)

    # 2. Re-validate nodes list type
    if "nodes" not in spec or not isinstance(spec["nodes"], list):
        sys.stderr.write("Validation Error: nodes must be a list\n")
        sys.exit(1)

    # 3. Canvas dimensions validation
    canvas_spec = spec.get("canvas") or {}
    if "width" in canvas_spec:
        try:
            w_val = float(canvas_spec["width"])
            if w_val <= 0 or not w_val.is_integer():
                raise ValueError
            canvas_spec["width"] = int(w_val)
        except (ValueError, TypeError):
            sys.stderr.write("Validation Error: canvas dimensions must be positive integers\n")
            sys.exit(1)
    if "height" in canvas_spec:
        try:
            h_val = float(canvas_spec["height"])
            if h_val <= 0 or not h_val.is_integer():
                raise ValueError
            canvas_spec["height"] = int(h_val)
        except (ValueError, TypeError):
            sys.stderr.write("Validation Error: canvas dimensions must be positive integers\n")
            sys.exit(1)

    # 4. Node coordinates validation and casting to float
    for node in spec["nodes"]:
        if not isinstance(node, dict):
            sys.stderr.write("Validation Error: each node must be a dictionary\n")
            sys.exit(1)
        for coord in ("x", "y"):
            if coord in node:
                try:
                    node[coord] = float(node[coord])
                except (ValueError, TypeError):
                    sys.stderr.write("Validation Error\n")
                    sys.exit(1)

    # 5. Parent panel cycle detection
    parent_map = {}
    for node in spec["nodes"]:
        nid = node.get("id")
        parent_id = node.get("parent")
        if nid and parent_id:
            parent_map[nid] = parent_id

    for start_node in parent_map:
        visited = set()
        curr = start_node
        while curr in parent_map:
            if curr in visited:
                sys.stderr.write("Validation Error: parent panel cycle detected\n")
                sys.exit(1)
            visited.add(curr)
            curr = parent_map[curr]

    # Store original coordinates for adjacency check during routing
    for node in spec["nodes"]:
        if isinstance(node, dict):
            if "x" in node:
                node["orig_x"] = node["x"]
            if "y" in node:
                node["orig_y"] = node["y"]
            if "width" in node:
                node["orig_width"] = node["width"]
            if "height" in node:
                node["orig_height"] = node["height"]

    # Rebrand if requested
    if args.rebrand or spec.get("rebrand", False):
        spec = apply_rebranding(spec)

    # Set theme
    theme_name = spec.get("theme", args.theme)
    set_theme(theme_name)

    # Resolve layout overlaps and sizes dynamically
    spec = resolve_diagram_layout(spec)

    nodes = spec.get("nodes")
    if not nodes:
        sys.stderr.write("Validation Error: nodes list is empty.\n")
        sys.exit(1)

    connections_raw = spec.get("connections", [])
    normalized_connections = []
    for conn in connections_raw:
        if isinstance(conn, dict):
            normalized_connections.append(conn)
        else:
            normalized_connections.append({"path": conn})
    nodes_map = {n["id"]: n for n in nodes}

    # Validate connections
    for conn_dict in normalized_connections:
        conn = conn_dict["path"]
        for node_id in conn:
            if node_id not in nodes_map:
                sys.stderr.write(f"Validation Error: Connection references nonexistent node ID '{node_id}'.\n")
                sys.exit(1)

    # Canvas dimensions and bounds
    canvas_spec = spec.get("canvas") or {}
    canvas_width = canvas_spec.get("width") or DEFAULT_W
    canvas_height = canvas_spec.get("height") or DEFAULT_H

    logical_width = max((n["x"] + n["width"] for n in nodes), default=0.0) + 60
    logical_height = max((n["y"] + n["height"] for n in nodes), default=0.0) + 90

    scale_x = min(100.0, canvas_width / logical_width) if logical_width > 0 else 1.0
    scale_y = min(100.0, canvas_height / logical_height) if logical_height > 0 else 1.0

    # Set globals
    fc.SCALE_X = scale_x
    fc.SCALE_Y = scale_y

    # 1. Group segments by unordered node ID pairs for parallel offset calculation
    segment_groups = {}
    for p, conn_dict in enumerate(normalized_connections):
        conn = conn_dict["path"]
        for seg_idx in range(len(conn) - 1):
            id_a = conn[seg_idx]
            id_b = conn[seg_idx + 1]
            key = tuple(sorted([id_a, id_b]))
            if key not in segment_groups:
                segment_groups[key] = []
            segment_groups[key].append({
                "conn_idx": p,
                "seg_idx": seg_idx,
                "id_a": id_a,
                "id_b": id_b
            })

    # 2. Pre-compute routed paths
    routed_segments_map = {}
    total_paths = len(normalized_connections)
    for p, conn_dict in enumerate(normalized_connections):
        conn = conn_dict["path"]
        for seg_idx in range(len(conn) - 1):
            id_a = conn[seg_idx]
            id_b = conn[seg_idx + 1]
            node_a = nodes_map[id_a]
            node_b = nodes_map[id_b]
            path_points = route_connection_path(
                node_a, node_b, conn_dict, nodes, normalized_connections,
                seg_idx, total_paths, p, segment_groups
            )
            routed_segments_map[(p, seg_idx)] = path_points

    # Calculate paths for routing
    resolved_paths = []
    for p, conn_dict in enumerate(normalized_connections):
        conn = conn_dict["path"]
        conn_color = conn_dict.get("color")
        for seg_idx in range(len(conn) - 1):
            id_a = conn[seg_idx]
            id_b = conn[seg_idx + 1]
            node_a = nodes_map[id_a]
            node_b = nodes_map[id_b]

            path_points = routed_segments_map[(p, seg_idx)]
            scaled_pts = [(px * scale_x, py * scale_y) for px, py in path_points]
            color = conn_color or get_segment_color(node_a, node_b)
            offset = p / max(1, total_paths)
            resolved_paths.append((scaled_pts, color, offset))

    spec["_resolved_paths"] = resolved_paths

    # Calculate pulse targets
    pulse_targets = []
    for node in nodes:
        if node.get("type") == "panel":
            x1 = node["x"] * scale_x
            y1 = node["y"] * scale_y
            x2 = (node["x"] + node["width"]) * scale_x
            y2 = (node["y"] + node["height"]) * scale_y
            color = get_node_color(node)
            pulse_targets.append(((x1, y1, x2, y2), color))

    spec["_resolved_pulse_targets"] = pulse_targets

    # Calculate _resolved_layout for post-processing
    outer_border_x = 18
    outer_border_y = 117
    outer_border_w = max(100.0, max(n["x"] + n["width"] for n in nodes) + 30 - outer_border_x)
    outer_border_h = max(100.0, max(n["y"] + n["height"] for n in nodes) + 55 - outer_border_y)

    layout = {
        "highlight_panel": (600, 27, 992, 99),
        "outer_border": (outer_border_x, outer_border_y, outer_border_x + outer_border_w, outer_border_y + outer_border_h)
    }
    for node in nodes:
        if node["id"] in ("core_panel", "center_panel", "left_panel", "right_panel"):
            layout[node["id"]] = (node["x"], node["y"], node["x"] + node["width"], node["y"] + node["height"])
    spec["_resolved_layout"] = layout

    # Initialize Excal and PIL Image
    ex_doc = Excal(canvas_width, canvas_height)
    img    = Image.new("RGBA", (canvas_width * SCALE, canvas_height * SCALE), hex_rgba(THEME["bg"]))
    draw   = ImageDraw.Draw(img)

    # 1. Draw Title Block if present in spec
    if "title" in spec:
        title_spec = spec["title"] or {}
        highlight_text = title_spec.get("highlight", "")
        prefix_text    = title_spec.get("prefix", "")
        subtitle_text  = title_spec.get("subtitle", "")
        
        draw_line(ex_doc, draw, [(29, 31), (29, 78)], THEME["purple"], 11, scaled=False)
        if prefix_text:
            draw_text(ex_doc, draw, prefix_text, 45, 14, 535, 66, 47, THEME["white"], "left", hand=fc.HAND, bold=True, scaled=False)
        if highlight_text:
            _hl_font = load_font(44, hand=fc.HAND, bold=True)
            _hl_tw, _ = text_size(draw, highlight_text, _hl_font)
            _hl_tw    = max(int(_hl_tw / SCALE), 200)
            _hl_pad_x = 22
            hl_rect_x = 600
            hl_rect_y = 27
            hl_rect_w = _hl_tw + _hl_pad_x * 2
            hl_rect_h = 72
            draw_rect(ex_doc, draw, hl_rect_x, hl_rect_y, hl_rect_w, hl_rect_h, THEME["highlight"], THEME["highlight"], 2, 16, scaled=False)
            draw_text(ex_doc, draw, highlight_text, hl_rect_x + _hl_pad_x, 19, hl_rect_w - _hl_pad_x * 2, 76, 44, THEME["green"], "center", hand=fc.HAND, bold=True, scaled=False)
        if subtitle_text:
            draw_text(ex_doc, draw, subtitle_text, 104, 90, 420, 25, 15, THEME["muted"], "left", scaled=False)

    # 2. Draw Outer Border
    draw_rect(ex_doc, draw, outer_border_x, outer_border_y, outer_border_w, outer_border_h, THEME["frame"], None, 2, 29, scaled=False)

    # 3. Signature drawing moved to end of drawing process to preserve element ordering for tests
    pass

    # 4. Draw Nodes
    for node in nodes:
        ntype = node["type"]
        nx, ny = node["x"], node["y"]
        nw, nh = node["width"], node["height"]
        ntitle = node.get("title", "")
        nbody = node.get("body", "")
        ncolor = node.get("color")
        nicon = node.get("icon")

        style = resolve_node_style(node)

        if ntype == "panel":
            stroke = style["strokeColor"] or ncolor or get_node_color(node)
            stroke_width = style["strokeWidth"] or 2
            corner_radius = style["cornerRadius"] or 20
            draw_rect(ex_doc, draw, nx, ny, nw, nh, stroke, None, stroke_width, corner_radius, style=style["strokeStyle"], scaled=False)
            ex_doc.elements[-1]["id"] = node["id"]
            
            # Panel Title
            hand_font = style["hand"]
            bold_font = style.get("bold", True)
            
            offsets = node.get("layout_offsets")
            if offsets and "title" in offsets:
                t_opt = offsets["title"]
                draw_text(ex_doc, draw, ntitle, nx + t_opt["x"], ny + t_opt["y"], t_opt["w"], t_opt["h"], t_opt["size"], THEME["white"], "left" if node["id"] == "left_panel" else "center", hand=hand_font, bold=bold_font, fit=True, min_size=t_opt.get("min_size", 12), scaled=False)
            else:
                if node["id"] == "left_panel":
                    draw_text(ex_doc, draw, ntitle, nx + 19, ny + 17, nw - 130, 30, 20, THEME["white"], "left", hand=hand_font, bold=bold_font, fit=True, min_size=12, scaled=False)
                else:
                    draw_text(ex_doc, draw, ntitle, nx + 15, ny + 15, nw - 30, 34, 22, THEME["white"], "center", hand=hand_font, bold=bold_font, fit=True, min_size=12, scaled=False)

            # Subtitle/Badge for converted legacy specs
            if not spec_had_nodes:
                if node["id"] == "left_panel" and "left_panel" in spec:
                    badge = spec["left_panel"].get("badge")
                    if badge:
                        bx = nx + nw - 110
                        by = ny + 20
                        bw = 90
                        bh = 22
                        draw_rect(ex_doc, draw, bx, by, bw, bh, THEME["green"], "#082b1b", 1, 6, scaled=False)
                        draw_text(ex_doc, draw, badge.upper(), bx, by + 4, bw, bh - 6, 9, THEME["green"], "center", bold=True, scaled=False)
                elif node["id"] == "center_panel" and "center_panel" in spec:
                    sub = spec["center_panel"].get("subtitle")
                    if sub:
                        draw_text(ex_doc, draw, sub, nx + (nw - 300) / 2, ny + 34, 300, 24, 14, THEME["white"], "center", scaled=False)
                elif node["id"] == "core_panel" and "core" in spec:
                    sub = spec["core"].get("subtitle")
                    if sub:
                        draw_text(ex_doc, draw, sub, nx + 390, ny + 24, 720, 20, 11, THEME["muted"], "left", scaled=False)

        elif ntype == "card":
            stroke = style["strokeColor"] or ncolor or THEME["core_stroke"]
            fill = style["fillColor"] or THEME["blue_fill"]
            stroke_width = style["strokeWidth"] or 2
            corner_radius = style["cornerRadius"] or 12
            draw_rect(ex_doc, draw, nx, ny, nw, nh, stroke, fill, stroke_width, corner_radius, style=style["strokeStyle"], scaled=False)
            ex_doc.elements[-1]["id"] = node["id"]
            
            offsets = node.get("layout_offsets")
            if offsets:
                icon_opt = offsets.get("icon")
                if icon_opt and icon_opt.get("draw") and nicon and node["id"] != "center_footer":
                    icon(ex_doc, draw, nicon, nx + icon_opt["x"], ny + icon_opt["y"], stroke, 0.8, scaled=False)
                
                hand_font = fc.HAND if "core_card" in node["id"] else style["hand"]
                bold_font = style.get("bold", True)
                
                title_opt = offsets["title"]
                start_sz = 20 if "core_card" in node["id"] else 18
                draw_text(ex_doc, draw, ntitle, nx + title_opt["x"], ny + title_opt["y"], title_opt["w"], title_opt["h"], start_sz, THEME["white"], "center", hand=hand_font, bold=bold_font, fit=True, min_size=title_opt.get("min_size", 12), scaled=False)
                
                body_opt = offsets.get("body")
                if body_opt and nbody:
                    start_sz = 14
                    draw_text(ex_doc, draw, nbody, nx + body_opt["x"], ny + body_opt["y"], body_opt["w"], body_opt["h"], start_sz, THEME["white"], "center", spacing=3, fit=True, min_size=body_opt.get("min_size", 9), scaled=False)
            else:
                if nicon and node["id"] != "center_footer":
                    icon(ex_doc, draw, nicon, nx + 14, ny + 13, stroke, 0.8, scaled=False)
                    
                hand_font = fc.HAND if "core_card" in node["id"] else style["hand"]
                bold_font = style.get("bold", True)
                if "center_card" in node["id"]:
                    draw_text(ex_doc, draw, ntitle, nx + 52, ny + 11, nw - 62, 30, 18, THEME["white"], "center", hand=hand_font, bold=bold_font, fit=True, min_size=12, scaled=False)
                    if nbody:
                        draw_text(ex_doc, draw, nbody, nx + 10, ny + 42, nw - 20, nh - 45, 12, THEME["white"], "center", spacing=3, fit=True, min_size=9, scaled=False)
                elif node["id"] == "center_footer":
                    draw_text(ex_doc, draw, ntitle, nx + 12, ny + 11, nw - 24, nh - 22, 14, THEME["white"], "center", hand=hand_font, bold=bold_font, fit=True, min_size=11, scaled=False)
                elif node["id"] == "output":
                    draw_text(ex_doc, draw, ntitle, nx + 48, ny + 11, nw - 58, 30, 18, THEME["white"], "center", hand=hand_font, bold=bold_font, fit=True, min_size=12, scaled=False)
                    if nbody:
                        draw_text(ex_doc, draw, nbody, nx + 10, ny + 42, nw - 20, nh - 45, 12, THEME["white"], "center", spacing=3, fit=True, min_size=9, scaled=False)
                else:
                    draw_text(ex_doc, draw, ntitle, nx + 100, ny + 11, nw - 110, 30, 18, THEME["white"], "center", hand=hand_font, bold=bold_font, fit=True, min_size=12, scaled=False)
                    if nbody:
                        draw_text(ex_doc, draw, nbody, nx + 85, ny + 42, nw - 95, nh - 45, 12, THEME["white"], "center", spacing=3, fit=True, min_size=9, scaled=False)

        elif ntype == "input":
            stroke = style["strokeColor"] or ncolor or THEME["cyan"]
            cx = nx + nw / 2
            cy = ny
            icon(ex_doc, draw, nicon or "file", cx - 16, cy + 1, stroke, 0.65, scaled=False)
            
            hand_font = style["hand"]
            bold_font = style.get("bold", False)
            
            offsets = node.get("layout_offsets")
            if offsets and "title" in offsets:
                t_opt = offsets["title"]
                draw_text(ex_doc, draw, ntitle, nx + t_opt["x"], cy + t_opt["y"], t_opt["w"], t_opt["h"], 13, THEME["white"], "center", hand=hand_font, bold=bold_font, fit=True, min_size=t_opt.get("min_size", 9), scaled=False)
            else:
                draw_text(ex_doc, draw, ntitle, nx, cy + 34, nw, nh - 34, 13, THEME["white"], "center", hand=hand_font, bold=bold_font, fit=True, min_size=9, scaled=False)

        elif ntype == "diamond":
            stroke = style["strokeColor"] or ncolor or THEME["green"]
            fill = style["fillColor"] or "#052515"
            stroke_width = style["strokeWidth"] or 2
            draw_diamond(ex_doc, draw, nx, ny, nw, nh, stroke, fill, stroke_width, scaled=False)
            ex_doc.elements[-1]["id"] = node["id"]
            
            offsets = node.get("layout_offsets")
            if offsets:
                title_opt = offsets["title"]
                draw_text(ex_doc, draw, ntitle, nx + title_opt["x"], ny + title_opt["y"], title_opt["w"], title_opt["h"], 18, THEME["white"], "center", hand=style["hand"], bold=True, fit=True, min_size=title_opt.get("min_size", 10), scaled=False)
                body_opt = offsets.get("body")
                if body_opt and nbody:
                    draw_text(ex_doc, draw, nbody, nx + body_opt["x"], ny + body_opt["y"], body_opt["w"], body_opt["h"], 13, THEME["white"], "center", hand=style["hand"], bold=style["bold"], fit=True, min_size=body_opt.get("min_size", 10), scaled=False)
            else:
                title_h = nh * 0.25
                body_h = nh * 0.35
                draw_text(ex_doc, draw, ntitle, nx + nw * 0.25, ny + nh * 0.25, nw * 0.5, title_h, 18, THEME["white"], "center", hand=style["hand"], bold=True, fit=True, min_size=10, scaled=False)
                if nbody:
                    draw_text(ex_doc, draw, nbody, nx + nw * 0.25, ny + nh * 0.25 + title_h + 3, nw * 0.5, body_h, 13, THEME["white"], "center", hand=style["hand"], bold=style["bold"], fit=True, min_size=10, scaled=False)
        elif ntype == "text":
            align = node.get("align", "center")
            size = node.get("size", 14)
            color = style["strokeColor"] or ncolor or THEME["white"]
            bold = style["bold"]
            hand = style["hand"]
            
            offsets = node.get("layout_offsets")
            if offsets and "title" in offsets:
                t_opt = offsets["title"]
                draw_text(ex_doc, draw, ntitle, nx + t_opt["x"], ny + t_opt["y"], t_opt["w"], t_opt["h"], t_opt["size"], color, align, hand=hand, bold=bold, fit=True, min_size=t_opt.get("min_size", 9), scaled=False)
            else:
                draw_text(ex_doc, draw, ntitle, nx, ny, nw, nh, size, color, align, hand=hand, bold=bold, fit=True, min_size=9, scaled=False)


    # 5. Converted legacy specs extra labels
    if not spec_had_nodes:
        decision_node = nodes_map["decision"]
        card0_node = nodes_map["core_card_0"]
        p_loop_start = (decision_node["x"], decision_node["y"] + decision_node["height"] / 2)
        p_loop_end = (card0_node["x"] + card0_node["width"] / 2, card0_node["y"] + card0_node["height"])

        loop_lbl_x = p_loop_end[0] + (p_loop_start[0] - p_loop_end[0] - 540) / 2
        loop_lbl_y = 398
        draw_text(ex_doc, draw, spec.get("loop_label", "Loop until checked and updated"), loop_lbl_x, loop_lbl_y, 540, 25, 14, THEME["white"], "center", scaled=False)

        retry_lbl_x = p_loop_end[0] + (p_loop_start[0] - p_loop_end[0] - 250) / 2
        retry_lbl_y = 446
        draw_text(ex_doc, draw, spec.get("retry_label", "No / missing source or conflict"), retry_lbl_x, retry_lbl_y, 250, 24, 14, THEME["white"], "center", scaled=False)

        left_panel_node = nodes_map["left_panel"]
        draw_text(ex_doc, draw, "Ingest Events", (left_panel_node["x"] + left_panel_node["width"] / 2) - 80, left_panel_node["y"] - 25, 160, 22, 14, THEME["white"], "center", scaled=False)

        right_panel_node = nodes_map["right_panel"]
        # Ensure label doesn't overlap the rightmost core card
        _consensus_right = max((n["x"] + n["width"] for n in nodes if n.get("type") == "card" and n["id"].startswith("core_card")), default=p_loop_start[0])
        _label_left = max(p_loop_start[0], _consensus_right + 10)
        reusable_x = _label_left + (right_panel_node["x"] - _label_left - 75) / 2
        pr_start_y = right_panel_node["y"]
        pr_end_y = decision_node["y"] + decision_node["height"]
        pr_ymid = pr_end_y + (pr_start_y - pr_end_y) / 2
        draw_text(ex_doc, draw, spec.get("right_panel", {}).get("return_label", "Reusable"), reusable_x, pr_ymid - 22, 75, 23, 16, THEME["white"], "center", scaled=False)
        
        center_panel_node = nodes_map["center_panel"]
        _cp_right = center_panel_node["x"] + center_panel_node["width"]
        _rp_left  = right_panel_node["x"]
        if _rp_left > _cp_right:
            _lbl_gap = _rp_left - _cp_right
        else:
            # Panels at different Y levels — measure gap between last center card and right panel
            _last_cc_right = max((n["x"] + n["width"] for n in nodes if "center_card" in n["id"]), default=_cp_right)
            _lbl_gap = _rp_left - _last_cc_right
        _lbl_w   = max(70, min(120, abs(_lbl_gap) - 8))
        _lbl_x   = _rp_left - _lbl_w - 4 if _lbl_gap < 0 else _cp_right + (_lbl_gap - _lbl_w) / 2
        draw_text(ex_doc, draw, spec.get("right_panel", {}).get("incoming_label", "Compile"), _lbl_x, center_panel_node["y"] + 116, _lbl_w, 44, 11, THEME["white"], "center", fit=True, min_size=9, scaled=False)

    # 6. Draw Connections
    for p, conn_dict in enumerate(normalized_connections):
        conn = conn_dict["path"]
        conn_color = conn_dict.get("color")
        conn_label = conn_dict.get("label")
        for seg_idx in range(len(conn) - 1):
            id_a = conn[seg_idx]
            id_b = conn[seg_idx + 1]
            node_a = nodes_map[id_a]
            node_b = nodes_map[id_b]

            path_points = routed_segments_map[(p, seg_idx)]
            style = "dashed" if (id_a == "decision" and id_b == "core_card_0") or (id_a == "center_panel" and id_b == "center_footer") else "solid"
            color = conn_color or get_segment_color(node_a, node_b)
            stroke = THEME["muted"] if style == "dashed" else color
            draw_line(ex_doc, draw, path_points, stroke, 2, style, arrow=True, scaled=False)

            if conn_label and seg_idx == 0:
                # Place label near the middle of the first segment
                P_start = path_points[0]
                P_mid1 = path_points[1] if len(path_points) > 1 else P_start
                lbl_x = (P_start[0] + P_mid1[0]) / 2
                lbl_y = (P_start[1] + P_mid1[1]) / 2 - 12
                if abs(P_start[0] - P_mid1[0]) < 1:
                    lbl_x = P_start[0] + 12
                    lbl_y = (P_start[1] + P_mid1[1]) / 2
                draw_text(ex_doc, draw, conn_label, lbl_x - 50, lbl_y - 10, 100, 20, 12, THEME["white"], "center", hand=fc.HAND, scaled=False)

    # 6b. Draw Signature/Brand watermark last to ensure node/text ordering for tests
    signature = spec.get("signature", "@FlowDraft")
    canvas_spec = spec.get("canvas") or {}
    bx = canvas_spec.get("signature_x")
    by = canvas_spec.get("signature_y")
    if bx is None or by is None:
        bx = (outer_border_x + outer_border_w) - 255
        by = 143
        if bx < 600:
            bx = 955
    draw_brand(ex_doc, draw, signature, bx, by)

    # 7. Post-process static image
    static_img = img.resize((canvas_width, canvas_height), Image.Resampling.LANCZOS).convert("RGB")
    final_img = premium_finish(static_img, spec)

    # 8. Create output directory
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    png_path = outdir / f"{args.basename}.png"
    gif_path = outdir / f"{args.basename}.gif"
    excal_path = outdir / f"{args.basename}.excalidraw"
    svg_path = outdir / f"{args.basename}.svg"

    # Save PNG
    final_img.save(png_path, "PNG")

    # Save GIF animation
    num_frames = canvas_spec.get("frames")
    if num_frames is None or not isinstance(num_frames, int) or num_frames <= 0:
        num_frames = DEFAULT_FRAMES
    frames = [animate_frame(final_img, i, num_frames, spec) for i in range(num_frames)]
    fps = canvas_spec.get("fps", DEFAULT_FPS)
    if fps is None or not isinstance(fps, (int, float)) or fps <= 0:
        fps = DEFAULT_FPS
    duration = int(1000 / fps)
    frames[0].save(
        gif_path,
        save_all=True, append_images=frames[1:],
        duration=duration, loop=0, optimize=False,
    )

    # Save Excalidraw JSON
    ex_doc.write(excal_path)

    # Save SVG
    svg_content = excalidraw_to_svg(ex_doc.elements, ex_doc.width, ex_doc.height, THEME["bg"])
    svg_path.write_text(svg_content, encoding="utf-8")

    result = {
        "png": str(png_path),
        "gif": str(gif_path),
        "excalidraw": str(excal_path),
        "svg": str(svg_path),
        "elements": len(ex_doc.elements)
    }

    if args.verify:
        result["verification"] = frame_diff_report(gif_path)
    if args.check:
        result["checks"] = check_outputs(result, spec)

    # Print JSON result to stdout
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if args.check and not result["checks"]["ok"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
