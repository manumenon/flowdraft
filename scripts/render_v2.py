#!/usr/bin/env python3
"""
render_v2.py — Main orchestrator/CLI for FlowDraft v2 universal diagram rendering engine.
"""

import argparse
import json
import math
import os
import sys
import random
from pathlib import Path
from PIL import Image, ImageDraw, ImageChops, ImageFilter

# Add project root to sys.path
_project_root = str(Path(__file__).resolve().parents[1])
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# Import FlowDraft v2 modules
from scripts.flowdraft.schema import validate_spec
from scripts.flowdraft.compiler import compile_spec
from scripts.flowdraft.layout_engine import layout
from scripts.flowdraft.renderer import render_all, get_port_coords

# Import shared modules
from scripts.flowdraft.constants import (
    DEFAULT_W, DEFAULT_H, DEFAULT_FRAMES, DEFAULT_FPS, SCALE, THEME, set_theme
)
import scripts.flowdraft.constants as fc
from scripts.flowdraft.color import hex_rgba
from scripts.flowdraft.fonts import load_font, text_size
from scripts.flowdraft.text import draw_text
from scripts.flowdraft.drawing import (
    draw_rect, draw_ellipse, draw_line, draw_diamond, draw_signature
)
from scripts.flowdraft.excal import Excal
from scripts.flowdraft.svg import excalidraw_to_svg
from scripts.flowdraft.animation import animate_frame

# Import utility functions from old runner to prevent replication
from scripts.render_dynamic_diagram import (
    apply_rebranding, draw_brand, premium_finish, check_outputs
)


