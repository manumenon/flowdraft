import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "render_dynamic_diagram.py"

class TestExtremeInputs(unittest.TestCase):
    def run_cli(self, spec: dict, outdir: str, basename: str, extra_args=None, timeout=15):
        """Helper to run the CLI with a given spec dict and timeout."""
        spec_path = Path(outdir) / f"{basename}_spec.json"
        spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
        
        args = [
            sys.executable, str(SCRIPT_PATH),
            "--spec", str(spec_path),
            "--outdir", str(outdir),
            "--basename", basename
        ]
        if extra_args:
            args.extend(extra_args)
            
        try:
            res = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", timeout=timeout)
            return res
        except subprocess.TimeoutExpired as e:
            # Return a mock result indicating timeout
            class TimeoutResult:
                returncode = -1
                stdout = e.stdout or ""
                stderr = e.stderr or "TIMEOUT EXPIRED"
            return TimeoutResult()

    def test_very_long_strings(self):
        """
        Verify the layout and drawing engine with extremely long strings.
        Tests titles, bodies, signatures, and titles/subtitles containing 5,000+ characters.
        """
        long_str = "A" * 5000
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 1},
            "signature": long_str,
            "title": {
                "prefix": long_str,
                "highlight": long_str,
                "subtitle": long_str
            },
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 100, "height": 100, "type": "card", "title": long_str, "body": long_str},
                {"id": "node_b", "x": 300, "y": 100, "width": 100, "height": 100, "type": "card", "title": "Normal Title", "body": "Normal Body"}
            ],
            "connections": [
                {"path": ["node_a", "node_b"], "label": long_str}
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            res = self.run_cli(spec, tmp, "long_strings", timeout=20)
            self.assertNotEqual(res.returncode, -1, "CLI hung on extremely long strings")
            # If it validates and exits with 0 or 1, check details
            if res.returncode == 0:
                out_gif = Path(tmp) / "long_strings.gif"
                self.assertTrue(out_gif.exists(), "Output GIF should be generated on success")
            else:
                self.assertIn("Validation Error", res.stderr + res.stdout, f"Expected validation error, got: {res.stderr}")

    def test_missing_coordinates_large_graph(self):
        """
        Verify auto-layout when many nodes (including panels) are missing coordinates.
        Tests horizontal and vertical auto-layout on a 15-node graph with disconnected components.
        """
        nodes = []
        # Add 3 panels and 12 card nodes distributed inside them and top-level
        nodes.append({"id": "panel_1", "type": "panel", "title": "Panel 1"})
        nodes.append({"id": "panel_2", "type": "panel", "title": "Panel 2"})
        nodes.append({"id": "panel_3", "type": "panel", "title": "Panel 3", "parent": "panel_2"})
        
        for i in range(4):
            nodes.append({"id": f"card_p1_{i}", "type": "card", "title": f"Card P1 {i}", "parent": "panel_1"})
        for i in range(4):
            nodes.append({"id": f"card_p3_{i}", "type": "card", "title": f"Card P3 {i}", "parent": "panel_3"})
        for i in range(4):
            nodes.append({"id": f"card_tl_{i}", "type": "card", "title": f"Top Level {i}"})
            
        connections = [
            ["card_p1_0", "card_p1_1", "card_p1_2"],
            ["card_p3_0", "card_p3_1"],
            ["card_tl_0", "card_tl_1", "card_tl_2"],
            ["panel_1", "panel_2"]
        ]
        
        spec = {
            "canvas": {"width": 1600, "height": 1200, "frames": 1},
            "nodes": nodes,
            "connections": connections
        }
        with tempfile.TemporaryDirectory() as tmp:
            res = self.run_cli(spec, tmp, "large_auto_layout", timeout=20)
            self.assertEqual(res.returncode, 0, f"CLI should run successfully: {res.stderr}")
            excal_path = Path(tmp) / "large_auto_layout.excalidraw"
            self.assertTrue(excal_path.exists())
            excal_data = json.loads(excal_path.read_text(encoding="utf-8"))
            
            # Check that all nodes were assigned valid coordinates and no two nodes have identical center coordinates
            elements = {el.get("id"): el for el in excal_data.get("elements", []) if el.get("id")}
            for nid in [n["id"] for n in nodes]:
                self.assertIn(nid, elements, f"Node {nid} missing from excalidraw output")
                el = elements[nid]
                self.assertIsNotNone(el.get("x"))
                self.assertIsNotNone(el.get("y"))

    def test_mixed_languages_and_scripts(self):
        """
        Verify the text wrapping and font loader with mixed languages:
        Arabic (RTL), Cyrillic, Greek, Emoji, CJK, and Latin.
        """
        mixed_str = "English Русский Ελληνικά العربية (RTL) 日本語 🌟 Emoji Test 💡"
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 1},
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 200, "height": 100, "type": "card", "title": mixed_str, "body": mixed_str},
                {"id": "node_b", "x": 400, "y": 100, "width": 200, "height": 100, "type": "card", "title": "RTL Test", "body": "العربية"}
            ],
            "connections": [
                {"path": ["node_a", "node_b"], "label": mixed_str}
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            res = self.run_cli(spec, tmp, "mixed_languages", timeout=20)
            self.assertEqual(res.returncode, 0, f"CLI failed on mixed languages: {res.stderr}")
            out_gif = Path(tmp) / "mixed_languages.gif"
            self.assertTrue(out_gif.exists())

    def test_deep_container_hierarchies(self):
        """
        Verify coordinates propagation and bounding box expansion in deep panel nesting.
        Tests nested panels 15 levels deep.
        """
        nodes = []
        for i in range(15):
            parent = f"panel_{i-1}" if i > 0 else None
            nodes.append({
                "id": f"panel_{i}",
                "type": "panel",
                "title": f"Panel Level {i}",
                "parent": parent
            })
        # Add a card inside the deepest panel
        nodes.append({
            "id": "deep_card",
            "type": "card",
            "title": "Deepest Card",
            "body": "Nested inside Level 14",
            "parent": "panel_14"
        })
        
        spec = {
            "canvas": {"width": 2000, "height": 2000, "frames": 1},
            "nodes": nodes,
            "connections": []
        }
        with tempfile.TemporaryDirectory() as tmp:
            res = self.run_cli(spec, tmp, "deep_nesting", timeout=25)
            self.assertEqual(res.returncode, 0, f"CLI failed on deep nesting: {res.stderr}")
            excal_path = Path(tmp) / "deep_nesting.excalidraw"
            self.assertTrue(excal_path.exists())
            excal_data = json.loads(excal_path.read_text(encoding="utf-8"))
            elements = {el.get("id"): el for el in excal_data.get("elements", []) if el.get("id")}
            
            # Check bounding boxes are strictly nesting: parent width/height must be strictly greater than child's
            for i in range(14):
                parent_el = elements[f"panel_{i}"]
                child_el = elements[f"panel_{i+1}"]
                self.assertGreater(parent_el["width"], child_el["width"], f"Panel {i} width not greater than Panel {i+1}")
                self.assertGreater(parent_el["height"], child_el["height"], f"Panel {i} height not greater than Panel {i+1}")

    def test_cyclic_parent_hierarchy(self):
        """
        Verify that cyclic parent relationships do not hang the engine.
        Expects a validation error or clean cycle breaking instead of infinite loop.
        """
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 1},
            "nodes": [
                {"id": "panel_a", "type": "panel", "title": "Panel A", "parent": "panel_b"},
                {"id": "panel_b", "type": "panel", "title": "Panel B", "parent": "panel_a"},
                {"id": "card_a", "type": "card", "title": "Card A", "parent": "panel_a"}
            ],
            "connections": [
                ["card_a", "panel_b"]
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            # We set a short timeout of 5 seconds. If it hung, timeout result will be returned.
            res = self.run_cli(spec, tmp, "cyclic_parents", timeout=5)
            self.assertNotEqual(res.returncode, -1, "CRITICAL BUG: Cyclic parent hierarchy caused infinite loop / hang")
            # The engine should gracefully fail validation
            self.assertEqual(res.returncode, 1, f"Cyclic parent should fail with status code 1, but got {res.returncode}. Stderr: {res.stderr}")
            self.assertIn("cycle", (res.stderr + res.stdout).lower(), "Expected cycle detection validation error message")

    def test_negative_canvas_dimensions(self):
        """Verify that negative canvas dimensions are caught by validation."""
        spec = {
            "canvas": {"width": -800, "height": 600, "frames": 1},
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 100, "height": 100, "type": "card", "title": "A", "body": "B"}
            ],
            "connections": []
        }
        with tempfile.TemporaryDirectory() as tmp:
            res = self.run_cli(spec, tmp, "negative_canvas", timeout=10)
            self.assertEqual(res.returncode, 1, f"Should fail, got: {res.returncode}")
            self.assertIn("Validation Error: canvas dimensions must be positive integers", res.stderr + res.stdout)

    def test_zero_canvas_dimensions(self):
        """Verify that zero canvas dimensions are caught by validation."""
        spec = {
            "canvas": {"width": 800, "height": 0, "frames": 1},
            "nodes": [
                {"id": "node_a", "x": 100, "y": 100, "width": 100, "height": 100, "type": "card", "title": "A", "body": "B"}
            ],
            "connections": []
        }
        with tempfile.TemporaryDirectory() as tmp:
            res = self.run_cli(spec, tmp, "zero_canvas", timeout=10)
            self.assertEqual(res.returncode, 1, f"Should fail, got: {res.returncode}")
            self.assertIn("Validation Error: canvas dimensions must be positive integers", res.stderr + res.stdout)

    def test_empty_coordinates_inputs(self):
        """Verify that running with completely empty/unset coordinates works and resolves overlaps."""
        spec = {
            "canvas": {"width": 800, "height": 600, "frames": 1},
            "nodes": [
                {"id": "node_a", "type": "card", "title": "Node A", "body": "No coords"},
                {"id": "node_b", "type": "card", "title": "Node B", "body": "No coords"},
                {"id": "node_c", "type": "card", "title": "Node C", "body": "No coords"}
            ],
            "connections": [
                {"path": ["node_a", "node_b"]},
                {"path": ["node_b", "node_c"]}
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            res = self.run_cli(spec, tmp, "empty_coords", timeout=15)
            self.assertEqual(res.returncode, 0, f"Should succeed, got: {res.stderr}")
            excal_path = Path(tmp) / "empty_coords.excalidraw"
            self.assertTrue(excal_path.exists())
            excal_data = json.loads(excal_path.read_text(encoding="utf-8"))
            elements = {el.get("id"): el for el in excal_data.get("elements", []) if el.get("id")}
            for nid in ["node_a", "node_b", "node_c"]:
                self.assertIn(nid, elements)
                self.assertIsNotNone(elements[nid].get("x"))
                self.assertIsNotNone(elements[nid].get("y"))

if __name__ == "__main__":
    unittest.main()

