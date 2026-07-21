# FlowDraft Layout & Motion Rendering Engine Specification

The core rendering engine resides in `scripts/flowdraft/` and forms the foundation of FlowDraft's deterministic diagram compiler, Excalidraw exporter, and animated GIF/MP4 renderer.

---

## 1. Engine Module Overview

| Module | Purpose & Primary Responsibilities |
| :--- | :--- |
| `schema.py` | Validates, normalises, and flattens V2 JSON diagram specs into internal data representations. Raises `SpecError` on violations. |
| `layout_engine.py` | Art-directed layout engine calculating exact X/Y positions for cards, decision diamonds, input source bars, and output panels. |
| `elk_layout.py` | Python bridge interfacing with ELKjs layout rules for hierarchical DAG node placement. |
| `graphviz_router.py` | Calculates orthogonal and curved spline routing paths for connections without overlapping cards. |
| `compiler.py` | Translates node/edge geometries into rendered visual shapes, shadows, gradients, and SVGs. |
| `renderer.py` | Master orchestrator producing static PNG previews, animated GIFs, and Excalidraw JSON bundles. |
| `excal.py` | Serializer producing `.excalidraw` schema-compliant JSON documents with unique IDs and Excalidraw font mappings (`fontFamily: 5`). |
| `animation.py` | Handles frame-by-frame GIF synthesis and frame-diff motion verification. |
| `text.py` / `fonts.py` | Text wrapping, dynamic font auto-scaling, line breaking for English and CJK text, and font metric measuring. |
| `drawing.py` / `svg.py` | Core canvas drawing primitives, SVG path generation, and icon vector paths. |

---

## 2. Diagram Spec V2 Reference Format

FlowDraft specs are structured JSON files containing title configurations, canvas dimensions, element lists, and connections.

```json
{
  "version": "2.0",
  "theme": "dark",
  "title": {
    "prefix": "Distributed",
    "highlight": "Dataflow System"
  },
  "signature": "@FlowDraft",
  "canvas": {
    "width": 1920,
    "height": 1440,
    "fps": 30,
    "duration": 2.0
  },
  "elements": [
    {
      "id": "ingest_card",
      "type": "card",
      "title": "Ingestion Gateway",
      "body": "Receives streaming event payload",
      "icon": "scan"
    },
    {
      "id": "db_node",
      "type": "card",
      "title": "State Store",
      "body": "Persists transactional state",
      "icon": "db"
    }
  ],
  "connections": [
    {
      "from": "ingest_card",
      "to": "db_node",
      "label": "Sync Writes",
      "style": "solid"
    }
  ]
}
```

### Supported Element Types
- `card`: Standard process container with title, body text, and optional icon.
- `diamond`: Decision node.
- `panel`: Container grouping sub-elements.
- `input`: Compact input source card.
- `label`: Floating text label.
- `group`: Logical cluster boundary.
- `cylinder`: Database or storage representation.
- `cloud`: Cloud or external service representation.

### Icon Library
Built-in vector icons: `folder`, `file`, `scan`, `shield`, `db`, `hash`, `package`.

### Visual Themes
- `dark` (Default): Sleek dark background with vibrant glowing highlights.
- `light`: Soft grey background with crisp slate borders.
- `white`: Pure white background suitable for print publications.

---

## 3. Dynamic Text-Fitting Algorithms

To prevent visual collisions in compact architecture cards, `text.py` applies automated multi-stage text wrapping and font-fitting:

1. **Explicit Line Break Preservation**: Manual `\n` characters in spec strings are strictly respected.
2. **Space & Character Wrapping**: English text wraps at word boundaries; CJK text wraps at character boundaries.
3. **Emergency Font Scaling**: If a line exceeds container bounds at default font size, font size is dynamically downscaled in steps until the copy fits without clipping.
4. **Copy Recommendations**: Core card body copy should remain under 2 lines, max 22 characters per line, for optimal visual hierarchy.

---

## 4. Command-Line Tools & Usage

FlowDraft provides CLI rendering scripts in `scripts/`:

### `scripts/render_v2.py`
The primary rendering CLI.

```bash
python scripts/render_v2.py \
  --spec assets/default-spec.json \
  --outdir outputs/my_diagram \
  --basename pipeline_flow \
  --theme dark \
  --check
```

### `scripts/render_flowdraft_diagram.py`
Compatibility wrapper with contract verification flags (`--verify` or `--check`).

```bash
python scripts/render_flowdraft_diagram.py \
  --spec assets/default-spec.json \
  --outdir outputs/verified_diagram \
  --basename architecture \
  --verify
```

### Output Contracts & Verification
When executed with `--verify` or `--check`, the CLI validates the following strict output contracts:
- **PNG Preview**: Non-zero file size, correct width/height dimensions.
- **GIF Animation**: Exact requested frame count and FPS, non-zero frame-diff confirming genuine visual motion.
- **Excalidraw JSON**: Parsable Excalidraw format, unique element IDs, `fontFamily: 5` applied, and no missing assets.
