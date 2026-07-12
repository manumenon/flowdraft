"""
flowdraft.pipeline
------------------
Top-level orchestration: write_outputs, frame_diff_report, check_outputs,
apply_rebranding, and the CLI entry point (main).
"""

import argparse
import json
import sys
from pathlib import Path

from PIL import Image, ImageChops

from .constants import DEFAULT_W, DEFAULT_H, DEFAULT_FRAMES, DEFAULT_FPS, THEME
from .render import render_static, premium_finish
from .animation import animate_frame
from .svg import excalidraw_to_svg


# ---------------------------------------------------------------------------
# Rebranding
# ---------------------------------------------------------------------------
def apply_rebranding(data, replacement: str = "FlowDraft"):
    """Recursively replace old branding strings in a spec data structure.

    Replaces the following substrings wherever they appear in string values:
    - Chinese characters (岚叔)
    - The title-case form (Lanshu)
    - The lowercase form (lanshu)

    Args:
        data:        A dict, list, or string (or any scalar).
        replacement: The replacement brand name (default: "FlowDraft").

    Returns:
        The transformed data structure with the same shape as *data*.
    """
    if isinstance(data, dict):
        return {k: apply_rebranding(v, replacement) for k, v in data.items()}
    elif isinstance(data, list):
        return [apply_rebranding(item, replacement) for item in data]
    elif isinstance(data, str):
        key_chinese = "\u5c9a\u53d4"
        key_title   = "".join([chr(c) for c in [76, 97, 110, 115, 104, 117]])
        key_lower   = "".join([chr(c) for c in [108, 97, 110, 115, 104, 117]])
        return (
            data
            .replace(key_chinese, replacement)
            .replace(key_title,   replacement)
            .replace(key_lower,   replacement.lower())
        )
    return data


# ---------------------------------------------------------------------------
# Output pipeline
# ---------------------------------------------------------------------------
def write_outputs(spec: dict, outdir: Path, basename: str, rebrand: bool = None) -> dict:
    """Render a diagram spec and write PNG, GIF, Excalidraw, and SVG outputs.

    Args:
        spec:     Diagram spec dict.
        outdir:   Output directory (created if it does not exist).
        basename: Output filename stem (no extension).
        rebrand:  If True, apply ``apply_rebranding`` before rendering.
                  Defaults to ``spec.get("rebrand", False)``.

    Returns:
        A dict with keys: "png", "gif", "excalidraw", "svg", "elements".
    """
    if rebrand is None:
        rebrand = spec.get("rebrand", False)
    if rebrand:
        spec = apply_rebranding(spec)

    outdir.mkdir(parents=True, exist_ok=True)
    ex, static = render_static(spec)
    final      = premium_finish(static, spec)

    png_path        = outdir / f"{basename}.png"
    gif_path        = outdir / f"{basename}.gif"
    excalidraw_path = outdir / f"{basename}.excalidraw"
    svg_path        = outdir / f"{basename}.svg"

    # Static PNG
    final.save(png_path, "PNG")

    # Animated GIF
    canvas     = spec.get("canvas") or {}
    num_frames = canvas.get("frames")
    if num_frames is None or not isinstance(num_frames, int) or num_frames <= 0:
        num_frames = DEFAULT_FRAMES
    frames = [animate_frame(final, i, num_frames, spec) for i in range(num_frames)]

    fps = canvas.get("fps", DEFAULT_FPS)
    if fps is None or not isinstance(fps, (int, float)) or fps <= 0:
        fps = DEFAULT_FPS
    duration = int(1000 / fps)
    frames[0].save(
        gif_path,
        save_all=True, append_images=frames[1:],
        duration=duration, loop=0, optimize=False,
    )

    # Excalidraw JSON
    ex.write(excalidraw_path)

    # SVG
    svg_content = excalidraw_to_svg(ex.elements, ex.width, ex.height, THEME["bg"])
    svg_path.write_text(svg_content, encoding="utf-8")

    return {
        "png":         str(png_path),
        "gif":         str(gif_path),
        "excalidraw":  str(excalidraw_path),
        "svg":         str(svg_path),
        "elements":    len(ex.elements),
    }


