# Project: FlowDraft Layout & Connection Enhancements

## Architecture
- **render_dynamic_diagram.py**: CLI entry point. Parses the JSON spec, invokes the layout engine, triggers the drawing/SVG/Excalidraw builders, and outputs visual artifacts.
- **flowdraft/layout.py**: Resolves element coordinates dynamically, calculates bounding boxes, handles text wrapping, and avoids overlap.
- **flowdraft/drawing.py** / **flowdraft/excal.py**: Translates layout components and routing paths to SVG/Excalidraw formats.
- **flowdraft/geometry.py**: Geometry helpers for distance, collisions, etc.

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 0 | E2E Test Suite Validation & Infrastructure Setup | Verify existing tests, create TEST_INFRA.md, publish TEST_READY.md | None | DONE |
| 1 | Exploration & Architecture Discovery | Use MCP tools to explore code layout, geometry, text wrapping | None | DONE |
| 2 | Implementation of Layout Engine (R1) & Routing Engine (R2) | Implement force-directed/relaxation overlap resolution and smart line routing | M1 | DONE |
| 3 | Premium Spec Update (R3) | Redesign default-spec.json to highlight dynamic capabilities | M2 | DONE |
| 4 | E2E Verification & Review | Pass 100% of E2E tests (Tiers 1-4) | M0, M2, M3 | DONE |
| 5 | Adversarial Hardening (Tier 5) | Perform white-box analysis, challenge edge cases | M4 | DONE |
| 6 | Forensic Audit & Handoff | Forensic Auditor verification and final handoff | M5 | DONE |

## Code Layout
- `scripts/render_dynamic_diagram.py` - Main CLI
- `scripts/flowdraft/layout.py` - Layout algorithms
- `scripts/flowdraft/drawing.py` - SVG/Excalidraw rendering coordinator
- `scripts/flowdraft/geometry.py` - Geometry helper functions
- `scripts/flowdraft/text.py` - Font and text wrapping utility
- `tests/e2e/test_e2e_suite.py` - E2E Test suite

## Interface Contracts
### `layout.py` ↔ `render_dynamic_diagram.py`
- Layout engine entry point: e.g., `layout_diagram(spec: dict) -> dict` returning updated coordinates and sizes.
- Expected node properties: `x`, `y`, `width`, `height`.
- Parent-child relation: children must stay within panel bounds.
