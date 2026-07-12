# FlowDraft E2E Test Suite Infrastructure

This document describes the End-to-End (E2E) testing infrastructure for the FlowDraft rendering engine and maps the requirements from `ORIGINAL_REQUEST.md` to specific E2E test cases.

## Test Directory Layout
The E2E tests are located in `tests/e2e` and structured into four tiers.

- `tests/e2e/__init__.py` - Package initialization.
- `tests/e2e/test_e2e_suite.py` - Complete test suite containing Tiers 1-4.
- `tests/e2e/TEST_INFRA.md` - Legacy E2E test documentation.
- `tests/e2e/TEST_READY.md` - Legacy E2E test readiness report.

---

## Requirement Mapping

### R1. Dynamic Overlap-Free Layout Engine
**Requirement Description:**
- Completely resolve overlapping bounding boxes (panels, cards, inputs, diamonds).
- Dynamic layout placement based on connections and text size (adjusting boxes dynamically to encompass text size, padding, and children).
- Text Wrapping & Fitting (English and CJK auto-wrapping, scaling without box edges/icons/lines overlap).

| Test Class | Test Case Name | Feature Dimension Covered |
|---|---|---|
| `E2ETier1FeatureCoverage` | `test_f1_fc_1_overlap_two_cards` | Resolving overlap of basic cards |
| `E2ETier1FeatureCoverage` | `test_f1_fc_2_overlap_card_input` | Resolving overlap of mixed element types (card and input) |
| `E2ETier1FeatureCoverage` | `test_f1_fc_3_overlap_card_diamond` | Resolving overlap of card and diamond elements |
| `E2ETier1FeatureCoverage` | `test_f1_fc_4_overlap_fixed_does_not_move` | Ensuring elements marked as fixed do not have coordinates shifted |
| `E2ETier1FeatureCoverage` | `test_f1_fc_5_overlap_within_panel` | Overlap resolution of elements inside a panel boundary |
| `E2ETier1FeatureCoverage` | `test_f2_fc_1_dynamic_card_width_by_title` | Bounding box width adjustment based on title length |
| `E2ETier1FeatureCoverage` | `test_f2_fc_2_dynamic_card_height_by_body` | Bounding box height adjustment based on body content |
| `E2ETier1FeatureCoverage` | `test_f2_fc_3_panel_autosize_by_children` | Panel width/height autosizing based on child cards |
| `E2ETier1FeatureCoverage` | `test_f2_fc_4_dynamic_diamond_size` | Diamond decision node sizing based on label length |
| `E2ETier1FeatureCoverage` | `test_f2_fc_5_custom_panel_padding` | Panel sizing incorporating custom padding values |
| `E2ETier1FeatureCoverage` | `test_f3_fc_1_english_word_wrapping` | Word-based text wrapping for English body text |
| `E2ETier1FeatureCoverage` | `test_f3_fc_2_cjk_char_wrapping` | Character-based text wrapping for CJK body text |
| `E2ETier1FeatureCoverage` | `test_f3_fc_3_adaptive_font_scaling_standard` | Automatic scaling down of font size to fit long unwrappable words |
| `E2ETier1FeatureCoverage` | `test_f3_fc_4_text_alignments` | Verifying different text alignment styles (left, center, right) |
| `E2ETier1FeatureCoverage` | `test_f3_fc_5_font_family_handwriting` | Application of font family presets (e.g. handwriting style) |
| `E2ETier2BoundaryCorner` | `test_f1_bc_1_extreme_density_overlap` | Stress test with 15 highly overlapping nodes |
| `E2ETier2BoundaryCorner` | `test_f1_bc_2_all_fixed_overlap` | Handling overlapping nodes when all nodes are marked fixed |
| `E2ETier2BoundaryCorner` | `test_f1_bc_3_nested_panels_deep` | Bounding box calculation for nested panels |
| `E2ETier2BoundaryCorner` | `test_f1_bc_4_negative_zero_dimensions` | Graceful fallback and sizing for negative or zero input dimensions |
| `E2ETier2BoundaryCorner` | `test_f1_bc_5_extreme_margins` | Sizing under extreme node/panel margin constraints |
| `E2ETier2BoundaryCorner` | `test_f2_bc_1_empty_title_and_body` | Layout calculation with empty strings for title and body |
| `E2ETier2BoundaryCorner` | `test_f2_bc_2_single_character_elements` | Sizing for single character strings (edge of minimal bounds) |
| `E2ETier2BoundaryCorner` | `test_f2_bc_3_huge_unwrappable_title` | Extreme width expansion for very long single-word titles |
| `E2ETier2BoundaryCorner` | `test_f2_bc_4_deeply_nested_panel_autosizing` | Autosizing calculations propagating through nested panels |
| `E2ETier2BoundaryCorner` | `test_f2_bc_5_floating_point_precision_dimensions` | Sizing with high-precision float coordinates |
| `E2ETier2BoundaryCorner` | `test_f3_bc_1_extremely_long_unwrappable_word` | Boundary scaling down for extremely long unwrappable words |
| `E2ETier2BoundaryCorner` | `test_f3_bc_2_special_characters_emojis` | Font rendering & size calculations with emojis & non-Latin strings |
| `E2ETier2BoundaryCorner` | `test_f3_bc_3_newline_preservation` | Preservation of explicit newlines in body text |
| `E2ETier2BoundaryCorner` | `test_f3_bc_4_tiny_container_scaling` | Sizing and scaling limits inside extremely small parent boxes |
| `E2ETier2BoundaryCorner` | `test_f3_bc_5_cjk_english_mixed` | Sizing calculations for mixed English and CJK texts |

