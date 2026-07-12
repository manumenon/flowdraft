# FlowDraft: Hand-Drawn Animated Architecture Diagrams

Create premium, hand-drawn technical diagrams with editable Excalidraw files, static PNG/SVG previews, and animated GIF workflows.

---

## Output Formats
Every rendering pipeline run produces a complete set of outputs:
* **`.excalidraw`**: Fully editable vector layout compatible with the Excalidraw web app.
* **`.png`**: High-resolution static raster preview with signature, vignette, and canvas details.
* **`.svg`**: Crisp vector static representation.
* **`.gif`**: Smooth, multi-frame loop highlighting step-by-step path flows and module pulses.

---

## Features
* **Modular Engine**: Refactored logic split into dedicated layout, text, geometry, components, and animation sub-modules.
* **Smart Layout & Alignment**: Built-in collision registry, automatic wrapping, and size fitting for both English and CJK text.
* **Multi-Theme Support**: Configurable color palettes including `dark`, `light`, and `white`.
* **Zero Remote Dependencies**: Rendering runs entirely locally with Python and Pillow. No external browser automation or API requests needed.
* **Motion Verification**: Integrated frame-diff statistics analyze pixel adjustments to verify animation quality.

---

## CLI Usage

Run the main command:
```bash
python scripts/render_flowdraft_diagram.py \
  --spec assets/default-spec.json \
  --outdir outputs \
  --basename sample \
  --theme dark \
  --verify \
  --check
```

### Argument Details:
* `--spec` (Required): Path to your input JSON configuration.
* `--outdir` (Required): Directory to write output files.
* `--basename` (Optional): Prefix filename for outputs (defaults to `animated-diagram`).
* `--theme` (Optional): Theme selection (`dark`, `light`, or `white`).
* `--verify` (Optional): Compares pixel changes across frames to log animation stats.
* `--check` (Optional): Validates output parameters (dimensions, unique IDs, font families) and exits nonzero on failure.
* `--rebrand` (Optional): Automatically sanitizes branding strings in the spec.

---

## Project Structure
* [scripts/flowdraft/](scripts/flowdraft): Sub-modules handling math, styling, layout calculation, components, and file output.
* [scripts/render_flowdraft_diagram.py](scripts/render_flowdraft_diagram.py): CLI interface facade.
* [references/spec-format.md](references/spec-format.md): Guide for building custom input JSONs.
* [SKILL.md](SKILL.md): Codex skill instructions.

This project is licensed under the MIT License - see the [LICENSE](./LICENSE) file for details.
