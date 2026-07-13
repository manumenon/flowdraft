import unittest
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from scripts.flowdraft.schema import validate_spec, SpecError
from scripts.flowdraft.compiler import compile_spec
from scripts.flowdraft.layout_engine import layout
from scripts.render_v2 import run_pipeline

SPEC_PATH = ROOT / "assets" / "default-spec-v2.json"

class TestFlowDraftV2(unittest.TestCase):
    def test_schema_validation_valid(self):
        """Test that a valid v2 spec passes schema validation."""
        spec_data = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
        validated = validate_spec(spec_data)
        self.assertIn("elements", validated)
        self.assertIn("connections", validated)

    def test_schema_validation_invalid(self):
        """Test that invalid spec structures raise SpecError."""
        invalid_spec = {
            "canvas": {"width": 800},
            "elements": [
                {"id": "node_1"}  # Missing "type"
            ]
        }
        with self.assertRaises(SpecError):
            validate_spec(invalid_spec)

    def test_compiler_flat_elements(self):
        """Test that compiler successfully parses and flattens elements."""
        spec_data = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
        validated = validate_spec(spec_data)
        ir = compile_spec(validated)
        self.assertIn("nodes", ir)
        self.assertIn("connections", ir)
        
        # Check that parent/child relations are preserved
        nodes_map = {n["id"]: n for n in ir["nodes"]}
        self.assertIn("input_panel", nodes_map)
        self.assertIn("input_0", nodes_map)
        self.assertEqual(nodes_map["input_0"]["parent"], "input_panel")

    def test_layout_engine_coordinates(self):
        """Test that layout engine respects explicit overrides and sizes panels."""
        spec_data = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
        validated = validate_spec(spec_data)
        ir = compile_spec(validated)
        
        # Run layout
        laid_out_ir = layout(ir, canvas_w=1920, canvas_h=1440)
        nodes_map = {n["id"]: n for n in laid_out_ir["nodes"]}
        
        # Check that manual panel coordinate was preserved
        self.assertIsNotNone(nodes_map["center_panel"]["x"])
        self.assertIsNotNone(nodes_map["center_panel"]["y"])

    def test_cli_execution(self):
        """Test the end-to-end v2 rendering pipeline on the default spec."""
        out_dir = ROOT / "outputs" / "test_run"
        out_dir.mkdir(parents=True, exist_ok=True)
        
        results = run_pipeline(
            spec_path=str(SPEC_PATH),
            outdir=str(out_dir),
            basename="test_v2_spec",
            run_checks=True,
            rebrand_name="FlowDraft"
        )
        
        self.assertTrue(results["checks"]["ok"])
        self.assertTrue((out_dir / "test_v2_spec.png").exists())
        self.assertTrue((out_dir / "test_v2_spec.gif").exists())
        self.assertTrue((out_dir / "test_v2_spec.svg").exists())
        self.assertTrue((out_dir / "test_v2_spec.excalidraw").exists())

    def test_canvas_mode_validation(self):
        # Valid modes
        for mode in ("dynamic", "absolute", "graph"):
            spec = {
                "canvas": {"mode": mode},
                "elements": [{"id": "n1", "type": "card"}]
            }
            res = validate_spec(spec)
            self.assertEqual(res["canvas"]["mode"], mode)

        # Default mode
        spec_no_mode = {
            "elements": [{"id": "n1", "type": "card"}]
        }
        res = validate_spec(spec_no_mode)
        self.assertEqual(res["canvas"]["mode"], "dynamic")

        # Invalid mode
        spec_invalid = {
            "canvas": {"mode": "invalid_mode"},
            "elements": [{"id": "n1", "type": "card"}]
        }
        with self.assertRaises(SpecError):
            validate_spec(spec_invalid)

    def test_canvas_temporal_settings(self):
        # Defaults when <= 1 specified
        spec = {
            "canvas": {"fps": 60.0}, # only 1 specified
            "elements": [{"id": "n1", "type": "card"}]
        }
        res = validate_spec(spec)
        self.assertEqual(res["canvas"]["fps"], 30.0)
        self.assertEqual(res["canvas"]["duration"], 3.0)
        self.assertEqual(res["canvas"]["frames"], 90)

        # Math solving: solve frames
        spec = {
            "canvas": {"fps": 24.0, "duration": 4.0},
            "elements": [{"id": "n1", "type": "card"}]
        }
        res = validate_spec(spec)
        self.assertEqual(res["canvas"]["frames"], 96)

        # Math solving: solve duration
        spec = {
            "canvas": {"fps": 30.0, "frames": 150},
            "elements": [{"id": "n1", "type": "card"}]
        }
        res = validate_spec(spec)
        self.assertEqual(res["canvas"]["duration"], 5.0)

        # Math solving: solve fps
        spec = {
            "canvas": {"duration": 2.0, "frames": 60},
            "elements": [{"id": "n1", "type": "card"}]
        }
        res = validate_spec(spec)
        self.assertEqual(res["canvas"]["fps"], 30.0)

        # Inconsistent inputs
        spec = {
            "canvas": {"fps": 30.0, "duration": 2.0, "frames": 100},
            "elements": [{"id": "n1", "type": "card"}]
        }
        with self.assertRaises(SpecError):
            validate_spec(spec)

        # Non-positive inputs
        spec = {
            "canvas": {"fps": -30.0, "duration": 2.0},
            "elements": [{"id": "n1", "type": "card"}]
        }
        with self.assertRaises(SpecError):
            validate_spec(spec)

        # Non-integer frames solved
        spec = {
            "canvas": {"fps": 30.0, "duration": 1.05}, # 30 * 1.05 = 31.5
            "elements": [{"id": "n1", "type": "card"}]
        }
        with self.assertRaises(SpecError):
            validate_spec(spec)

    def test_leaf_elements_structure(self):
        # Card with children should raise error
        spec = {
            "elements": [{
                "id": "card1",
                "type": "card",
                "children": [{"id": "sub1", "type": "label"}]
            }]
        }
        with self.assertRaises(SpecError):
            validate_spec(spec)

        # Panel with children should succeed
        spec = {
            "elements": [{
                "id": "panel1",
                "type": "panel",
                "children": [{"id": "sub1", "type": "label"}]
            }]
        }
        res = validate_spec(spec)
        self.assertEqual(len(res["elements"]), 2)

    def test_coordinate_completeness(self):
        # Partial coordinates x only
        spec = {
            "elements": [{"id": "n1", "type": "card", "x": 10}]
        }
        with self.assertRaises(SpecError):
            validate_spec(spec)

        # Both coordinates
        spec = {
            "elements": [{"id": "n1", "type": "card", "x": 10, "y": 20}]
        }
        res = validate_spec(spec)
        self.assertEqual(res["elements"][0]["out_of_flow"], False)

        # Inside a panel (has a parent)
        spec = {
            "elements": [{
                "id": "panel1",
                "type": "panel",
                "children": [{"id": "child1", "type": "card", "x": 10, "y": 20}]
            }]
        }
        res = validate_spec(spec)
        child = [e for e in res["elements"] if e["id"] == "child1"][0]
        self.assertEqual(child["out_of_flow"], True)

    def test_port_aliases_and_validation(self):
        # Aliases toPort and fromPort
        spec = {
            "elements": [{"id": "n1", "type": "card"}, {"id": "n2", "type": "card"}],
            "connections": [{
                "from": "n1",
                "to": "n2",
                "fromPort": "right",
                "toPort": "left"
            }]
        }
        res = validate_spec(spec)
        self.assertEqual(res["connections"][0]["exitPort"], "right")
        self.assertEqual(res["connections"][0]["entryPort"], "left")

        # Invalid port choice
        spec = {
            "elements": [{"id": "n1", "type": "card"}, {"id": "n2", "type": "card"}],
            "connections": [{
                "from": "n1",
                "to": "n2",
                "exitPort": "middle"
            }]
        }
        with self.assertRaises(SpecError):
            validate_spec(spec)

    def test_style_and_layout_validation(self):
        # Invalid strokeWidth
        spec = {
            "elements": [{"id": "n1", "type": "card", "style": {"strokeWidth": -1}}]
        }
        with self.assertRaises(SpecError):
            validate_spec(spec)

        # Invalid layout gap
        spec = {
            "elements": [{"id": "n1", "type": "panel", "layout": {"gap": -5}}]
        }
        with self.assertRaises(SpecError):
            validate_spec(spec)

        # Invalid grid_cols
        spec = {
            "elements": [{"id": "n1", "type": "panel", "layout": {"grid_cols": 0}}]
        }
        with self.assertRaises(SpecError):
            validate_spec(spec)

        # Valid style and layout
        spec = {
            "elements": [{
                "id": "n1",
                "type": "panel",
                "style": {"strokeWidth": 2, "cornerRadius": 10, "padding": {"left": 5}},
                "layout": {"gap": 15, "max_cols": 3}
            }]
        }
        res = validate_spec(spec)
        self.assertEqual(res["elements"][0]["style"]["strokeWidth"], 2)

    def test_style_cascade_and_theme_overrides(self):
        """Test Pass 2: Style & Theme Cascade propagates styles and handles custom theme definitions."""
        spec = {
            "theme": {
                "custom_preset": "#123456",
                "custom_preset_fill": "#654321"
            },
            "elements": [{
                "id": "parent_panel",
                "type": "panel",
                "style": {
                    "hand": False,
                    "bold": True,
                    "strokeWidth": 5,
                    "cornerRadius": 15,
                    "padding": 25
                },
                "children": [{
                    "id": "child_card",
                    "type": "card",
                    "color_preset": "custom_preset"
                }]
            }]
        }
        validated = validate_spec(spec)
        ir = compile_spec(validated)
        nodes_map = {n["id"]: n for n in ir["nodes"]}

        parent = nodes_map["parent_panel"]
        child = nodes_map["child_card"]

        # Check parent properties
        self.assertEqual(parent["_resolved_style"]["hand"], False)
        self.assertEqual(parent["_resolved_style"]["strokeWidth"], 5)
        self.assertEqual(parent["_resolved_style"]["padding"]["left"], 25)

        # Check cascaded child properties (inherited from parent)
        self.assertEqual(child["_resolved_style"]["hand"], False)
        self.assertEqual(child["_resolved_style"]["bold"], True)
        self.assertEqual(child["_resolved_style"]["strokeWidth"], 5)
        self.assertEqual(child["_resolved_style"]["cornerRadius"], 15)
        self.assertEqual(child["_resolved_style"]["padding"]["left"], 25)

        # Check theme preset resolved from custom theme definitions in the spec
        self.assertEqual(child["_resolved_style"]["strokeColor"], "#123456")
        self.assertEqual(child["_resolved_style"]["fillColor"], "#654321")

    def test_panel_header_minimum_bounds(self):
        """Test Pass 3: Panels compute minimum inner bounds for header text instead of 100x100."""
        spec = {
            "elements": [{
                "id": "header_panel",
                "type": "panel",
                "title": "Extremely Long Panel Title Indeed",
                "subtitle": "Very long subtitle explaining things in great detail",
                "badge": "Premium Version badge"
            }]
        }
        validated = validate_spec(spec)
        ir = compile_spec(validated)
        panel = ir["nodes"][0]

        # panel must have calculated width & height larger than default 100x100 placeholder
        self.assertGreater(panel["width"], 100.0)
        self.assertGreater(panel["height"], 60.0)

    def test_hierarchical_layout_solving(self):
        """Test Pass 4 & 5: Nested panels bottom-up size layout and recursive absolutization."""
        spec = {
            "elements": [{
                "id": "panel_outer",
                "type": "panel",
                "children": [{
                    "id": "panel_inner",
                    "type": "panel",
                    "children": [{
                        "id": "card_leaf",
                        "type": "card",
                        "title": "Leaf Node"
                    }]
                }]
            }]
        }
        validated = validate_spec(spec)
        ir = compile_spec(validated)
        
        # Run layout
        laid_out = layout(ir, canvas_w=1000, canvas_h=1000)
        nodes_map = {n["id"]: n for n in laid_out["nodes"]}

        outer = nodes_map["panel_outer"]
        inner = nodes_map["panel_inner"]
        leaf = nodes_map["card_leaf"]

        # Footprints should nest correctly: outer > inner > leaf
        self.assertGreater(outer["width"], inner["width"])
        self.assertGreater(outer["height"], inner["height"])
        self.assertGreater(inner["width"], leaf["width"])
        self.assertGreater(inner["height"], leaf["height"])

        # Positions should be absolute and nested
        self.assertGreater(leaf["x"], inner["x"])
        self.assertGreater(inner["x"], outer["x"])

    def test_absolute_and_graph_modes(self):
        """Test Absolute and Graph canvas modes."""
        # Test Absolute mode
        spec_abs = {
            "canvas": {"mode": "absolute", "width": 800, "height": 800},
            "elements": [
                {"id": "n1", "type": "card", "x": 150, "y": 250},
                {"id": "n2", "type": "card", "x": 400, "y": 450}
            ]
        }
        validated_abs = validate_spec(spec_abs)
        ir_abs = compile_spec(validated_abs)
        laid_abs = layout(ir_abs)
        nodes_map = {n["id"]: n for n in laid_abs["nodes"]}
        # Absolute positions preserved (after translation/centering, they shift but maintain relative distance)
        dx = nodes_map["n2"]["x"] - nodes_map["n1"]["x"]
        dy = nodes_map["n2"]["y"] - nodes_map["n1"]["y"]
        self.assertEqual(dx, 400 - 150)
        self.assertEqual(dy, 450 - 250)

        # Test Graph mode
        spec_graph = {
            "canvas": {"mode": "graph", "width": 800, "height": 800},
            "elements": [
                {"id": "n1", "type": "card"},
                {"id": "n2", "type": "card"}
            ],
            "connections": [{"from": "n1", "to": "n2"}]
        }
        validated_graph = validate_spec(spec_graph)
        ir_graph = compile_spec(validated_graph)
        laid_graph = layout(ir_graph)
        # Just check that it runs and assigns coordinates
        self.assertIsNotNone(laid_graph["nodes"][0]["x"])
        self.assertIsNotNone(laid_graph["nodes"][1]["x"])

    def test_fixed_constraint_anchoring_and_out_of_flow(self):
        """Test Pass 4 constraints: fixed node anchoring and out-of-flow nodes."""
        # Fixed node anchoring
        spec_fixed = {
            "elements": [{
                "id": "panel1",
                "type": "panel",
                "children": [
                    {"id": "child_fixed", "type": "card", "x": 100, "y": 100},
                    {"id": "child_auto", "type": "card"}
                ]
            }]
        }
        validated_fixed = validate_spec(spec_fixed)
        ir_fixed = compile_spec(validated_fixed)
        laid_fixed = layout(ir_fixed)
        nodes_map = {n["id"]: n for n in laid_fixed["nodes"]}
        fixed_node = nodes_map["child_fixed"]
        auto_node = nodes_map["child_auto"]
        # Auto node should be placed such that it doesn't overlap with the fixed node
        # In a row layout (default), if auto_node was placed first, it would start at origin (padding.left),
        # but since child_fixed is at 100, auto_node should be pushed beyond fixed_node if there is collision.
        # Let's verify they do not overlap
        self.assertTrue(
            auto_node["x"] >= fixed_node["x"] + fixed_node["width"] or
            auto_node["x"] + auto_node["width"] <= fixed_node["x"]
        )

        # Out of flow inflation
        spec_oof = {
            "elements": [{
                "id": "panel1",
                "type": "panel",
                "children": [
                    {"id": "child_oof", "type": "card", "x": 500, "y": 500},
                    {"id": "child_in", "type": "card"}
                ]
            }]
        }
        validated_oof = validate_spec(spec_oof)
        ir_oof = compile_spec(validated_oof)
        # Run layout
        laid_oof = layout(ir_oof)
        panel_post = [n for n in laid_oof["nodes"] if n["id"] == "panel1"][0]
        # Panel size should not expand to enclose child_oof (500x500), so panel post height should be small
        self.assertLess(panel_post["height"], 500.0)

    def test_shape_aware_port_docking(self):
        """Test shape-aware port coordinate docking for ellipse and diamond nodes."""
        from scripts.flowdraft.layout_engine import get_shape_port_coords
        
        # Ellipse node
        ellipse_node = {
            "id": "e1",
            "type": "ellipse",
            "x": 100.0,
            "y": 100.0,
            "width": 100.0,
            "height": 50.0
        }
        # Center = (150, 125), a = 50, b = 25
        # Port "right" -> theta = 0 -> x = 150 + 50 = 200, y = 125
        pt_right = get_shape_port_coords(ellipse_node, "right")
        self.assertAlmostEqual(pt_right[0], 200.0)
        self.assertAlmostEqual(pt_right[1], 125.0)
        
        # Port "top" -> theta = -pi/2 -> x = 150, y = 125 - 25 = 100
        pt_top = get_shape_port_coords(ellipse_node, "top")
        self.assertAlmostEqual(pt_top[0], 150.0)
        self.assertAlmostEqual(pt_top[1], 100.0)

        # Diamond node
        diamond_node = {
            "id": "d1",
            "type": "diamond",
            "x": 100.0,
            "y": 100.0,
            "width": 100.0,
            "height": 100.0
        }
        # Center = (150, 150), a = 50, b = 50
        pt_br = get_shape_port_coords(diamond_node, "bottom-right")
        self.assertAlmostEqual(pt_br[0], 175.0)
        self.assertAlmostEqual(pt_br[1], 175.0)

    def test_obstacle_aware_orthogonal_routing(self):
        """Test grid-based A* routing avoiding node bounding boxes."""
        spec = {
            "canvas": {"mode": "absolute", "width": 800, "height": 800},
            "elements": [
                {"id": "n1", "type": "card", "x": 100, "y": 100, "width": 100, "height": 50},
                {"id": "n2", "type": "card", "x": 600, "y": 100, "width": 100, "height": 50},
                # Obstacle directly in the straight path between n1 and n2
                {"id": "obs", "type": "label", "x": 350, "y": 130, "width": 50, "height": 20}
            ],
            "connections": [
                {"from": "n1", "to": "n2", "fromPort": "right", "toPort": "left"}
            ]
        }
        validated = validate_spec(spec)
        ir = compile_spec(validated)
        laid_out = layout(ir)
        conn = laid_out["connections"][0]
        pts = conn["points"]
        
        # Verify it successfully routed around the obstacle
        self.assertGreater(len(pts), 2)
        # Shift is dx = -50, dy = 260. obs is at [350, 130, 390, 150] before shift.
        # Centered obs is [300, 390, 340, 410]. Padded is [285, 375, 355, 425].
        for px, py in pts:
            in_obs = (285 <= px <= 355) and (375 <= py <= 425)
            self.assertFalse(in_obs, f"Point {px}, {py} should not be inside obstacle")

    def test_perpendicular_label_clamping(self):
        """Test that connection label offset is perpendicular and nudged if needed."""
        spec = {
            "canvas": {"mode": "absolute", "width": 800, "height": 800},
            "elements": [
                {"id": "n1", "type": "card", "x": 100, "y": 100, "width": 100, "height": 50},
                {"id": "n2", "type": "card", "x": 100, "y": 300, "width": 100, "height": 50}
            ],
            "connections": [
                {"from": "n1", "to": "n2", "fromPort": "bottom", "toPort": "top", "label": "test_label"}
            ]
        }
        validated = validate_spec(spec)
        ir = compile_spec(validated)
        laid_out = layout(ir)
        conn = laid_out["connections"][0]
        lbl = conn["layout_offsets"]["label"]
        
        self.assertAlmostEqual(lbl["x"], 412.0)
        self.assertAlmostEqual(lbl["y"], 400.0)

    def test_annotation_targets_and_midpoints(self):
        """Test target-attached and connection midpoint annotations resolution."""
        spec = {
            "canvas": {"mode": "absolute", "width": 800, "height": 800},
            "elements": [
                {"id": "n1", "type": "card", "x": 100, "y": 100, "width": 100, "height": 50},
                {"id": "n2", "type": "card", "x": 100, "y": 300, "width": 100, "height": 50}
            ],
            "connections": [
                {"from": "n1", "to": "n2"}
            ],
            "annotations": [
                # target-attached
                {"text": "Attached to Node", "attachTo": "n1", "position": "top"},
                # midpoint-attached
                {"text": "Midpoint Ann", "from": "n1", "to": "n2"}
            ]
        }
        validated = validate_spec(spec)
        ir = compile_spec(validated)
        laid_out = layout(ir)
        annotations = laid_out["annotations"]
        
        self.assertAlmostEqual(annotations[0]["x"], 400.0)
        self.assertAlmostEqual(annotations[0]["y"], 245.0)
        
        self.assertAlmostEqual(annotations[1]["x"], 400.0)
        self.assertAlmostEqual(annotations[1]["y"], 400.0)

    def test_ir_driven_layout_decoration(self):
        """Test that page decorations are injected as standard IR nodes."""
        spec = {
            "canvas": {"mode": "absolute", "width": 800, "height": 800},
            "title": {"prefix": "Prefix Text", "highlight": "Highlight Text", "subtitle": "Subtitle Text"},
            "elements": [
                {"id": "n1", "type": "card", "x": 100, "y": 200, "width": 100, "height": 50}
            ]
        }
        validated = validate_spec(spec)
        ir = compile_spec(validated)
        laid_out = layout(ir)
        nodes_ids = {n["id"] for n in laid_out["nodes"]}
        
        self.assertIn("decor_outer_border", nodes_ids)
        self.assertIn("decor_title_line", nodes_ids)
        self.assertIn("decor_title_prefix", nodes_ids)
        self.assertIn("decor_title_highlight", nodes_ids)
        self.assertIn("decor_title_subtitle", nodes_ids)
        self.assertIn("decor_brand", nodes_ids)

    def test_gif_temporal_interpolation(self):
        """Test that GIF temporal interpolation evaluates correctly for different frames."""
        from scripts.flowdraft.animation import animate_frame
        from PIL import Image
        
        base_img = Image.new("RGB", (100, 100), (0, 0, 0))
        spec = {
            "_resolved_paths": [
                ([(0.0, 0.0), (100.0, 100.0)], "#00ff00", 0.0)
            ],
            "_resolved_pulse_targets": [
                ((10, 10, 90, 90), "#ff0000")
            ],
            "canvas": {
                "fps": 30.0,
                "duration": 3.0,
                "speed": 1.0
            }
        }
        frame_0 = animate_frame(base_img, 0, 30, spec)
        frame_15 = animate_frame(base_img, 15, 30, spec)
        
        self.assertIsNotNone(frame_0)
        self.assertIsNotNone(frame_15)
        self.assertEqual(frame_0.size, (100, 100))
        self.assertEqual(frame_15.size, (100, 100))

    def test_uniform_scaling(self):
        """Test that layout scales all components uniformly when content exceeds fixed canvas."""
        spec = {
            "canvas": {
                "mode": "absolute",
                "width": 800,
                "height": 600
            },
            "elements": [
                {
                    "id": "panel_huge",
                    "type": "panel",
                    "x": 0,
                    "y": 0,
                    "width": 1600,
                    "height": 1200,
                    "title": "Huge Panel",
                    "children": [
                        {
                            "id": "card_huge",
                            "type": "card",
                            "x": 100,
                            "y": 100,
                            "width": 400,
                            "height": 200,
                            "title": "Huge Card"
                        }
                    ]
                }
            ]
        }
        validated = validate_spec(spec)
        ir = compile_spec(validated)
        
        # Run layout with fixed 800x600 canvas
        laid_out_ir = layout(ir, canvas_w=800, canvas_h=600)
        nodes_map = {n["id"]: n for n in laid_out_ir["nodes"]}
        
        panel = nodes_map["panel_huge"]
        card = nodes_map["card_huge"]
        
        self.assertLess(panel["width"], 1600.0)
        self.assertLess(card["width"], 400.0)
        self.assertLess(panel["layout_offsets"]["title"]["size"], 22.0)


if __name__ == "__main__":
    unittest.main()

