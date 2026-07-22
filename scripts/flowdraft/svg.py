"""
flowdraft.svg
-------------
Converts a list of Excalidraw element dicts to a valid SVG string.

The SVG output is a flat document: each element is translated to its nearest
SVG equivalent (rect → <rect>, ellipse → <ellipse>, line/arrow → <polyline>
or <polygon>, text → <text> with <tspan> lines).

A ``<defs>`` block with a panel drop-shadow filter is included automatically.
"""

import math
import xml.etree.ElementTree as ET

from . import constants as _c  # live attribute access; never bind SCALE_X/Y at import time


def excalidraw_to_svg(elements: list, width: int, height: int, bg_color: str) -> str:
    """Convert Excalidraw element dicts to an SVG string.

    Args:
        elements:  List of Excalidraw element dicts (as produced by ``Excal``).
        width:     Canvas width in logical pixels.
        height:    Canvas height in logical pixels.
        bg_color:  Background colour hex string for the SVG canvas.

    Returns:
        A UTF-8 SVG string.
    """
    svg = ET.Element("svg", {
        "xmlns": "http://www.w3.org/2000/svg",
        "width":   str(width),
        "height":  str(height),
        "viewBox": f"0 0 {width} {height}",
    })

    # --- Drop-shadow filter for panels ---
    defs = ET.SubElement(svg, "defs")
    filt = ET.SubElement(defs, "filter", {
        "id": "panel-shadow",
        "x": "-6%", "y": "-6%", "width": "118%", "height": "118%",
    })
    ET.SubElement(filt, "feDropShadow", {
        "dx": "0", "dy": "3",
        "stdDeviation": "5",
        "flood-color": "#000000",
        "flood-opacity": "0.20",
    })

    # Canvas background
    ET.SubElement(svg, "rect", {"width": "100%", "height": "100%", "fill": bg_color or "#000000"})

    for el in elements:
        if el.get("isDeleted"):
            continue

        el_type = el.get("type")
        x       = el.get("x", 0)
        y       = el.get("y", 0)
        w       = el.get("width", 0)
        h       = el.get("height", 0)
        stroke  = el.get("strokeColor", "#ffffff")
        fill    = el.get("backgroundColor", "transparent")
        if fill == "transparent" or not fill:
            fill = "none"
        stroke_w = el.get("strokeWidth", 2)
        style    = el.get("strokeStyle", "solid")

        stroke_dash = ""
        if style == "dashed":
            stroke_dash = "8,8"
        elif style == "dotted":
            stroke_dash = "2,7"

        extra_attrs = {}
        if stroke_dash:
            extra_attrs["stroke-dasharray"] = stroke_dash
        opacity_val = el.get("_opacity")
        if opacity_val is not None and opacity_val < 1.0:
            extra_attrs["opacity"] = str(opacity_val)

        # --- Rectangle ---
        if el_type == "rectangle":
            radius_val = el.get("_radius")
            rx = str(radius_val) if radius_val is not None else ("10" if el.get("roundness") else "0")
            ET.SubElement(svg, "rect", {
                "x": str(x), "y": str(y),
                "width": str(w), "height": str(h),
                "stroke": stroke, "fill": fill,
                "stroke-width": str(stroke_w),
                "rx": rx, "ry": rx,
                **extra_attrs,
            })

        # --- Ellipse ---
        elif el_type == "ellipse":
            ET.SubElement(svg, "ellipse", {
                "cx": str(x + w / 2), "cy": str(y + h / 2),
                "rx": str(w / 2),     "ry": str(h / 2),
                "stroke": stroke, "fill": fill,
                "stroke-width": str(stroke_w),
                **extra_attrs,
            })

        # --- Diamond ---
        elif el_type == "diamond":
            p1 = f"{x + w/2},{y}"
            p2 = f"{x + w},{y + h/2}"
            p3 = f"{x + w/2},{y + h}"
            p4 = f"{x},{y + h/2}"
            ET.SubElement(svg, "polygon", {
                "points": f"{p1} {p2} {p3} {p4}",
                "stroke": stroke, "fill": fill,
                "stroke-width": str(stroke_w),
                "stroke-linejoin": "round",
                "stroke-linecap": "round",
                **extra_attrs,
            })

        # --- Line / Arrow ---
        elif el_type in ("line", "arrow"):
            pts = el.get("points", [])
            absolute_pts = [(x + px, y + py) for px, py in pts]
            is_closed = (
                len(absolute_pts) >= 3
                and math.dist(absolute_pts[0], absolute_pts[-1]) < 0.1
            )
            points_str = " ".join(f"{px},{py}" for px, py in absolute_pts)
            attrs = {
                "points": points_str,
                "stroke": stroke, "fill": fill,
                "stroke-width": str(stroke_w),
                "stroke-linejoin": "round",
                "stroke-linecap": "round",
                **extra_attrs,
            }
            ET.SubElement(svg, "polygon" if is_closed else "polyline", attrs)

            # Arrow-head polyline (logical canvas coordinates)
            if el_type == "arrow" and len(absolute_pts) >= 2:
                ap1, ap2 = absolute_pts[-2], absolute_pts[-1]
                angle  = math.atan2(ap2[1] - ap1[1], ap2[0] - ap1[0])
                length = 12 + stroke_w
                spread = 0.52
                h1x = ap2[0] - length * math.cos(angle - spread)
                h1y = ap2[1] - length * math.sin(angle - spread)
                h2x = ap2[0] - length * math.cos(angle + spread)
                h2y = ap2[1] - length * math.sin(angle + spread)
                ET.SubElement(svg, "polyline", {
                    "points": f"{h1x},{h1y} {ap2[0]},{ap2[1]} {h2x},{h2y}",
                    "stroke": stroke, "fill": "none",
                    "stroke-width": str(stroke_w),
                    "stroke-linejoin": "round",
                    "stroke-linecap": "round",
                })

            # --- Motion Flow Highlights in SVG Output ---
            if not is_closed and len(absolute_pts) >= 2:
                path_d = "M " + " L ".join(f"{px},{py}" for px, py in absolute_pts)
                glow_color = stroke if stroke and stroke not in ("#000000", "#ffffff", "none", "transparent") else "#00f0ff"

                # 1. Animated stroke-dashoffset flow highlight
                flow_path = ET.SubElement(svg, "path", {
                    "d": path_d,
                    "fill": "none",
                    "stroke": glow_color,
                    "stroke-width": str(max(1.5, stroke_w)),
                    "stroke-dasharray": "8,16",
                    "stroke-linecap": "round",
                    "opacity": "0.85",
                })
                ET.SubElement(flow_path, "animate", {
                    "attributeName": "stroke-dashoffset",
                    "from": "24",
                    "to": "0",
                    "dur": "1.5s",
                    "repeatCount": "indefinite",
                })

                # 2. Animated particle using <animateMotion>
                particle_circle = ET.SubElement(svg, "circle", {
                    "r": "4",
                    "fill": glow_color,
                })
                ET.SubElement(particle_circle, "animateMotion", {
                    "path": path_d,
                    "dur": "3s",
                    "repeatCount": "indefinite",
                })

        # --- Text ---
        elif el_type == "text":
            font_size   = el.get("fontSize", 16)
            text_color  = el.get("strokeColor", "#ffffff")
            align       = el.get("textAlign", "left")
            text_anchor = {"center": "middle", "right": "end"}.get(align, "start")

            if el.get("_hand"):
                font_family = '"Comic Sans MS", "Chalkboard SE", "Noteworthy", "Bradley Hand", cursive'
            elif el.get("_cjk"):
                font_family = '"Microsoft YaHei", "STHeiti", "Hiragino Sans GB", "SimSun", "Noto Sans CJK SC", sans-serif'
            else:
                font_family = '"Helvetica Neue", "Helvetica", "Arial", sans-serif'

            text_attrs = {
                "fill": text_color,
                "font-size": f"{font_size}px",
                "font-family": font_family,
                "text-anchor": text_anchor,
                "dominant-baseline": "hanging",
                **extra_attrs,
            }
            if el.get("_bold"):
                text_attrs["font-weight"] = "bold"

            text_el = ET.SubElement(svg, "text", text_attrs)
            raw_lines   = el.get("text", "").split("\n")
            total_text_h = (len(raw_lines) - 1) * (font_size * 1.25) + font_size
            y_offset    = (h - total_text_h) / 2.0

            for i, line_text in enumerate(raw_lines):
                tx = x
                if align == "center":
                    tx = x + w / 2
                elif align == "right":
                    tx = x + w
                ty = y + y_offset + i * (font_size * 1.25)
                tspan = ET.SubElement(text_el, "tspan", {"x": str(tx), "y": str(ty)})
                tspan.text = line_text

    return ET.tostring(svg, encoding="utf-8").decode("utf-8")