---

### R2. Smart Obstacle-Avoiding Line Routing
**Requirement Description:**
- Rewrite or enhance connection line routing to cleanly navigate around nodes (panels, cards, diamonds) and exit/entry ports.
- Implement parallel offset paths for multiple connections between same regions/nodes to prevent overlap.

| Test Class | Test Case Name | Feature Dimension Covered |
|---|---|---|
| `E2ETier1FeatureCoverage` | `test_f4_fc_1_direct_path_no_obstacle` | Routing standard straight connection when path is clear |
| `E2ETier1FeatureCoverage` | `test_f4_fc_2_obstacle_avoidance_horizontal` | Routing around a blocking obstacle horizontally |
| `E2ETier1FeatureCoverage` | `test_f4_fc_3_obstacle_avoidance_vertical` | Routing around a blocking obstacle vertically |
| `E2ETier1FeatureCoverage` | `test_f4_fc_4_routing_inside_panel` | Connection routing contained entirely inside panel boundaries |
| `E2ETier1FeatureCoverage` | `test_f4_fc_5_port_direction_hints` | Honoring designated entry and exit ports for connection line start/end |
| `E2ETier1FeatureCoverage` | `test_f5_fc_1_parallel_two_connections` | Offsetting two parallel connections to prevent overlap |
| `E2ETier1FeatureCoverage` | `test_f5_fc_2_parallel_three_connections` | Offsetting three parallel connections |
| `E2ETier1FeatureCoverage` | `test_f5_fc_3_parallel_self_loop_offsets` | Offsetting multiple self-loop connections on a single node |
| `E2ETier1FeatureCoverage` | `test_f5_fc_4_parallel_adjacent_nodes` | Offsetting parallel connections between adjacent nodes |
| `E2ETier1FeatureCoverage` | `test_f5_fc_5_parallel_offset_spacing_custom` | Custom offset spacing configuration limits |
| `E2ETier2BoundaryCorner` | `test_f4_bc_1_no_valid_path` | Fallback routing when no non-intersecting path exists |
| `E2ETier2BoundaryCorner` | `test_f4_bc_2_self_loop_boundaries` | Handling loop-back connections on boundary coordinates |
| `E2ETier2BoundaryCorner` | `test_f4_bc_3_nonexistent_node_id` | Proper validation and failure on invalid/nonexistent node IDs |
| `E2ETier2BoundaryCorner` | `test_f4_bc_4_exactly_aligned_axes` | Routing when node axes are perfectly aligned (potential divide-by-zero risk) |
| `E2ETier2BoundaryCorner` | `test_f4_bc_5_long_path_chain` | Multi-segment connection routing across a chain of nodes |
| `E2ETier2BoundaryCorner` | `test_f5_bc_1_many_parallel_connections` | Routing 10 parallel connections between a single pair of nodes |
| `E2ETier2BoundaryCorner` | `test_f5_bc_2_parallel_opposing_directions` | Offsetting parallel lines running in opposite directions |
| `E2ETier2BoundaryCorner` | `test_f5_bc_3_zero_spacing_offset` | Routing when spacing parameter for offsets is set to zero |
| `E2ETier2BoundaryCorner` | `test_f5_bc_4_parallel_self_loops_large_count` | Offsetting 5 parallel self-loop connections |
| `E2ETier2BoundaryCorner` | `test_f5_bc_5_parallel_offset_extreme_coordinates` | Routing parallel lines at extreme canvas coordinates |

