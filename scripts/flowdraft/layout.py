"""
flowdraft.layout
----------------
Dynamic bounding box calculations and hierarchical overlap resolution.
"""

import math
from PIL import Image, ImageDraw
from scripts.flowdraft.constants import SCALE, THEME
import scripts.flowdraft.constants as fc
from scripts.flowdraft.fonts import load_font, text_size
from scripts.flowdraft.text import fit_text

def resolve_node_style(node):
    """Parse style properties from the node's style dictionary with fallback defaults."""
    style = node.get("style", {})
    
    # Fill & stroke colors
    fill_color = style.get("fillColor") or style.get("fill")
    stroke_color = style.get("strokeColor") or style.get("stroke") or node.get("color")
    color_preset = style.get("color_preset") or node.get("color_preset")
    
    if color_preset:
        color_preset = color_preset.lower()
        if color_preset in THEME:
            stroke_color = stroke_color or THEME[color_preset]
            fill_key = f"{color_preset}_fill"
            if fill_key in THEME:
                fill_color = fill_color or THEME[fill_key]
            else:
                if color_preset == "cyan":
                    fill_color = fill_color or THEME.get("blue_fill")
                else:
                    fill_color = fill_color or THEME.get("bg")
        else:
            if color_preset == "blue":
                stroke_color = stroke_color or THEME.get("cyan")
                fill_color = fill_color or THEME.get("blue_fill")
            elif color_preset == "core":
                stroke_color = stroke_color or THEME.get("core_stroke")
                fill_color = fill_color or THEME.get("core_fill")
                
    # Helper to validate hex colors
    def is_valid_hex(val):
        if not val or not isinstance(val, str):
            return False
        v = val.lstrip("#")
        return len(v) == 6 and all(c in "0123456789abcdefABCDEF" for c in v)

    if fill_color and fill_color != "transparent" and not is_valid_hex(fill_color):
        fill_color = None
    if stroke_color and stroke_color != "transparent" and not is_valid_hex(stroke_color):
        stroke_color = None

    # Other style properties
    stroke_width = style.get("strokeWidth") or style.get("border_width")
    try:
        if stroke_width is not None:
            stroke_width = float(stroke_width)
            if stroke_width < 0:
                stroke_width = 2
        else:
            stroke_width = 2
    except (ValueError, TypeError):
        stroke_width = 2
        
    stroke_style = style.get("strokeStyle") or style.get("border_style") or "solid"
    if stroke_style not in ("solid", "dashed", "dotted"):
        stroke_style = "solid"
    
    # Type-specific corner radius defaults
    ntype = node.get("type", "card")
    default_radius = 12
    if ntype == "panel":
        default_radius = 20
    elif ntype in ("diamond", "input", "text"):
        default_radius = 0
        
    corner_radius = style.get("cornerRadius") or style.get("corner_radius")
    if corner_radius is not None:
        try:
            corner_radius = float(corner_radius)
            if corner_radius < 0:
                corner_radius = default_radius
        except (ValueError, TypeError):
            corner_radius = default_radius
    else:
        corner_radius = default_radius
        
    bold = style.get("bold", False)
    hand = style.get("hand")
    if hand is None:
        hand = fc.HAND if hasattr(fc, "HAND") else True
        
    margin = style.get("margin") or node.get("margin") or 15
    padding = style.get("padding") or node.get("padding")
    
    return {
        "fillColor": fill_color,
        "strokeColor": stroke_color,
        "strokeWidth": stroke_width,
        "strokeStyle": stroke_style,
        "cornerRadius": corner_radius,
        "bold": bold,
        "hand": hand,
        "margin": margin,
        "padding": padding
    }

