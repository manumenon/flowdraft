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
    fitted_text, fitted_size, fitted_font = fit_text(
        draw, str(text), default_w, default_h, start_size,
        min_size=min_size, hand=hand, bold=bold, spacing=spacing, wrap=wrap,
        allow_grow=True,
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
        is_center_card = "center_card" in node.get("id", "")
        is_center_footer = node.get("id", "") == "center_footer"
        is_output = node.get("id", "") == "output"
        is_core = "core_card" in node.get("id", "")
        has_icon = bool(node.get("icon"))
        
        if is_center_card:
            padding_left = 10
            padding_right = 10
            padding_top = 11
            padding_bottom = 10
            icon_x = 14
            icon_y = 13
            title_x = 52 if has_icon else 10
            title_w_lim = base_w - title_x - padding_right
            title_h_lim = 30
            body_x = 10
            body_w_lim = base_w - body_x - padding_right
            body_h_lim = base_h - 45
            title_sz = 18
            title_min_size = 12
            body_sz = 12
            body_min_size = 9
            content_gap = 1
            bold_title = True
            bold_body = False
            hand_title = style["hand"]
            hand_body = style["hand"]
        elif is_center_footer:
            padding_left = 12
            padding_right = 12
            padding_top = 11
            padding_bottom = 11
            has_icon = False
            icon_x = 0
            icon_y = 0
            title_x = 12
            title_w_lim = base_w - title_x - padding_right
            title_h_lim = base_h - 22
            body_x = 0
            body_w_lim = 0
            body_h_lim = 0
            title_sz = 14
            title_min_size = 11
            body_sz = 0
            body_min_size = 0
            content_gap = 0
            bold_title = True
            bold_body = False
            hand_title = style["hand"]
            hand_body = style["hand"]
        elif is_output:
            padding_left = 10
            padding_right = 10
            padding_top = 11
            padding_bottom = 10
            icon_x = 14
            icon_y = 13
            title_x = 48 if has_icon else 10
            title_w_lim = base_w - title_x - padding_right
            title_h_lim = 30
            body_x = 10
            body_w_lim = base_w - body_x - padding_right
            body_h_lim = base_h - 45
            title_sz = 18
            title_min_size = 12
            body_sz = 12
            body_min_size = 9
            content_gap = 1
            bold_title = True
            bold_body = False
            hand_title = style["hand"]
            hand_body = style["hand"]
        else: # default card
            padding_left = 16
            padding_right = 16
            padding_top = 11
            padding_bottom = 12
            icon_x = 14
            icon_y = 13
            title_x = 100 if has_icon else 100
            body_x = 85 if has_icon else 85
            title_w_lim = base_w - 110
            body_w_lim = base_w - 95
            title_h_lim = 28
            body_h_lim = base_h - 45 - 7
            title_sz = 20 if is_core else 18
            title_min_size = 15 if is_core else 12
            body_sz = 14
            body_min_size = 11
            content_gap = 3
            bold_title = True
            bold_body = False
            hand_title = is_core or style["hand"]
            hand_body = style["hand"]
            
        t_w, t_h = 0, 0
        t_sz = title_sz
        if title:
            fitted_title, fitted_title_sz, fitted_title_font = fit_text(
                draw, str(title), title_w_lim, title_h_lim, title_sz,
                min_size=title_min_size, hand=hand_title, bold=bold_title, wrap=True, allow_grow=True
            )
            tw, th = text_size(draw, fitted_title, fitted_title_font)
            t_w, t_h = tw / SCALE, th / SCALE
            t_sz = fitted_title_sz
            
        b_w, b_h = 0, 0
        b_sz = body_sz
        if body:
            fitted_body, fitted_body_sz, fitted_body_font = fit_text(
                draw, str(body), body_w_lim, body_h_lim, body_sz,
                min_size=body_min_size, hand=hand_body, bold=bold_body, wrap=True, allow_grow=True
            )
            tw, th = text_size(draw, fitted_body, fitted_body_font)
            b_w, b_h = tw / SCALE, th / SCALE
            b_sz = fitted_body_sz
            
        extra_w = max(0, t_w - title_w_lim, b_w - body_w_lim)
        extra_h = max(0, (t_h - title_h_lim) + (b_h - body_h_lim))
        
        node["width"] = base_w + extra_w
        node["height"] = base_h + extra_h
        
        node["layout_offsets"] = {
            "icon": {
                "x": icon_x,
                "y": icon_y,
                "w": 38.4,
                "h": 38.4,
                "draw": has_icon
            },
            "title": {
                "x": title_x,
                "y": padding_top,
                "w": title_w_lim + extra_w,
                "h": t_h if title else 0,
                "size": t_sz,
                "min_size": title_min_size
            }
        }
        if body:
            node["layout_offsets"]["body"] = {
                "x": body_x,
                "y": padding_top + (t_h if title else 0) + content_gap,
                "w": body_w_lim + extra_w,
                "h": b_h,
                "size": b_sz,
                "min_size": body_min_size
            }
            
    elif ntype == "diamond":
        title_w_lim = base_w * 0.5
        body_w_lim = base_w * 0.5
        title_h_lim = base_h * 0.25
        body_h_lim = base_h * 0.45
        
        t_w, t_h = 0, 0
        t_sz = 18
        if title:
            fitted_title, fitted_title_sz, fitted_title_font = fit_text(
                draw, str(title), title_w_lim, title_h_lim, 18,
                min_size=10, hand=style["hand"], bold=True, wrap=True, allow_grow=True
            )
            tw, th = text_size(draw, fitted_title, fitted_title_font)
            t_w, t_h = tw / SCALE, th / SCALE
            t_sz = fitted_title_sz
            
        b_w, b_h = 0, 0
        b_sz = 13
        if body:
            fitted_body, fitted_body_sz, fitted_body_font = fit_text(
                draw, str(body), body_w_lim, body_h_lim, 13,
                min_size=6, hand=style["hand"], bold=style["bold"], wrap=True, allow_grow=True
            )
            tw, th = text_size(draw, fitted_body, fitted_body_font)
            b_w, b_h = tw / SCALE, th / SCALE
            b_sz = fitted_body_sz
            
        extra_w = max(0, t_w - title_w_lim, b_w - body_w_lim)
        extra_h = max(0, (t_h - title_h_lim) + (b_h - body_h_lim))
        
        nw = (base_w * 0.5 + extra_w) / 0.5
        nh = (base_h * 0.5 + extra_h) / 0.5
        node["width"] = nw
        node["height"] = nh
        
        node["layout_offsets"] = {
            "title": {
                "x": nw * 0.25,
                "y": nh * 0.25,
                "w": nw * 0.5,
                "h": t_h if title else 0,
                "size": t_sz,
                "min_size": 10
            }
        }
        if body:
            node["layout_offsets"]["body"] = {
                "x": nw * 0.25,
                "y": nh * 0.25 + (t_h if title else 0) + 3,
                "w": nw * 0.5,
                "h": b_h,
                "size": b_sz,
                "min_size": 10
            }
            
    elif ntype == "input":
        t_w, t_h = 0, 0
        t_sz = 13
        if title:
            fitted_title, fitted_title_sz, fitted_title_font = fit_text(
                draw, str(title), base_w, max(24, base_h - 34), 13,
                min_size=9, hand=style["hand"], bold=False, wrap=True, allow_grow=True
            )
            tw, th = text_size(draw, fitted_title, fitted_title_font)
            t_w, t_h = tw / SCALE, th / SCALE
            t_sz = fitted_title_sz
            
        node["width"] = max(base_w, t_w)
        node["height"] = max(base_h, t_h + 34)
        
        node["layout_offsets"] = {
            "title": {
                "x": 0,
                "y": 34,
                "w": node["width"],
                "h": node["height"] - 34,
                "size": t_sz,
                "min_size": 9
            }
        }
        
    elif ntype == "text":
        size = node.get("size", 14)
        bold = node.get("bold", False)
        hand = node.get("hand", True)
        
        t_w, t_h = 0, 0
        t_sz = size
        if title:
            fitted_title, fitted_title_sz, fitted_title_font = fit_text(
                draw, str(title), base_w, base_h, size,
                min_size=9, hand=hand, bold=bold, wrap=True, allow_grow=True
            )
            tw, th = text_size(draw, fitted_title, fitted_title_font)
            t_w, t_h = tw / SCALE, th / SCALE
            t_sz = fitted_title_sz
            
        node["width"] = max(base_w, t_w)
        node["height"] = max(base_h, t_h)
        
        node["layout_offsets"] = {
            "title": {
                "x": 0,
                "y": 0,
                "w": node["width"],
                "h": node["height"],
                "size": t_sz,
                "min_size": 9
            }
        }

def resolve_overlaps(elements: list, margin: float = 15.0, max_iterations: int = 150, edges: list = None):
    """Perform overlap resolution using Constraint-based Force-Directed Relaxation (CFDR)
    with a fallback Axis-Aligned Bounding Box (AABB) projection phase.
    """
    if not elements:
        return

    # Map ID to elements for force lookup and spring calculations
    nodes_map = {el["id"]: el for el in elements}
    
    # CFDR parameters
    k_attr = 0.05
    k_rep = 0.2
    L_0 = 160.0
    dt = 0.5
    max_displacement = 30.0

    # Ensure elements don't overlap initially by giving them slight random offsets if their coordinates are identical
    for i, el_a in enumerate(elements):
        for j in range(i + 1, len(elements)):
            el_b = elements[j]
            if el_a["x"] == el_b["x"] and el_a["y"] == el_b["y"]:
                fixed_b = el_b.get("fixed", False) or el_b.get("style", {}).get("fixed", False)
                if not fixed_b:
                    el_b["x"] += 5.0
                    el_b["y"] += 5.0

    # 1. CFDR relaxation iterations
    for iteration in range(max_iterations):
        moved = False
        forces = {el["id"]: [0.0, 0.0] for el in elements}

        # 1a. Compute attractive forces along connection edges
        if edges:
            for u_id, v_id in edges:
                if u_id in nodes_map and v_id in nodes_map:
                    el_u = nodes_map[u_id]
                    el_v = nodes_map[v_id]
                    
                    cx_u = el_u["x"] + el_u["width"] / 2
                    cy_u = el_u["y"] + el_u["height"] / 2
                    cx_v = el_v["x"] + el_v["width"] / 2
                    cy_v = el_v["y"] + el_v["height"] / 2
                    
                    dx = cx_v - cx_u
                    dy = cy_v - cy_u
                    dist = math.hypot(dx, dy)
                    if dist > 1e-3:
                        ux = dx / dist
                        uy = dy / dist
                        f_mag = k_attr * (dist - L_0)
                        
                        forces[u_id][0] += f_mag * ux
                        forces[u_id][1] += f_mag * uy
                        forces[v_id][0] -= f_mag * ux
                        forces[v_id][1] -= f_mag * uy

        # 1b. Compute repulsive forces for overlapping node pairs
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
                
                dx = cx_B - cx_A
                dy = cy_B - cy_A
                dist = math.hypot(dx, dy)
                if dist < 1e-3:
                    dx = 1.0 if el_a["id"] < el_b["id"] else -1.0
                    dy = 0.0
                    dist = 1.0
                
                ux = dx / dist
                uy = dy / dist

                ox = (w_A + w_B) / 2 + margin - abs(cx_A - cx_B)
                oy = (h_A + h_B) / 2 + margin - abs(cy_A - cy_B)
                
                if ox > 0 and oy > 0:
                    penetration = min(ox, oy)
                    f_rep_mag = k_rep * (penetration ** 2)
                    
                    fixed_a = el_a.get("fixed", False) or el_a.get("style", {}).get("fixed", False)
                    fixed_b = el_b.get("fixed", False) or el_b.get("style", {}).get("fixed", False)
                    
                    if fixed_a and fixed_b:
                        continue
                    
                    if not fixed_a:
                        forces[el_a["id"]][0] -= f_rep_mag * ux
                        forces[el_a["id"]][1] -= f_rep_mag * uy
                    if not fixed_b:
                        forces[el_b["id"]][0] += f_rep_mag * ux
                        forces[el_b["id"]][1] += f_rep_mag * uy

        # 1c. Update positions
        disp_sum = 0.0
        for el in elements:
            fixed = el.get("fixed", False) or el.get("style", {}).get("fixed", False)
            if fixed:
                continue
                
            fx, fy = forces[el["id"]]
            f_len = math.hypot(fx, fy)
            if f_len > 0:
                dx = fx * dt
                dy = fy * dt
                d_len = math.hypot(dx, dy)
                if d_len > max_displacement:
                    dx = (dx / d_len) * max_displacement
                    dy = (dy / d_len) * max_displacement
                
                el["x"] += dx
                el["y"] += dy
                disp_sum += math.hypot(dx, dy)
                moved = True

        if not moved or disp_sum < 0.1:
            break

    # 2. Hard constraint fallback: AABB Projection to guarantee absolute overlap-free status
    for _ in range(50):
        any_overlap = False
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
                
                ox = (w_A + w_B) / 2 + margin - abs(cx_A - cx_B)
                oy = (h_A + h_B) / 2 + margin - abs(cy_A - cy_B)
                
                if ox > 0 and oy > 0:
                    fixed_a = el_a.get("fixed", False) or el_a.get("style", {}).get("fixed", False)
                    fixed_b = el_b.get("fixed", False) or el_b.get("style", {}).get("fixed", False)
                    
                    if fixed_a and fixed_b:
                        continue
                        
                    any_overlap = True
                    
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
        if not any_overlap:
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
    
    # Store original overall top-left to preserve/restore global layout alignment
    valid_coords_x = [node["x"] for node in nodes if node.get("x") is not None]
    valid_coords_y = [node["y"] for node in nodes if node.get("y") is not None]
    original_min_x = min(valid_coords_x) if valid_coords_x else 39
    original_min_y = min(valid_coords_y) if valid_coords_y else 138
    
    # 2. Establish hierarchy (group children by parent panel)
    parent_map = {}
    for node in nodes:
        nid = node["id"]
        parent_id = node.get("parent")
        if parent_id and parent_id in nodes_map and nodes_map[parent_id]["type"] == "panel":
            parent_map[nid] = parent_id
            continue
            
        # Legacy/prefix inference fallback (only for non-panel nodes)
        if node["type"] != "panel":
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
                
            if inferred_parent and inferred_parent in nodes_map:
                parent_map[nid] = inferred_parent
                node["parent"] = inferred_parent
                continue
                
            # Spatial containment fallback (only for non-panel nodes with coords)
            if node.get("x") is not None and node.get("y") is not None:
                cx = node["x"] + node["width"] / 2
                cy = node["y"] + node["height"] / 2
                containing_panels = []
                for p in panels:
                    if p["id"] == nid:
                        continue
                    px1, py1 = p["x"], p["y"]
                    px2, py2 = p["x"] + p["width"], p["y"] + p["height"]
                    if px1 <= cx <= px2 and py1 <= cy <= py2:
                        containing_panels.append(p)
                if containing_panels:
                    containing_panels.sort(key=lambda p: p["width"] * p["height"])
                    best_p = containing_panels[0]["id"]
                    parent_map[nid] = best_p
                    node["parent"] = best_p

    children_map = {n["id"]: [] for n in nodes if n["type"] == "panel"}
    for nid, pid in parent_map.items():
        if pid in children_map:
            children_map[pid].append(nid)
            
    top_level_ids = [n["id"] for n in nodes if n["id"] not in parent_map]
    
    # Helper functions for layout
    def get_ancestor_in_container(node_id, container_id, parent_map):
        curr = node_id
        while curr is not None:
            parent = parent_map.get(curr)
            if parent == container_id:
                return curr
            curr = parent
        return None

    def get_flow_direction(container_id, spec):
        if container_id is None:
            return spec.get("layout", {}).get("flow_direction") or spec.get("layout", {}).get("direction") or "LR"
        container_node = nodes_map.get(container_id)
        if container_node:
            style = container_node.get("style", {})
            direction = style.get("flow_direction") or style.get("direction") or container_node.get("flow_direction")
            if direction:
                return direction
        if container_id in ("left_panel", "right_panel", "center_panel"):
            return "TB"
        return "LR"

    def layout_container(container_id, spec):
        children = children_map.get(container_id, []) if container_id else top_level_ids
        for child_id in children:
            if nodes_map[child_id]["type"] == "panel":
                layout_container(child_id, spec)
                
        if not children:
            return
            
        layout_cfg = spec.get("layout", {})
        auto_layout = spec.get("auto_layout") or layout_cfg.get("auto_layout") or (layout_cfg.get("strategy") == "auto")
        needs_auto_layout = auto_layout or any(nodes_map[cid].get("x") is None or nodes_map[cid].get("y") is None for cid in children)
        
        child_nodes = [nodes_map[cid] for cid in children]
        
        # Build projected edges among children (always, for CFDR force resolution)
        edges = []
        seen_edges = set()
        for conn_dict in spec.get("connections", []):
            path = conn_dict if isinstance(conn_dict, list) else conn_dict.get("path", [])
            for idx in range(len(path) - 1):
                u, v = path[idx], path[idx + 1]
                u_anc = get_ancestor_in_container(u, container_id, parent_map)
                v_anc = get_ancestor_in_container(v, container_id, parent_map)
                if u_anc and v_anc and u_anc != v_anc:
                    edge = (u_anc, v_anc)
                    if edge not in seen_edges:
                        seen_edges.add(edge)
                        edges.append(edge)

        if needs_auto_layout:
            # Cycle breaking DFS to make it a DAG
            visited = {}
            reversed_edges = set()
            dag_edges = []
            
            def dfs(node):
                visited[node] = 1
                neighbors = [v for u, v in edges if u == node]
                for n in neighbors:
                    if visited.get(n, 0) == 1:
                        reversed_edges.add((node, n))
                        dag_edges.append((n, node))
                    elif visited.get(n, 0) == 0:
                        dag_edges.append((node, n))
                        dfs(n)
                    else:
                        dag_edges.append((node, n))
                visited[node] = 2
                
            for cid in children:
                if visited.get(cid, 0) == 0:
                    dfs(cid)
                    
            # Compute topological ranks
            rank = {}
            for cid in children:
                rank[cid] = None
                
            def compute_rank(node):
                if rank[node] is not None:
                    return rank[node]
                incoming = [u for u, v in dag_edges if v == node]
                if not incoming:
                    rank[node] = 0
                    return 0
                rank[node] = max(compute_rank(u) for u in incoming) + 1
                return rank[node]
                
            for cid in children:
                compute_rank(cid)
                
            # Group children by rank
            from collections import defaultdict
            rank_groups = defaultdict(list)
            for cid in children:
                r = rank[cid]
                rank_groups[r].append(cid)
                
            sorted_ranks = sorted(rank_groups.keys())
            
            # Determine flow direction
            flow_direction = get_flow_direction(container_id, spec)
            
            column_gap = layout_cfg.get("column_gap", 80)
            row_gap = layout_cfg.get("row_gap", 40)
            
            # Determine container padding
            padding_left = 20
            padding_right = 20
            padding_top = 60 if container_id else 20
            padding_bottom = 20
            
            if container_id:
                container_node = nodes_map[container_id]
                p_pad = container_node.get("style", {}).get("padding") or container_node.get("padding")
                if isinstance(p_pad, dict):
                    padding_left = p_pad.get("left", padding_left)
                    padding_right = p_pad.get("right", padding_right)
                    padding_top = p_pad.get("top", padding_top)
                    padding_bottom = p_pad.get("bottom", padding_bottom)
                elif isinstance(p_pad, (int, float)):
                    padding_left = padding_right = padding_top = padding_bottom = p_pad
            
            if flow_direction == "LR":
                max_w_in_rank = {}
                for r in sorted_ranks:
                    max_w_in_rank[r] = max(nodes_map[cid]["width"] for cid in rank_groups[r])
                    
                rank_x = {}
                if sorted_ranks:
                    rank_x[sorted_ranks[0]] = padding_left
                    for i in range(1, len(sorted_ranks)):
                        prev_r = sorted_ranks[i - 1]
                        curr_r = sorted_ranks[i]
                        rank_x[curr_r] = rank_x[prev_r] + max_w_in_rank[prev_r] + column_gap
                        
                for r in sorted_ranks:
                    curr_y = padding_top
                    for cid in rank_groups[r]:
                        node = nodes_map[cid]
                        if (node.get("fixed") or node.get("style", {}).get("fixed")) and node.get("x") is not None and node.get("y") is not None:
                            continue
                        node["x"] = rank_x[r] + (max_w_in_rank[r] - node["width"]) / 2
                        node["y"] = curr_y
                        curr_y += node["height"] + row_gap
            else:
                max_h_in_rank = {}
                for r in sorted_ranks:
                    max_h_in_rank[r] = max(nodes_map[cid]["height"] for cid in rank_groups[r])
                    
                rank_y = {}
                if sorted_ranks:
                    rank_y[sorted_ranks[0]] = padding_top
                    for i in range(1, len(sorted_ranks)):
                        prev_r = sorted_ranks[i - 1]
                        curr_r = sorted_ranks[i]
                        rank_y[curr_r] = rank_y[prev_r] + max_h_in_rank[prev_r] + row_gap
                        
                for r in sorted_ranks:
                    curr_x = padding_left
                    for cid in rank_groups[r]:
                        node = nodes_map[cid]
                        if (node.get("fixed") or node.get("style", {}).get("fixed")) and node.get("x") is not None and node.get("y") is not None:
                            continue
                        node["x"] = curr_x
                        node["y"] = rank_y[r] + (max_h_in_rank[r] - node["height"]) / 2
                        curr_x += node["width"] + column_gap
                        
        global_node_margin = layout_cfg.get("node_margin", 15)
        global_panel_margin = layout_cfg.get("panel_margin", 30)
        margin = global_panel_margin if container_id is None else global_node_margin
        
        resolve_overlaps(child_nodes, margin=margin, max_iterations=150, edges=edges)
        
        if container_id:
            panel_node = nodes_map[container_id]
            padding_left = 20
            padding_right = 20
            padding_top = 60
            padding_bottom = 20
            
            p_pad = panel_node.get("style", {}).get("padding") or panel_node.get("padding")
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
            
            panel_node["width"] = x2 - x1
            panel_node["height"] = y2 - y1
            panel_node["x"] = x1
            panel_node["y"] = y1
            
            dx = -x1
            dy = -y1
            for c in child_nodes:
                c["x"] += dx
                c["y"] += dy

    # 4. Run layout recursively from root
    layout_container(None, spec)
    
    # 5. Top-down propagation of absolute coordinates
    def propagate_coords(node_id, px, py):
        node = nodes_map[node_id]
        node["x_rel"] = node["x"]
        node["y_rel"] = node["y"]
        node["x"] = px + node["x_rel"]
        node["y"] = py + node["y_rel"]
        for cid in children_map.get(node_id, []):
            propagate_coords(cid, node["x"], node["y"])
            
    for top_id in top_level_ids:
        node = nodes_map[top_id]
        node["x_rel"] = node["x"]
        node["y_rel"] = node["y"]
        for cid in children_map.get(top_id, []):
            propagate_coords(cid, node["x"], node["y"])
            
    # Compute panel offsets so that the renderer can draw panel titles dynamically
    for panel in panels:
        if panel["id"] == "left_panel":
            panel["layout_offsets"] = {
                "title": {
                    "x": 19,
                    "y": 17,
                    "w": panel["width"] - 130,
                    "h": 30,
                    "size": 20,
                    "min_size": 12
                }
            }
        else:
            panel["layout_offsets"] = {
                "title": {
                    "x": 15,
                    "y": 15,
                    "w": panel["width"] - 30,
                    "h": 34,
                    "size": 22,
                    "min_size": 12
                }
            }
            
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