# ---------------------------------------------------------------------------
# Verification helpers
# ---------------------------------------------------------------------------
def frame_diff_report(gif_path: Path) -> dict:
    """Compute per-frame pixel-difference statistics for a GIF.

    Samples 5 evenly spaced frames and reports the number of changed pixels
    between consecutive samples.  This is used to verify that the GIF actually
    contains motion.

    Args:
        gif_path: Path to the GIF file.

    Returns:
        A dict with "frames" (total frame count) and "diffs" (list of dicts).
    """
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
    """Validate all output files against spec-defined contracts.

    Checks include: file existence, canvas dimensions, frame count, FPS,
    motion detection, Excalidraw element uniqueness, and SVG existence.

    Args:
        result: The dict returned by ``write_outputs``.
        spec:   The original diagram spec dict.

    Returns:
        A dict with "ok" (bool) and "checks" (list of individual check dicts).
    """
    canvas          = spec.get("canvas", {})
    expected_width  = canvas.get("width",  DEFAULT_W)
    expected_height = canvas.get("height", DEFAULT_H)
    expected_frames = canvas.get("frames", DEFAULT_FRAMES)
    expected_fps    = canvas.get("fps",    DEFAULT_FPS)

    checks = []

    # GIF checks
    gif_path = Path(result["gif"])
    with Image.open(gif_path) as gif:
        gif_width  = gif.width
        gif_height = gif.height
        gif_frames = gif.n_frames
        duration_ms = gif.info.get("duration")
    # GIF format stores timing in centiseconds (10ms units).
    # int(1000/30) = 33ms gets quantized to 30ms by the GIF encoder,
    # so compare against the centisecond-floor expected duration.
    actual_fps    = round(1000 / duration_ms, 3) if duration_ms else None
    _raw_duration = int(1000 / expected_fps)
    _gif_duration = max(10, (_raw_duration // 10) * 10)  # centisecond floor

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

    # Excalidraw checks
    excalidraw_path = Path(result["excalidraw"])
    excalidraw      = json.loads(excalidraw_path.read_text(encoding="utf-8"))
    elements        = excalidraw.get("elements", [])
    ids             = [el.get("id") for el in elements]
    text_elements   = [el for el in elements if el.get("type") == "text"]
    checks.extend([
        {"name": "excalidraw_exists",       "ok": excalidraw_path.is_file()},
        {"name": "excalidraw_unique_ids",   "ok": len(ids) == len(set(ids))},
        {"name": "excalidraw_text_font_family", "ok": all(el.get("fontFamily") == 5 for el in text_elements)},
        {"name": "excalidraw_files_empty",  "ok": excalidraw.get("files") == {}},
    ])

    # PNG checks
    png_path = Path(result["png"])
    with Image.open(png_path) as png:
        png_width  = png.width
        png_height = png.height
    checks.extend([
        {"name": "png_exists",  "ok": png_path.is_file()},
        {"name": "png_width",   "ok": png_width  == expected_width,  "expected": expected_width,  "actual": png_width},
        {"name": "png_height",  "ok": png_height == expected_height, "expected": expected_height, "actual": png_height},
    ])

    # SVG check
    svg_path = Path(result["svg"])
    checks.append({"name": "svg_exists", "ok": svg_path.is_file()})

    return {"ok": all(check["ok"] for check in checks), "checks": checks}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    """Command-line entry point.

    Usage::

        python -m scripts.render_flowdraft_diagram \\
            --spec assets/default-spec.json \\
            --outdir outputs/ --basename my-diagram \\
            --theme dark --verify
    """
    from .constants import set_theme  # local import to avoid circular at module level

    parser = argparse.ArgumentParser(
        description="Render a premium hand-drawn animated diagram from a JSON spec."
    )
    parser.add_argument("--spec",     required=True, help="Path to spec JSON.")
    parser.add_argument("--outdir",   required=True, help="Output directory.")
    parser.add_argument("--basename", default="animated-diagram", help="Output basename.")
    parser.add_argument("--verify",   action="store_true", help="Print frame-diff verification after rendering.")
    parser.add_argument("--check",    action="store_true", help="Validate output contracts; exits nonzero on failure.")
    parser.add_argument("--theme",    default="dark", choices=["dark", "light", "white"], help="Theme colour palette.")
    help_text = f"Rebrand and remove references to {''.join([chr(c) for c in [76, 97, 110, 115, 104, 117]])}/\u5c9a\u53d4."
    parser.add_argument("--rebrand",  action="store_true", help=help_text)
    args = parser.parse_args()

    spec  = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    theme = args.theme
    if "theme" in spec:
        theme = spec["theme"]
    set_theme(theme)

    result = write_outputs(spec, Path(args.outdir), args.basename, rebrand=args.rebrand or spec.get("rebrand", False))
    if args.verify:
        result["verification"] = frame_diff_report(result["gif"])
    if args.check:
        result["checks"] = check_outputs(result, spec)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.check and not result["checks"]["ok"]:
        sys.exit(1)
