# E2E Test Infra: FlowDraft Redesign Refinement

## Test Philosophy
- Opaque-box, requirement-driven. No dependency on implementation design.
- Methodology: Category-Partition + Boundary Value Analysis + Pairwise Combinatorial Testing + Real-World Workload Testing.

## Feature Inventory
| # | Feature | Source (Requirement) | Tier 1 (Feature Coverage) | Tier 2 (Boundary/Corner) | Tier 3 (Cross-Feature Pairwise) |
|---|---------|----------------------|:-------------------------:|:------------------------:|:-------------------------------:|
| 1 | Overlap Check & Bounding Box (R1) | ORIGINAL_REQUEST R1 | 5 | 5 | ✓ |
| 2 | Orthogonal Routing (R2) | ORIGINAL_REQUEST R2 | 5 | 5 | ✓ |
| 3 | Typography Wrapping & Scaling (R3) | ORIGINAL_REQUEST R3 | 5 | 5 | ✓ |
| 4 | Aesthetics & Rebranding (R4) | ORIGINAL_REQUEST R4 | 5 | 5 | ✓ |
| 5 | Rich Spec Updates (R5) | ORIGINAL_REQUEST R5 | 5 | 5 | ✓ |

## Test Architecture
- **Test Runner**: Run via `python -m pytest tests/e2e/test_e2e_suite.py` or `python -m unittest discover -s tests`.
- **Test Target**: `scripts/render_dynamic_diagram.py`.
- **Test Case Format**: Custom JSON specs written to temporary files, rendering outputs, and executing validations against generated `.excalidraw`, `.svg`, `.png`, and `.gif` files.
- **Directory Layout**:
  - `tests/e2e/test_e2e_suite.py`: E2E test suite python file.

## Test Case Detailed Plan

### Tier 1: Feature Coverage (Minimum 5 per Feature = 25 total)

#### Feature 1: Overlap Check & Bounding Box Enforcement (R1)
1. `test_r1_1_basic_bounding_box_computation`: Validates base bounds are calculated using elements and spacing.
2. `test_r1_2_overlap_elimination_moves_nodes`: Validates overlapping boxes are pushed apart along minimum penetration axis.
3. `test_r1_3_fixed_nodes_dont_move`: Validates nodes marked as `fixed` or `style.fixed` do not move during relaxation.
4. `test_r1_4_hierarchical_panel_resize`: Validates panels expand/envelope child nodes dynamically.
5. `test_r1_5_global_layout_shift_preserves_min_coords`: Validates alignment remains adjusted to the overall diagram top-left corner.

#### Feature 2: Orthogonal Routing, Node Crossing Avoidance, Port Attachment (R2)
1. `test_r2_1_orthogonal_connector_routing`: Validates all connector lines are orthogonal (horizontal/vertical lines).
2. `test_r2_2_port_attachment_boundaries`: Validates connections attach exactly to the node boundary edges.
3. `test_r2_3_avoid_node_crossings`: Validates connector lines route around/avoid crossing unrelated elements when paths exist.
4. `test_r2_4_avoid_overlapping_connector_paths`: Validates parallel or overlapping connection paths are offset.
5. `test_r2_5_port_direction_hints`: Validates routing hints on connections (e.g. force exit/enter top, bottom, left, right).

#### Feature 3: Typography Wrapping and Adaptive Scaling, Alignment (R3)
1. `test_r3_1_typography_wrapping`: Validates long text wraps to multiple lines rather than clipping.
2. `test_r3_2_adaptive_font_scaling`: Validates text scaling reduces font size to fit containers when constraints are reached.
3. `test_r3_3_text_alignment`: Validates center/left/right alignments on card titles, bodies, and standalone text.
4. `test_r3_4_cjk_wrapping`: Validates CJK characters wrap on characters correctly.
5. `test_r3_5_font_family_enforcement`: Validates text elements use `fontFamily: 5` (hand-drawn font) in Excalidraw output.

#### Feature 4: Aesthetics: Shadows, Glows, Borders, Rebrand Checks (R4)
1. `test_r4_1_glow_dot_animations`: Validates presence of animated glow dots pulsating along connection paths.
2. `test_r4_2_shadows_and_glows`: Validates glow/shadow effects are drawn on elements.
3. `test_r4_3_custom_borders_and_strokes`: Validates borders with custom colors, widths, styles (e.g. solid/dotted/dashed), and corner radii.
4. `test_r4_4_rebrand_cleans_branding`: Validates old trademark text matches are entirely replaced with FlowDraft.
5. `test_r4_5_signature_rendering`: Validates signature/watermark is correctly rendered in the top-right brand slot.

#### Feature 5: Rich Spec Updates (R5)
1. `test_r5_1_rich_style_properties`: Validates style overrides (fillColor, strokeColor, strokeWidth, strokeStyle) are correctly processed.
2. `test_r5_2_color_presets`: Validates color presets (cyan, blue, core, green) load and display correct colors.
3. `test_r5_3_icons_support`: Validates support for different icons (activity, layers, shield-check, database, etc.).
4. `test_r5_4_default_rich_spec_loading`: Validates that the default rich spec (`assets/default-spec.json`) renders cleanly.
5. `test_r5_5_legacy_backward_compatibility`: Validates legacy-format diagram specifications are correctly parsed and auto-converted.