---

### R3. Premium Spec Design Update & Themes
**Requirement Description:**
- Redesign `assets/default-spec.json` to showcase multi-layered layout, distinct styles, clean groupings, visual aesthetics.
- Ensure proper theme support (dark, light, white), stroke widths, styles, presets.

| Test Class | Test Case Name | Feature Dimension Covered |
|---|---|---|
| `E2ETier1FeatureCoverage` | `test_f6_fc_1_theme_dark_palette` | Applying dark theme palette colors |
| `E2ETier1FeatureCoverage` | `test_f6_fc_2_theme_light_palette` | Applying light theme palette colors |
| `E2ETier1FeatureCoverage` | `test_f6_fc_3_theme_white_palette` | Applying white theme palette colors |
| `E2ETier1FeatureCoverage` | `test_f6_fc_4_custom_stroke_width_and_style` | Verifying custom stroke widths and dash/solid styles |
| `E2ETier1FeatureCoverage` | `test_f6_fc_5_custom_colors_preset` | Verifying color preset overrides (e.g. cyan preset) |
| `E2ETier2BoundaryCorner` | `test_f6_bc_1_invalid_hex_colors` | Fallback handling when invalid hex color codes are supplied |
| `E2ETier2BoundaryCorner` | `test_f6_bc_2_unknown_preset_theme` | Fallback theme handling for unknown theme strings |
| `E2ETier2BoundaryCorner` | `test_f6_bc_3_missing_style_subkeys` | Sane defaults when style specifications are partially empty |
| `E2ETier2BoundaryCorner` | `test_f6_bc_4_unsupported_stroke_styles` | Fallback behavior when unsupported stroke styles are requested |
| `E2ETier2BoundaryCorner` | `test_f6_bc_5_negative_stroke_width` | Fallback behavior for negative stroke widths |
| `E2ETier3Combinations` | `test_comb_rebrand_and_scaling` | Multi-feature integration: Rebranding + scaling |
| `E2ETier3Combinations` | `test_comb_rebrand_and_svg` | Multi-feature integration: Rebranding + SVG verification |
| `E2ETier3Combinations` | `test_comb_scaling_and_svg` | Multi-feature integration: Coordinate scaling + SVG export |
| `E2ETier3Combinations` | `test_comb_all_features_combined` | Complex integration: Theme + rebrand + obstacle avoidance + parallel lines + multi-frame GIF |
| `E2ETier3Combinations` | `test_comb_text_fitting_and_scaling` | Complex integration: Text fitting + Auto-scaling CJK text |
| `E2ETier3Combinations` | `test_comb_obstacle_avoidance_and_parallel_offsets` | Complex integration: Obstacle avoidance + parallel offsets |
| `E2ETier4Scenarios` | `test_scenario_1_microservices_auth_flow` | Real-world: OAuth2/OIDC microservices flow |
| `E2ETier4Scenarios` | `test_scenario_2_data_ingestion_pipeline` | Real-world: Kafka ingestion & Iceberg memory buffer |
| `E2ETier4Scenarios` | `test_scenario_3_ml_training_pipeline` | Real-world: Machine Learning model continuous training |
| `E2ETier4Scenarios` | `test_scenario_4_e_commerce_order_processing` | Real-world: E-Commerce checkout & order orchestration |
| `E2ETier4Scenarios` | `test_scenario_5_devops_ci_cd_pipeline` | Real-world: DevOps CI/CD pipeline |

---

## Execution Command
To execute the E2E test suite, run the following command in the workspace root:

```bash
python -m unittest tests.e2e.test_e2e_suite
```
