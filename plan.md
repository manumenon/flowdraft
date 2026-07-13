# Plan: FlowDraft v2 Implementation Plan

## Architecture & Design
- **Entry point**: `scripts/render_v2.py`
- **Compiler**: `scripts/flowdraft/compiler.py` (implement passes, layout_offsets)
- **Schema**: `scripts/flowdraft/schema.py` (DSL schema validation, validation of modes, animation config, out-of-flow flag or absolute coordinate checks)
- **Layout**: `scripts/flowdraft/layout_engine.py` (Pass 4: Hierarchical layout solver, Pass 5: Structural absolutizer)
- **Routing**: `scripts/flowdraft/geometry.py` or new router (Pass 6: Edge Router & Label Injector)
- **Renderer**: `scripts/flowdraft/renderer.py` & `drawing.py` (Pass 7: Paint Engine)

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | Exploration & Diagnostic Validation | Run existing tests in `tests/test_v2.py` via a worker to get baseline behavior. Identify gaps in current codebase. | None | PLANNED |
| 2 | Spec DSL Schema & Parser (Pass 1) | Update schema validation to support `canvas.mode`, temporal configurations, themes, nested node tree, and out-of-flow absolute positioning. | M1 | PLANNED |
| 3 | 7-Pass compiler pipeline & Layout Solvers (Passes 2-5) | Implement style cascade, intrinsic metrics, and layout solvers (dynamic, absolute, graph modes with compound graph solver). Implement Pass 5 structural absolutizer. | M2 | PLANNED |
| 4 | Edge Routing & Paint Engine (Passes 6-7) | Implement obstacle-aware orthogonal edge router and shape-aware port docking, label injection, and paint engine outputs (GIF temporal interpolation). | M3 | PLANNED |
| 5 | Legacy Code Cleanup & Extended E2E Verification | Delete legacy compatibility helpers and unused code. Extend and pass all tests in `tests/test_v2.py`. | M4 | PLANNED |

## Interface Contracts
- Schema: `validate_spec(spec)` returns normalised v2 spec.
- Compiler: `compile_spec(spec)` triggers 7-pass pipeline, producing a fully resolved IR with exact coordinates in `layout_offsets`.
- Layout: `layout(ir)` resolves positions for all canvas modes and absolutizes coordinates.