def layout_text_fit_local(
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
    """Helper to wrap and fit text inside a box using the shared fit_text utility,

    returning the resolved logical width and height.
    """
    raw_text = str(text)
    fitted_text, fitted_size, fitted_font = fit_text(
        draw, raw_text, default_w, default_h, start_size,
        min_size=min_size, hand=hand, bold=bold, spacing=spacing, wrap=wrap,
    )
    tw, th = text_size(draw, fitted_text, fitted_font, spacing=spacing)
    unscaled_tw = tw / SCALE
    unscaled_th = th / SCALE
    if unscaled_tw <= default_w and unscaled_th <= default_h:
        return default_w, default_h
    return max(default_w, unscaled_tw), max(default_h, unscaled_th)

def compute_node_bounds(node, draw: ImageDraw.ImageDraw):
    """Compute precise dynamic bounding box for elements based on text wrapping,

    fonts, icons, styling parameters, and margins.
    """
    ntype = node.get("type", "card")
    if ntype == "panel":
        return  # Panels computed from children later
        
    style = resolve_node_style(node)
    base_w = node.get("width") or 260
    base_h = node.get("height") or 90
    
    title = node.get("title", "")
    body = node.get("body", "")
    
    if ntype == "card":
        title_w_lim = base_w - 110
        body_w_lim = base_w - 95
        
        if title:
            # Cards in core use hand_font (title), others don't by default
            is_core = "core_card" in node.get("id", "")
            t_w, t_h = layout_text_fit_local(
                draw, title, title_w_lim, 28, 20, 15, hand=is_core or style["hand"], bold=True
            )
        else:
            t_w, t_h = 0, 0
            
        if body:
            b_w, b_h = layout_text_fit_local(
                draw, body, body_w_lim, base_h - 45 - 7, 14, 11, hand=style["hand"], bold=False
            )
        else:
            b_w, b_h = 0, 0
            
        extra_w = max(0, t_w - title_w_lim, b_w - body_w_lim)
        extra_h = max(0, (t_h - 28) + (b_h - (base_h - 45 - 7)))
        
        node["width"] = base_w + extra_w
        node["height"] = base_h + extra_h
        
    elif ntype == "diamond":
        title_w_lim = base_w * 0.7
        body_w_lim = base_w * 0.7
        title_h_lim = base_h * 0.3
        body_h_lim = base_h * 0.4
        
        if title:
            t_w, t_h = layout_text_fit_local(
                draw, title, title_w_lim, title_h_lim, 18, 10, hand=style["hand"], bold=True
            )
        else:
            t_w, t_h = 0, 0
            
        if body:
            b_w, b_h = layout_text_fit_local(
                draw, body, body_w_lim, body_h_lim, 13, 10, hand=style["hand"], bold=False
            )
        else:
            b_w, b_h = 0, 0
            
        extra_w = max(0, t_w - title_w_lim, b_w - body_w_lim)
        extra_h = max(0, (t_h - title_h_lim) + (b_h - body_h_lim))
        
        node["width"] = (base_w * 0.7 + extra_w) / 0.7
        node["height"] = (base_h * 0.7 + extra_h) / 0.7
        
    elif ntype == "input":
        if title:
            t_w, t_h = layout_text_fit_local(
                draw, title, base_w, max(24, base_h - 34), 13, 9, hand=style["hand"], bold=False
            )
        else:
            t_w, t_h = 0, 0
        node["width"] = max(base_w, t_w)
        node["height"] = max(base_h, t_h + 34)
        
    elif ntype == "text":
        size = node.get("size", 14)
        bold = node.get("bold", False)
        hand = node.get("hand", True)
        if title:
            t_w, t_h = layout_text_fit_local(
                draw, title, base_w, base_h, size, 9, hand=hand, bold=bold
            )
        else:
            t_w, t_h = 0, 0
        node["width"] = max(base_w, t_w)
        node["height"] = max(base_h, t_h)

def resolve_overlaps(elements: list, margin: float = 15.0, max_iterations: int = 100):
    """Perform overlap resolution using iterative AABB relaxation with order-preserving

    separation vectors along the axis of minimum penetration.
    """
    for iteration in range(max_iterations):
        moved = False
        for i in range(len(elements)):
            for j in range(i + 1, len(elements)):
                el_a = elements[i]
                el_b = elements[j]
                
                w_A, h_A = el_a["width"], el_a["height"]
                w_B, h_B = el_b["width"], el_b["height"]
                
                cx_A = el_a["x"] + w_A / 2
                cy_A = el_a["y"] + h_A / 2
                cx_B = el_b["x"] + w_B / 2
                cy_B = el_b["y"] + h_B / 2
                
                # Check for overlap
                ox = (w_A + w_B) / 2 + margin - abs(cx_A - cx_B)
                oy = (h_A + h_B) / 2 + margin - abs(cy_A - cy_B)
                
                if ox > 0 and oy > 0:
                    fixed_a = el_a.get("fixed", False) or el_a.get("style", {}).get("fixed", False)
                    fixed_b = el_b.get("fixed", False) or el_b.get("style", {}).get("fixed", False)
                    
                    if fixed_a and fixed_b:
                        continue
                        
                    moved = True
                    
                    # Resolve along the axis of minimum penetration
                    if ox < oy:
                        direction = 1 if cx_B >= cx_A else -1
                        if cx_B == cx_A:
                            direction = 1 if el_a["id"] < el_b["id"] else -1
                            
                        if fixed_a:
                            el_b["x"] += ox * direction
                        elif fixed_b:
                            el_a["x"] -= ox * direction
                        else:
                            el_a["x"] -= (ox / 2.0) * direction
                            el_b["x"] += (ox / 2.0) * direction
                    else:
                        direction = 1 if cy_B >= cy_A else -1
                        if cy_B == cy_A:
                            direction = 1 if el_a["id"] < el_b["id"] else -1
                            
                        if fixed_a:
                            el_b["y"] += oy * direction
                        elif fixed_b:
                            el_a["y"] -= oy * direction
                        else:
                            el_a["y"] -= (oy / 2.0) * direction
                            el_b["y"] += (oy / 2.0) * direction
        if not moved:
            break

def resolve_diagram_layout(spec: dict) -> dict:
    """Run hierarchical layout overlap resolution on the specification."""
    nodes = spec.get("nodes", [])
    if not nodes:
        return spec
        
    dummy_img = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    draw = ImageDraw.Draw(dummy_img)
    
    # 1. Compute dynamic bounding boxes for all non-panel elements
    for node in nodes:
        compute_node_bounds(node, draw)
        
    nodes_map = {n["id"]: n for n in nodes}
    panels = [n for n in nodes if n["type"] == "panel"]
    panel_ids = {p["id"] for p in panels}
    
    # Store original overall top-left to preserve/restore global layout alignment
    original_min_x = min(node["x"] for node in nodes)
    original_min_y = min(node["y"] for node in nodes)
    
    # 2. Establish hierarchy (group children by parent panel)
    panel_children = {p["id"]: [] for p in panels}
    for node in nodes:
        if node["type"] == "panel":
            continue
        parent_id = node.get("parent")
        if parent_id and parent_id in panel_ids:
            panel_children[parent_id].append(node["id"])
            continue
            
        # Legacy/prefix inference fallback
        nid = node["id"]
        inferred_parent = None
        if nid.startswith("input_"):
            inferred_parent = "input_panel"
        elif nid.startswith("core_card_") or nid in ("decision", "output"):
            inferred_parent = "core_panel"
        elif nid.startswith("left_card_"):
            inferred_parent = "left_panel"
        elif nid.startswith("center_card_") or nid == "center_footer":
            inferred_parent = "center_panel"
        elif nid.startswith("right_card_"):
            inferred_parent = "right_panel"
            
        if inferred_parent and inferred_parent in panel_ids:
            panel_children[inferred_parent].append(nid)
            node["parent"] = inferred_parent
            continue
            
        # Spatial containment fallback
        cx = node["x"] + node["width"] / 2
        cy = node["y"] + node["height"] / 2
        containing_panels = []
        for p in panels:
            px1, py1 = p["x"], p["y"]
            px2, py2 = p["x"] + p["width"], p["y"] + p["height"]
            if px1 <= cx <= px2 and py1 <= cy <= py2:
                containing_panels.append(p)
        if containing_panels:
            containing_panels.sort(key=lambda p: p["width"] * p["height"])
            best_p = containing_panels[0]["id"]
            panel_children[best_p].append(nid)
            node["parent"] = best_p
            
    # Load global layout configuration overrides
    layout_cfg = spec.get("layout", {})
    global_node_margin = layout_cfg.get("node_margin", 15)
    global_panel_margin = layout_cfg.get("panel_margin", 30)
    global_panel_padding = layout_cfg.get("panel_padding", {})
    
    # 3. Local Pass: Resolve sibling card/node overlaps inside panels
    for panel_id, child_ids in panel_children.items():
        if not child_ids:
            continue
        children = [nodes_map[cid] for cid in child_ids if cid in nodes_map]
        resolve_overlaps(children, margin=global_node_margin, max_iterations=100)
        
    # 4. Resize Panels to envelope all their resolved child nodes plus padding
    for panel in panels:
        pid = panel["id"]
        child_ids = panel_children.get(pid, [])
        if not child_ids:
            continue
        child_nodes = [nodes_map[cid] for cid in child_ids if cid in nodes_map]
        
        # Determine padding
        padding_left = global_panel_padding.get("left", 20)
        padding_right = global_panel_padding.get("right", 20)
        padding_top = global_panel_padding.get("top", 60)
        padding_bottom = global_panel_padding.get("bottom", 20)
        
        panel_style = panel.get("style", {})
        p_pad = panel_style.get("padding") or panel.get("padding")
        if isinstance(p_pad, dict):
            padding_left = p_pad.get("left", padding_left)
            padding_right = p_pad.get("right", padding_right)
            padding_top = p_pad.get("top", padding_top)
            padding_bottom = p_pad.get("bottom", padding_bottom)
        elif isinstance(p_pad, (int, float)):
            padding_left = padding_right = padding_top = padding_bottom = p_pad
            
        x1 = min(c["x"] for c in child_nodes) - padding_left
        y1 = min(c["y"] for c in child_nodes) - padding_top
        x2 = max(c["x"] + c["width"] for c in child_nodes) + padding_right
        y2 = max(c["y"] + c["height"] for c in child_nodes) + padding_bottom
        
        panel["x"] = x1
        panel["y"] = y1
        panel["width"] = x2 - x1
        panel["height"] = y2 - y1
        
    # 5. Global Pass: Resolve overlaps between top-level panels and independent nodes
    top_level = [n for n in nodes if n["type"] == "panel" or not n.get("parent")]
    original_top_level_pos = {n["id"]: (n["x"], n["y"]) for n in top_level}
    
    resolve_overlaps(top_level, margin=global_panel_margin, max_iterations=100)
    
    # Translate nested children of moved panels accordingly
    for item in top_level:
        if item["type"] == "panel":
            orig_x, orig_y = original_top_level_pos[item["id"]]
            dx = item["x"] - orig_x
            dy = item["y"] - orig_y
            if dx != 0 or dy != 0:
                for child_id in panel_children.get(item["id"], []):
                    child_node = nodes_map[child_id]
                    child_node["x"] += dx
                    child_node["y"] += dy
                    
    # 6. Global Alignment adjustment: Restore original minimum top-left corner
    current_min_x = min(node["x"] for node in nodes)
    current_min_y = min(node["y"] for node in nodes)
    shift_dx = original_min_x - current_min_x
    shift_dy = original_min_y - current_min_y
    if shift_dx != 0 or shift_dy != 0:
        for node in nodes:
            node["x"] += shift_dx
            node["y"] += shift_dy
            
    return spec
