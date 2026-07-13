---
name: flowdraft-animated-architecture-diagram
description: Create premium technical architecture and process diagrams in the FlowDraft animated GIF style, with editable .excalidraw files, static PNG/SVG previews, and genuinely animated GIFs with moving flow highlights. Use this skill whenever the user asks for Excalidraw-like diagrams, DailyDoseOfDS-style black-background sketches, animated architecture/process GIFs, polished flowcharts, visual explanations of articles or system designs, or asks to replicate or improve a reference diagram.
---

# FlowDraft: Technical Animated Architecture Diagram Skill

This skill guides the creation of premium technical diagrams using local Pillow rendering tools.

---

## Deliverables
For every target architecture diagram, produce:
1. **Editable Source**: `.excalidraw` file containing vector elements.
2. **Previews**: High-quality static `.png` and vector `.svg` files.
3. **Animated Target**: A multi-frame loop `.gif` showing path animation flows.

---

## Workflow Steps

### 1. Extract & Group Content
Identify inputs, core stages (typically up to 3 cards), decisions, bottom contextual panels, and target outputs.

### 2. Formulate the Spec JSON
Create or update the layout spec using fields like `signature`, `title`, `inputs`, `core.cards`, `decision`, and bottom panels (`left_panel`, `center_panel`, `right_panel`). Refer to `references/spec-format.md` for text wrapping constraints.

### 3. Execute the Local Renderer
Run the command-line interface helper:
```bash
python scripts/render_flowdraft_diagram.py \
  --spec spec.json \
  --outdir outputs \
  --basename diagram \
  --theme dark \
  --verify \
  --check
```

### 4. Post-Render Validation
* Ensure `--check` outputs `"ok": true`.
* Verify nonzero pixel variation across frames with `--verify`.
* Open the PNG file to manually verify visual clarity and prevent overlaps.

---

## Style Guidelines
* **Themes**: Standard palette defaults to `dark`. Switch to `light` or `white` if requested.
* **Text Copy**: Keep descriptions brief to fit in allocated rectangles.
* ** watermarks**: Include signature text (e.g. `@FlowDraft`) in the top-right corner.
* **Arrow highlights**: Rely on white main static arrows and colorized motion lines in the GIF.