def main():
    parser = argparse.ArgumentParser(description="FlowDraft v2 Diagram Rendering CLI.")
    parser.add_argument("--spec", required=True, help="Spec JSON path.")
    parser.add_argument("--outdir", required=True, help="Output directory.")
    parser.add_argument("--basename", default="sample_v2", help="Output basename.")
    parser.add_argument("--check", action="store_true", help="Validate output contracts.")
    parser.add_argument("--theme", default=None, help="Color theme (dark|light|white).")
    parser.add_argument("--rebrand", action="store_true", help="Rebrand strings (Lanshu -> FlowDraft).")
    args = parser.parse_args()

    # Load spec
    spec_path = Path(args.spec)
    try:
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
    except Exception as e:
        sys.stderr.write(f"Validation Error: Failed to parse JSON spec: {e}\n")
        sys.exit(1)

    # Rebrand if requested
    if args.rebrand:
        spec = apply_rebranding(spec, "FlowDraft")

    # 1. Validate spec using v2 schema
    try:
        validated = validate_spec(spec)
    except Exception as e:
        sys.stderr.write(f"Validation Error in schema: {e}\n")
        sys.exit(1)

    # Set theme
    theme_name = args.theme or validated.get("theme", "dark")
    set_theme(theme_name)

    # Set global hands setting
    fc.HAND = validated.get("hand", True)

    # 2. Compile spec to flat IR
    ir = compile_spec(validated)

    # 3. Layout engine: position nodes and fit to canvas
    canvas_meta = validated.get("canvas", {})
    canvas_w = canvas_meta.get("width", 1920)
    canvas_h = canvas_meta.get("height", 1440)
    ir = layout(ir, canvas_w, canvas_h)

    # Reset scaling factor to 1.0 since layout_engine already fitted everything to canvas
    fc.SCALE_X = 1.0
    fc.SCALE_Y = 1.0

    # Initialize Excal and PIL Image
    ex_doc = Excal(canvas_w, canvas_h)
    
    physical_w = int(canvas_w * SCALE)
    physical_h = int(canvas_h * SCALE)
    img = Image.new("RGBA", (physical_w, physical_h), hex_rgba(THEME["bg"]))
    draw = ImageDraw.Draw(img)

    # 4. Draw Title Block if present
    title_spec = validated.get("title") or {}
    highlight_text = title_spec.get("highlight", "")
    prefix_text    = title_spec.get("prefix", "")
    subtitle_text  = title_spec.get("subtitle", "")
    
    hl_rect_x = 600
    hl_rect_w = 300
    hl_rect_y = 27
    hl_rect_h = 72

    if title_spec:
        draw_line(ex_doc, draw, [(29, 31), (29, 78)], THEME["purple"], 11, scaled=False)
        if prefix_text:
            draw_text(ex_doc, draw, prefix_text, 45, 14, 535, 66, 47, THEME["white"], "left", hand=fc.HAND, bold=True, scaled=False)
        if highlight_text:
            _hl_font = load_font(44, hand=fc.HAND, bold=True)
            _hl_tw, _ = text_size(draw, highlight_text, _hl_font)
            _hl_tw    = max(int(_hl_tw / SCALE), 200)
            _hl_pad_x = 22
            
            # Position highlight box dynamically after prefix if prefix exists
            if prefix_text:
                _pref_font = load_font(47, hand=fc.HAND, bold=True)
                _pref_tw, _ = text_size(draw, prefix_text, _pref_font)
                _pref_tw_scaled = _pref_tw / SCALE
                hl_rect_x = max(600, int(45 + _pref_tw_scaled + 20))
            else:
                hl_rect_x = 45

            hl_rect_w = _hl_tw + _hl_pad_x * 2
            draw_rect(ex_doc, draw, hl_rect_x, hl_rect_y, hl_rect_w, hl_rect_h, THEME["highlight"], THEME["highlight"], 2, 16, scaled=False)
            draw_text(ex_doc, draw, highlight_text, hl_rect_x + _hl_pad_x, 19, hl_rect_w - _hl_pad_x * 2, 76, 44, THEME["green"], "center", hand=fc.HAND, bold=True, scaled=False)
        if subtitle_text:
            draw_text(ex_doc, draw, subtitle_text, 104, 90, 420, 25, 15, THEME["muted"], "left", scaled=False)

    # 5. Compute dynamic outer border enclosing all nodes
    xs = [n["x"] for n in ir["nodes"]]
    ys = [n["y"] for n in ir["nodes"]]
    rights = [n["x"] + n["width"] for n in ir["nodes"]]
    bottoms = [n["y"] + n["height"] for n in ir["nodes"]]
    
    min_x = min(xs) if xs else 50
    min_y = min(ys) if ys else 117
    max_x = max(rights) if rights else canvas_w - 50
    max_y = max(bottoms) if bottoms else canvas_h - 50
    
    outer_border_x = max(10, min_x - 30)
    outer_border_y = max(100, min_y - 20)
    outer_border_w = min(canvas_w - 10, max_x + 30) - outer_border_x
    outer_border_h = min(canvas_h - 10, max_y + 30) - outer_border_y

    draw_rect(ex_doc, draw, outer_border_x, outer_border_y, outer_border_w, outer_border_h, THEME["frame"], None, 2, 29, scaled=False)

    # 6. Render nodes, connections, and annotations using v2 renderer
    render_all(ex_doc, draw, ir)

    # 7. Render signature/brand watermark
    signature = validated.get("signature", "@FlowDraft")
    bx = (outer_border_x + outer_border_w) - 255
    by = 143
    if bx < 600:
        bx = canvas_w - 270
    draw_brand(ex_doc, draw, signature, bx, by)

    # 8. Pre-resolve paths and pulse targets for GIF animation and premium finish
    nodes_map = {n["id"]: n for n in ir["nodes"]}
    resolved_paths = []
    total_paths = len(ir["connections"])
    for p, conn in enumerate(ir["connections"]):
        src_id = conn.get("from")
        tgt_id = conn.get("to")
        src_node = nodes_map.get(src_id)
        tgt_node = nodes_map.get(tgt_id)
        if not src_node or not tgt_node:
            continue
            
        from_port = conn.get("fromPort", conn.get("exitPort", "bottom"))
        to_port = conn.get("toPort", conn.get("entryPort", "top"))
        p_start = get_port_coords(src_node, from_port)
        p_end = get_port_coords(tgt_node, to_port)
        
        # Simple L-shaped routing
        if abs(p_start[0] - p_end[0]) > 1 and abs(p_start[1] - p_end[1]) > 1:
            mid_y = (p_start[1] + p_end[1]) / 2
            path_points = [p_start, (p_start[0], mid_y), (p_end[0], mid_y), p_end]
        else:
            path_points = [p_start, p_end]
            
        # Draw animate comets along path in logical pixels
        # animate_frame receives logical coordinate paths!
        resolved_paths.append((path_points, conn.get("color") or THEME["core_stroke"], p / max(1, total_paths)))
        
    validated["_resolved_paths"] = resolved_paths

    pulse_targets = []
    for node in ir["nodes"]:
        if node.get("type") == "panel":
            x1 = node["x"]
            y1 = node["y"]
            x2 = node["x"] + node["width"]
            y2 = node["y"] + node["height"]
            color = node.get("_resolved_style", {}).get("strokeColor") or THEME["core_stroke"]
            pulse_targets.append(((x1, y1, x2, y2), color))
            
    validated["_resolved_pulse_targets"] = pulse_targets

    layout_spec = {
        "highlight_panel": (hl_rect_x, hl_rect_y, hl_rect_x + hl_rect_w, hl_rect_y + hl_rect_h) if highlight_text else None,
        "outer_border": (outer_border_x, outer_border_y, outer_border_x + outer_border_w, outer_border_y + outer_border_h)
    }
    for node in ir["nodes"]:
        if node.get("type") == "panel":
            layout_spec[node["id"]] = (node["x"], node["y"], node["x"] + node["width"], node["y"] + node["height"])
    validated["_resolved_layout"] = layout_spec

    # 9. Post-process static image
    static_img = img.resize((canvas_w, canvas_h), Image.Resampling.LANCZOS).convert("RGB")
    final_img = premium_finish(static_img, validated)

    # 10. Save outputs
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    basename = args.basename

    png_path = outdir / f"{basename}.png"
    gif_path = outdir / f"{basename}.gif"
    excal_path = outdir / f"{basename}.excalidraw"
    svg_path = outdir / f"{basename}.svg"

    # Save PNG
    final_img.save(png_path, "PNG")

    # Save GIF animation
    num_frames = canvas_meta.get("frames", DEFAULT_FRAMES)
    fps = canvas_meta.get("fps", DEFAULT_FPS)
    frames = [animate_frame(final_img, i, num_frames, validated) for i in range(num_frames)]
    duration = int(1000 / fps)
    frames[0].save(
        gif_path,
        save_all=True, append_images=frames[1:],
        duration=duration, loop=0, optimize=False,
    )

    # Save Excalidraw
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

    # 11. Run checks if requested
    if args.check:
        result["checks"] = check_outputs(result, validated)

    # Print JSON result to stdout
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if args.check and not result["checks"]["ok"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
