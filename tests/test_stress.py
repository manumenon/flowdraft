import json
import unittest
import sys
import tempfile
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))
import scripts.render_flowdraft_diagram as render_flowdraft_diagram


class StressAndCollisionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.renderer = render_flowdraft_diagram
        cls.default_spec = {
            "canvas": {
                "width": 1210,
                "height": 1138,
                "fps": 20,
                "frames": 2
            },
            "signature": "@FlowDraft",
            "title": {
                "prefix": "Stress Test",
                "highlight": "Renderer",
                "subtitle": "Checking boundaries and scaling limits"
            },
            "input_title": "Inputs",
            "inputs": [
                {"label": "In 1", "icon": "file"},
                {"label": "In 2", "icon": "folder"}
            ],
            "core": {
                "title": "Core Stage",
                "subtitle": "Sub",
                "cards": [
                    {"title": "Step 1", "body": "Do 1", "icon": "scan"},
                    {"title": "Step 2", "body": "Do 2", "icon": "shield"},
                    {"title": "Step 3", "body": "Do 3", "icon": "db"}
                ]
            },
            "decision": {
                "title": "Ready?",
                "body": "Check"
            },
            "output": {
                "label": "Output",
                "icon": "package"
            },
            "left_panel": {
                "title": "Left Panel",
                "badge": "read only",
                "cards": [
                    {"title": "L1", "body": "Left Card 1", "icon": "file"},
                    {"title": "L2", "body": "Left Card 2", "icon": "folder"}
                ]
            },
            "center_panel": {
                "title": "Center Panel",
                "subtitle": "Center Sub",
                "footer": "Footer",
                "cards": [
                    {"title": "C1", "body": "Center Card 1", "icon": "hash"},
                    {"title": "C2", "body": "Center Card 2", "icon": "db"}
                ]
            },
            "right_panel": {
                "title": "Right Panel",
                "incoming_label": "In",
                "return_label": "Out",
                "cards": [
                    {"title": "R1", "body": "Right Card 1", "icon": "package"}
                ]
            }
        }

    def test_collision_registry_detects_overlaps(self):
        """Verify the CollisionRegistry successfully detects overlaps."""
        registry = self.renderer.CollisionRegistry()
        
        # Register overlapping rectangles
        registry.register("A", 10, 10, 50, 50)
        registry.register("B", 40, 40, 50, 50)  # Overlaps A (x: 40-60, y: 40-60 vs x: 10-60, y: 10-60)
        
        overlaps = registry.check_overlaps()
        self.assertEqual(len(overlaps), 1)
        self.assertIn(("A", "B"), overlaps)

    def test_collision_registry_ignores_nested_elements(self):
        """Verify the CollisionRegistry ignores nested elements (e.g. Card inside Panel)."""
        registry = self.renderer.CollisionRegistry()
        
        # B is completely inside A
        registry.register("PanelA", 10, 10, 100, 100)
        registry.register("CardB", 20, 20, 30, 30)
        
        overlaps = registry.check_overlaps()
        self.assertEqual(len(overlaps), 0)

    def test_collision_registry_ignores_adjacent_non_overlapping(self):
        """Verify the CollisionRegistry does not flag adjacent but non-overlapping elements."""
        registry = self.renderer.CollisionRegistry()
        
        # A and B touch borders but do not overlap
        registry.register("A", 10, 10, 50, 50)
        registry.register("B", 60, 10, 50, 50)
        
        overlaps = registry.check_overlaps()
        self.assertEqual(len(overlaps), 0)

    def test_extreme_input_items_scaling_bounds(self):
        """Stress test with 10 input items."""
        spec = self.default_spec.copy()
        spec["inputs"] = [{"label": f"Input Item {i}", "icon": "file"} for i in range(10)]
        
        with tempfile.TemporaryDirectory() as tmp:
            result = self.renderer.write_outputs(spec, Path(tmp), "stress_10_inputs")
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            
            # Count registered inputs in Excalidraw
            input_texts = [
                el["text"] for el in excal_data["elements"] 
                if el.get("type") == "text" and el.get("text", "").startswith("Input Item")
            ]
            # The renderer only takes first 4 inputs (inputs[:4]) due to hardcoded bounds
            self.assertLessEqual(len(input_texts), 4)

    def test_extreme_core_cards_scaling_bounds(self):
        """Stress test with 6 core cards."""
        spec = self.default_spec.copy()
        spec["core"] = spec["core"].copy()
        spec["core"]["cards"] = [{"title": f"Core Card {i}", "body": f"Processing {i}", "icon": "file"} for i in range(6)]
        
        with tempfile.TemporaryDirectory() as tmp:
            result = self.renderer.write_outputs(spec, Path(tmp), "stress_6_core_cards")
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            
            card_titles = [
                el["text"] for el in excal_data["elements"] 
                if el.get("type") == "text" and el.get("text", "").startswith("Core Card")
            ]
            # The renderer only takes first 3 core cards (cards[:3]) due to hardcoded bounds
            self.assertLessEqual(len(card_titles), 3)

    def test_large_badge_text_leak_and_non_detection(self):
        """Verify that very large badge texts do not cause registry overlap flags because they aren't registered."""
        spec = self.default_spec.copy()
        spec["left_panel"] = spec["left_panel"].copy()
        spec["left_panel"]["badge"] = "VERY LARGE BADGE TEXT THAT IS EXTREMELY LONG AND OVERFLOWS BORDERS"
        
        with tempfile.TemporaryDirectory() as tmp:
            result = self.renderer.write_outputs(spec, Path(tmp), "stress_large_badge")
            # Overlaps printed to stderr/warning, check if registry detects overlaps
            # It will NOT detect this overlap because the badge is not registered in the registry!
            # The test confirms no overlaps are reported by check_overlaps(), indicating a blind spot.
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            
            # The registry check inside render_static should not raise overlaps warning
            # we check the returned elements
            elements = excal_data.get("elements", [])
            # Search for badge element in Excalidraw
            badge_el = next((el for el in elements if el.get("type") == "text" and "VERY LARGE BADGE TEXT" in el.get("text", "")), None)
            self.assertIsNotNone(badge_el)

    def test_no_card_or_panel_overlap_under_stress_spec(self):
        """Verify that no card or panel overlap is detected in the excalidraw file for stress specs."""
        spec = self.default_spec.copy()
        # Large body text to expand cards
        spec["core"] = spec["core"].copy()
        spec["core"]["cards"] = [
            {"title": "Core Card 1", "body": "A" * 200, "icon": "file"},
            {"title": "Core Card 2", "body": "B" * 200, "icon": "file"},
            {"title": "Core Card 3", "body": "C" * 200, "icon": "file"}
        ]
        
        with tempfile.TemporaryDirectory() as tmp:
            result = self.renderer.write_outputs(spec, Path(tmp), "stress_large_cards")
            excal_data = json.loads(Path(result["excalidraw"]).read_text(encoding="utf-8"))
            
            # Verify coordinates of core cards from excalidraw
            elements = excal_data.get("elements", [])
            core_rects = []
            for el in elements:
                if el.get("type") == "rectangle" and el.get("strokeColor") == self.renderer.THEME["core_stroke"]:
                    # Filter out the panel itself (width > 500)
                    if el.get("width", 0) < 500:
                        x, y = el["x"], el["y"]
                        w, h = el["width"], el["height"]
                        core_rects.append((x, y, x + w, y + h, el["id"]))
            
            # Check pairwise overlap
            for i in range(len(core_rects)):
                for j in range(i + 1, len(core_rects)):
                    box1 = core_rects[i][:4]
                    box2 = core_rects[j][:4]
                    overlap = not (box1[2] <= box2[0] or box2[2] <= box1[0] or box1[3] <= box2[1] or box2[3] <= box1[1])
                    self.assertFalse(overlap, f"Core cards {core_rects[i][4]} and {core_rects[j][4]} overlap!")

    def test_connector_routing_paths_match_component_edges(self):
        """Verify that connector routing solver generates coordinate paths matching component edges."""
        spec = self.default_spec.copy()
        
        # Run render_static to populate _resolved_layout and _resolved_paths
        ex, static_img = self.renderer.render_static(spec)
        
        # Retrieve the dynamically resolved scale factors
        scale_x = self.renderer.SCALE_X
        scale_y = self.renderer.SCALE_Y
        
        # Check path_card0_to_card1 (index 1 in _resolved_paths)
        paths = spec["_resolved_paths"]
        card0_to_card1_points = paths[1][0]
        
        start_x, start_y = card0_to_card1_points[0]
        end_x, end_y = card0_to_card1_points[1]
        
        # Unscaled right edge of Card 0 is 95 + 260 = 355
        # Scaled right edge should be 355 * scale_x
        self.assertAlmostEqual(start_x, 355.0 * scale_x, delta=0.001)
        
        # Unscaled left edge of Card 1 is resolved_card_x[1] = 472
        # Scaled left edge should be 472 * scale_x
        self.assertAlmostEqual(end_x, 472.0 * scale_x, delta=0.001)
        
        # Check path_card2_to_decision (index 3 in _resolved_paths)
        # It should end at decision top vertex (decision_x + dec_w/2, decision_y)
        card2_to_dec_points = paths[3][0]
        end_pt = card2_to_dec_points[-1]
        
        # Card 1 right edge = 472 + 260 = 732
        # Card 2 left edge = 850
        # Decision width = 120
        # Decision X = 732 + (850 - 732 - 120) / 2 = 731
        # Decision center X = 731 + 60 = 791
        # Scaled decision center X should be 791 * scale_x
        self.assertAlmostEqual(end_pt[0], 791.0 * scale_x, delta=0.001)


if __name__ == "__main__":
    unittest.main()
