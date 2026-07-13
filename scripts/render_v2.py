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
    if strip_h > 0:
        strip_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        strip_draw = ImageDraw.Draw(strip_layer)
        for row in range(strip_h):
            t    = row / max(strip_h - 1, 1)
            a    = int(35 * (1.0 - t)) if not is_light else int(15 * (1.0 - t))
            tint = (200, 200, 200, a) if is_light else (0, 0, 0, a)
            strip_draw.line([(0, height - strip_h + row), (width, height - strip_h + row)], fill=tint)
        img.alpha_composite(strip_layer)

    grain = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    gd    = ImageDraw.Draw(grain)
    rng   = random.Random(2069769416930414980)
    for _ in range(5500):
        gx   = rng.randrange(width)
        gy   = rng.randrange(height)
        tone = rng.randrange(80, 240)
        gd.point((gx, gy), fill=(tone, tone, tone, rng.randrange(5, 18)))
    img.alpha_composite(grain)

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


def run_pipeline(
    spec_path: str,
    outdir: str,
    basename: str = "sample_v2",
    run_checks: bool = False,
    theme_name: str = None,
    rebrand_name: str = None
) -> dict:
    """Executes the universal FlowDraft v2 rendering pipeline."""
    # Load spec
    spec_file = Path(spec_path)
    spec = json.loads(spec_file.read_text(encoding="utf-8"))

    # Rebrand if requested
    if rebrand_name:
        spec = apply_rebranding(spec, rebrand_name)

    # 1. Validate spec using v2 schema
    validated = validate_spec(spec)

    # Set theme
    active_theme = theme_name or validated.get("theme", "dark")
    set_theme(active_theme)

    # Set global hands setting
    fc.HAND = validated.get("hand", True)

    # 2. Compile spec to flat IR
    ir = compile_spec(validated)

    # 3. Layout engine: position nodes and fit to canvas
    canvas_meta = validated.get("canvas", {})
    canvas_w = canvas_meta.get("width", 1920)
    canvas_h = canvas_meta.get("height", 1440)
    ir = layout(ir, canvas_w, canvas_h)
    canvas_w = ir.get("canvas", {}).get("width", canvas_w)
    canvas_h = ir.get("canvas", {}).get("height", canvas_h)

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

    # 5. Extract layout decorations dynamically for layout_spec
    outer_border = None
    highlight_panel = None
    for node in ir["nodes"]:
        if node["id"] == "decor_outer_border":
            outer_border = (node["x"], node["y"], node["x"] + node["width"], node["y"] + node["height"])
        elif node["id"] == "decor_title_highlight":
            highlight_panel = (node["x"], node["y"], node["x"] + node["width"], node["y"] + node["height"])

    # 6. Render nodes, connections, annotations, and injected page layout decorations
    render_all(ex_doc, draw, ir)

    # 8. Pre-resolve paths and pulse targets for GIF animation and premium finish
    resolved_paths = []
    total_paths = len(ir["connections"])
    for p, conn in enumerate(ir["connections"]):
        path_points = [tuple(pts) for pts in conn.get("points", [])]
        if path_points:
            resolved_paths.append((path_points, conn.get("color") or THEME["core_stroke"], p / max(1, total_paths)))
        
    validated["_resolved_paths"] = resolved_paths

    pulse_targets = []
    for node in ir["nodes"]:
        if node.get("type") == "panel" and not node["id"].startswith("decor_"):
            x1 = node["x"]
            y1 = node["y"]
            x2 = node["x"] + node["width"]
            y2 = node["y"] + node["height"]
            color = node.get("_resolved_style", {}).get("strokeColor") or THEME["core_stroke"]
            pulse_targets.append(((x1, y1, x2, y2), color))
            
    validated["_resolved_pulse_targets"] = pulse_targets

    layout_spec = {
        "highlight_panel": highlight_panel,
        "outer_border": outer_border
    }
    for node in ir["nodes"]:
        if node.get("type") == "panel" and not node["id"].startswith("decor_"):
            layout_spec[node["id"]] = (node["x"], node["y"], node["x"] + node["width"], node["y"] + node["height"])
    validated["_resolved_layout"] = layout_spec


    # 9. Post-process static image
    static_img = img.resize((canvas_w, canvas_h), Image.Resampling.LANCZOS).convert("RGB")
    final_img = premium_finish(static_img, validated)

    # 10. Save outputs
    output_dir = Path(outdir)
    output_dir.mkdir(parents=True, exist_ok=True)

    png_path = output_dir / f"{basename}.png"
    gif_path = output_dir / f"{basename}.gif"
    excal_path = output_dir / f"{basename}.excalidraw"
    svg_path = output_dir / f"{basename}.svg"

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
    if run_checks:
        result["checks"] = check_outputs(result, validated)

    return result


def main():
    parser = argparse.ArgumentParser(description="FlowDraft v2 Diagram Rendering CLI.")
    parser.add_argument("--spec", required=True, help="Spec JSON path.")
    parser.add_argument("--outdir", required=True, help="Output directory.")
    parser.add_argument("--basename", default="sample_v2", help="Output basename.")
    parser.add_argument("--check", action="store_true", help="Validate output contracts.")
    parser.add_argument("--theme", default=None, help="Color theme (dark|light|white).")
    parser.add_argument("--rebrand", action="store_true", help="Rebrand strings (Lanshu -> FlowDraft).")
    args = parser.parse_args()

    rebrand_name = "FlowDraft" if args.rebrand else None
    
    try:
        result = run_pipeline(
            spec_path=args.spec,
            outdir=args.outdir,
            basename=args.basename,
            run_checks=args.check,
            theme_name=args.theme,
            rebrand_name=rebrand_name
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        
        if args.check and not result.get("checks", {}).get("ok", True):
            sys.exit(1)
            
    except Exception as e:
        sys.stderr.write(f"Pipeline Execution Error: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
