# Project: FlowDraft Redesign

## Architecture
The new dynamic rendering architecture processes a user-defined JSON spec that contains arbitrary nodes and connections. 

1. **CLI Driver (`scripts/render_dynamic_diagram.py`)**:
   - Parses command-line inputs (`--spec`, `--outdir`, `--basename`, `--verify`, `--check`).
   - Validates spec schema (dimensions, canvas themes, list of nodes, list of connections).
2. **Layout & Coordinate Engine**:
   - Uses custom coordinates defined on nodes directly.
   - Automatically calculates connector path coordinates (routing arrows between node boundaries or centers).
3. **Drawing Primitives**:
   - Interacts with `flowdraft.drawing` to draw cards, panels, inputs, and diamonds.
   - Generates Excalidraw JSON and rasterizes to PIL.
4. **Animation Engine**:
   - Translates computed connection paths into glow dot animations over configurable frames.
   - Saves final looping GIF.
5. **Legacies**:
   - All rigid rendering components (such as fixed positions in `scripts/flowdraft/render.py`, old spec format) will be removed.

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | M1. Exploration | Explore codebase, mapping legacy files and defining target spec design. | None | DONE (explorer_m1: 5d5c3040-0223-4db4-90a4-b6d77586b290) |
| 2 | M2. E2E Testing Suite | Create independent E2E test suite in `tests/e2e/` with 4-tier cases, publishing `TEST_READY.md`. | M1 | DONE (e2e_testing_orch: b742cd2b-568e-4ae3-b0d8-42e15de7e4d2) |
| 3 | M3. Implementation | Build `scripts/render_dynamic_diagram.py`, implementing coordinate handling, path routing, and animations. | M2 | DONE (implementation_orch: d8ab05a5-e72e-4d94-951c-57104b5f895b) |
| 4 | M4. Verification & Clean-up | Pass all tests, run checkers/verifiers, remove legacy code files and tests. | M3 | DONE (worker_cleanup: e7496dff-4aea-4e91-8fce-ab046f0f0e07) |

## Code Layout
- `scripts/render_dynamic_diagram.py`: New dynamic renderer entry point.
- `scripts/flowdraft/`: Core drawing, text, SVG, excal components (cleaned of legacy layout logic).
- `tests/e2e/`: E2E test suite for the dynamic renderer.
- `tests/`: Unit tests and other verification suites.

## Interface Contracts
### CLI Input Specification
- CLI options:
  - `--spec`: JSON spec file path (required)
  - `--outdir`: output directory path (required)
  - `--basename`: output basename without extension (default: `animated-diagram`)
  - `--verify`: print pixel changes across frames
  - `--check`: validates output parameters and exit code
- JSON Schema:
  - `canvas`: `{"width": int, "height": int, "frames": int, "fps": int}`
  - `theme`: `"dark" | "light" | "white"`
  - `signature`: string
  - `nodes`: list of `{"id": str, "x": float, "y": float, "width": float, "height": float, "type": "card"|"panel"|"input"|"diamond", "title": str, "body": str, "icon": str, "color": str}`
  - `connections`: list of paths e.g., `["node_a", "node_b", "node_c"]`