---

### Tier 2: Boundary & Corner Cases (Minimum 5 per Feature = 25 total)

#### Feature 1: Overlap & Bounding Box Boundaries
1. `test_r1_boundary_1_extremely_dense_nodes`: Extremely dense overlapping nodes to stress-test relaxation loop termination.
2. `test_r1_boundary_2_large_padding_margins`: Very large custom margins and padding settings.
3. `test_r1_boundary_3_nested_panels`: Panels inside panels or hierarchy with missing parent panel references.
4. `test_r1_boundary_4_zero_dimensions`: Nodes specifying zero or negative width/height.
5. `test_r1_boundary_5_all_fixed_overlap`: Overlapping nodes where all are marked fixed (no movement should happen).

#### Feature 2: Orthogonal Routing Boundaries
1. `test_r2_boundary_1_nodes_aligned_exactly`: Nodes aligned exactly on the same coordinate axis (horizontal/vertical lines).
2. `test_r2_boundary_2_adjacent_touching_nodes`: Connectors between touching or extremely close nodes.
3. `test_r2_boundary_3_self_referencing_connection`: A node connecting to itself (self-loop routing).
4. `test_r2_boundary_4_nonexistent_node_references`: Verification of error catching on connections with invalid node IDs.
5. `test_r2_boundary_5_long_path_many_nodes`: Large chain connection path traversing >5 nodes in sequence.

#### Feature 3: Typography & Text Boundaries
1. `test_r3_boundary_1_extremely_long_unwrappable_string`: Long strings without any spaces (like URLs or hashes) to test scaling/truncation limits.
2. `test_r3_boundary_2_empty_text_fields`: Empty title and body parameters.
3. `test_r3_boundary_3_unicode_special_chars`: Emojis, math notation, and non-latin alphabets.
4. `test_r3_boundary_4_tiny_font_limit`: Verification that font size doesn't drop below the emergency limit (9pt).
5. `test_r3_boundary_5_newline_preservation`: Verification that manual newlines (`\n`) in the spec are preserved.

#### Feature 4: Aesthetics Boundaries
1. `test_r4_boundary_1_missing_signature`: Specification with None/empty signature.
2. `test_r4_boundary_2_no_motion_in_static_gif`: Verification that frames are identical except for glow dot motion.
3. `test_r4_boundary_3_theme_colors`: Verify correct theme mappings for "dark", "light", and "white" backgrounds.
4. `test_r4_boundary_4_unusual_stroke_styles`: Dash/dot stroke style variations on shapes.
5. `test_r4_boundary_5_gradient_fills`: Element rendering when gradient fills are configured.

#### Feature 5: Rich Spec Boundaries
1. `test_r5_boundary_1_invalid_style_values`: Check fallbacks for invalid hex colors, negative border widths, or invalid corner radii.
2. `test_r5_boundary_2_unknown_icons`: Fallback icon selected when specifying an unregistered icon string.
3. `test_r5_boundary_3_partial_styles`: Custom styles with some properties missing (verify merging with defaults).
4. `test_r5_boundary_4_extra_unsupported_fields`: Adding unknown fields to check if schema ignores/warns cleanly.
5. `test_r5_boundary_5_malformed_spec_json`: Spec json with syntax errors to verify graceful exit and error message reporting.

---

### Tier 3: Cross-Feature Combinations (Minimum 5 cases)
1. `test_comb_rebrand_and_scaling`: Pairwise check of rebrand replacements in a scaled-up custom resolution.
2. `test_comb_rebrand_and_svg`: Verify CJK rebrand replacements inside high-res vector SVG outputs.
3. `test_comb_scaling_and_svg`: Verify canvas dimension modifications properly align viewport in SVG outputs.
4. `test_comb_all_features_combined`: Complex spec combining rich custom style presets, rebrand strings, custom dimensions, and orthogonal connections in a single build.
5. `test_comb_text_fitting_and_scaling`: Pairwise check of wrapped text blocks inside heavily shrunken custom boxes to verify nested layout bounds recalculation.

---

### Tier 4: Real-World Application Scenarios (Minimum 5 Scenarios)
1. `test_scenario_1_microservices_auth_flow`: Multi-agent OAuth2 verification gateway diagram.
2. `test_scenario_2_data_ingestion_pipeline`: Real-time Kafka ingestion and Iceberg database storage pipeline.
3. `test_scenario_3_ml_training_pipeline`: MLOps training/evaluation pipeline with XGBoost, ONNX, and MLflow tracking.
4. `test_scenario_4_e_commerce_order_processing`: Checkout backend saga orchestrator diagram with payment hooks.
5. `test_scenario_5_devops_ci_cd_pipeline`: PR build, Trivy scan, Helm deploy, and Grafana monitoring dashboard diagram.

## Coverage Thresholds
- Tier 1: ≥5 per feature
- Tier 2: ≥5 per feature (where boundaries exist)
- Tier 3: pairwise coverage of major feature interactions
- Tier 4: ≥5 realistic application scenarios
